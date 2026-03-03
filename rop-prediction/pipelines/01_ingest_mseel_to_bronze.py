"""
01_ingest_mseel_to_bronze.py
────────────────────────────
PySpark job: read MSEEL drilling CSV files → drilling_demo_bronze.mseel_drilling_raw

MSEEL (Marcellus Shale Energy and Environment Laboratory) raw drilling data lives
under /mnt/mseel/<WELL>/Drilling/*.csv.  Each file contains time-stamped surface
measurements recorded at ~1–5 s intervals.

Usage (Databricks notebook / job):
    %run /Workspace/.../01_ingest_mseel_to_bronze

Environment variables (override defaults):
    MSEEL_WELL_PATHS   : comma-separated mount paths
    MSEEL_BIT_DEPTH_COL: CSV column name for measured depth (default 'Bit Depth (ft)')
    BRONZE_TABLE       : target Delta table (default 'drilling_demo_bronze.mseel_drilling_raw')
"""

import os
import re
from datetime import datetime, timezone
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, TimestampType
)

# ── Configuration ────────────────────────────────────────────
WELL_PATHS: list[str] = [
    p.strip()
    for p in os.getenv(
        "MSEEL_WELL_PATHS",
        "/mnt/mseel/MIP_3H/Drilling/,/mnt/mseel/MIP_4H/Drilling/"
    ).split(",")
    if p.strip()
]

BRONZE_TABLE = os.getenv("BRONZE_TABLE", "drilling_demo_bronze.mseel_drilling_raw")

# Mapping from common MSEEL CSV column names → canonical schema names.
# Keys are lower-cased and stripped of whitespace during matching.
COLUMN_MAP: dict[str, str] = {
    # Depth
    "bit depth (ft)":        "md",
    "bit depth":             "md",
    "measured depth":        "md",
    "md":                    "md",
    "hole depth (ft)":       "tvd",
    "tvd":                   "tvd",
    # Drilling parameters
    "wob (klbs)":            "wob",
    "weight on bit (klbs)":  "wob",
    "wob":                   "wob",
    "rpm":                   "rpm",
    "rotary speed (rpm)":    "rpm",
    "torque (ft-lbs)":       "torque",
    "surface torque (ft-lbs)": "torque",
    "torque":                "torque",
    "standpipe pressure (psi)": "spp",
    "spp (psi)":             "spp",
    "spp":                   "spp",
    "flow (gpm)":            "flow",
    "pump flow (gpm)":       "flow",
    "flow out (gpm)":        "flow",
    "flow":                  "flow",
    "hookload (klbs)":       "hookload",
    "hook load (klbs)":      "hookload",
    "hookload":              "hookload",
    "rop (ft/hr)":           "rop",
    "rop (ft/h)":            "rop",
    "rate of penetration":   "rop",
    "rop":                   "rop",
    "rig state":             "rig_state",
}

TIMESTAMP_COLS = [
    "date time", "datetime", "timestamp", "time", "date/time", "date_time"
]


def get_spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def infer_well_id(path: str) -> str:
    """Extract well identifier from file path.

    Looks for patterns like MIP_3H, MIP3H, MIP-3H anywhere in the path.
    Falls back to the top-level folder name.
    """
    patterns = [
        r"(MIP[\-_]?\d+[A-Z]+)",   # MIP_3H, MIP3H, MIP-3H
        r"([\w]+[\-_]\d+[A-Z]+)",  # generic WELL_NNX
    ]
    for pat in patterns:
        m = re.search(pat, path, re.IGNORECASE)
        if m:
            return m.group(1).upper().replace("-", "_")
    # fallback: second-to-last path component
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    return parts[-2].upper() if len(parts) >= 2 else "UNKNOWN"


def rename_columns(df: DataFrame) -> DataFrame:
    """Normalise CSV column names to the canonical schema."""
    rename = {}
    for col in df.columns:
        canonical = COLUMN_MAP.get(col.strip().lower())
        if canonical and canonical not in rename.values():
            rename[col] = canonical

    for old, new in rename.items():
        df = df.withColumnRenamed(old, new)
    return df


def parse_timestamp(df: DataFrame) -> DataFrame:
    """Find and parse the timestamp column into ts_original (TIMESTAMP)."""
    ts_col = None
    for col in df.columns:
        if col.strip().lower() in TIMESTAMP_COLS:
            ts_col = col
            break

    if ts_col is None:
        print(f"  ⚠ No timestamp column found; ts_original will be null")
        df = df.withColumn("ts_original", F.lit(None).cast(TimestampType()))
    else:
        # Try multiple format strings common in MSEEL data
        df = df.withColumn(
            "ts_original",
            F.coalesce(
                F.to_timestamp(F.col(ts_col), "M/d/yyyy H:mm:ss"),
                F.to_timestamp(F.col(ts_col), "yyyy-MM-dd HH:mm:ss"),
                F.to_timestamp(F.col(ts_col), "yyyy-MM-dd'T'HH:mm:ss"),
                F.to_timestamp(F.col(ts_col), "MM/dd/yyyy HH:mm:ss"),
                F.to_timestamp(F.col(ts_col), "dd/MM/yyyy HH:mm:ss"),
                F.to_timestamp(F.col(ts_col)),
            )
        ).drop(ts_col)

    return df


def cast_numeric_columns(df: DataFrame) -> DataFrame:
    """Cast all expected numeric channels to DOUBLE, silently coercing nulls."""
    numeric_cols = ["md", "tvd", "wob", "rpm", "torque", "spp", "flow", "hookload", "rop"]
    for c in numeric_cols:
        if c in df.columns:
            df = df.withColumn(c, F.col(c).cast(DoubleType()))
        else:
            df = df.withColumn(c, F.lit(None).cast(DoubleType()))
    if "rig_state" not in df.columns:
        df = df.withColumn("rig_state", F.lit(None).cast(StringType()))
    return df


def ensure_required_columns(df: DataFrame, well_id: str, file_path: str) -> DataFrame:
    """Add lineage and well_id columns."""
    ingest_ts = datetime.now(timezone.utc)
    df = (
        df
        .withColumn("well_id",    F.lit(well_id))
        .withColumn("_file",      F.lit(file_path))
        .withColumn("_ingest_ts", F.lit(ingest_ts).cast(TimestampType()))
    )
    return df


def select_final_columns(df: DataFrame) -> DataFrame:
    final_cols = [
        "well_id", "ts_original", "md", "tvd", "wob", "rpm",
        "torque", "spp", "flow", "hookload", "rop", "rig_state",
        "_file", "_ingest_ts"
    ]
    return df.select(*final_cols)


def ingest_path(spark: SparkSession, path: str, well_id: str) -> int:
    """Read one well's CSV directory and append to Bronze Delta table."""
    print(f"\n[{well_id}] Reading: {path}")

    try:
        raw_df = (
            spark.read
            .option("header", "true")
            .option("inferSchema", "false")   # all strings initially
            .option("multiLine", "false")
            .option("ignoreLeadingWhiteSpace", "true")
            .option("ignoreTrailingWhiteSpace", "true")
            .option("mode", "PERMISSIVE")     # bad rows → nulls, not errors
            .csv(path)
            .withColumn("_source_file", F.input_file_name())
        )
    except Exception as e:
        print(f"  ✗ Failed to read {path}: {e}")
        return 0

    print(f"  Raw columns ({len(raw_df.columns)}): {raw_df.columns[:8]} …")
    count_raw = raw_df.count()
    print(f"  Raw row count: {count_raw:,}")

    df = rename_columns(raw_df)
    df = parse_timestamp(df)
    df = cast_numeric_columns(df)
    df = ensure_required_columns(df, well_id, path)
    df = select_final_columns(df)

    # Filter rows where at least one key drilling channel is non-null
    df = df.filter(
        F.col("md").isNotNull() | F.col("rop").isNotNull() | F.col("wob").isNotNull()
    )

    count_clean = df.count()
    print(f"  Rows after filtering: {count_clean:,}  (dropped {count_raw - count_clean:,} empty rows)")

    if count_clean == 0:
        print(f"  ⚠ No valid rows to write for {well_id}, skipping.")
        return 0

    (
        df.write
        .format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .saveAsTable(BRONZE_TABLE)
    )
    print(f"  ✓ Appended {count_clean:,} rows → {BRONZE_TABLE}")
    return count_clean


def run():
    spark = get_spark()
    spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")

    print("=" * 60)
    print("MSEEL Bronze Ingestion")
    print(f"Target table : {BRONZE_TABLE}")
    print(f"Well paths   : {WELL_PATHS}")
    print("=" * 60)

    total = 0
    for path in WELL_PATHS:
        well_id = infer_well_id(path)
        total += ingest_path(spark, path, well_id)

    print(f"\n✅ Ingestion complete — {total:,} total rows written to {BRONZE_TABLE}")


if __name__ == "__main__":
    run()
