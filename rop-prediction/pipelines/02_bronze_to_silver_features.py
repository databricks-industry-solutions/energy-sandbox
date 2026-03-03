"""
02_bronze_to_silver_features.py
────────────────────────────────
PySpark batch job:
  drilling_demo_bronze.mseel_drilling_raw  →  drilling_demo_silver.mseel_drilling_clean
  drilling_demo_silver.mseel_drilling_clean →  drilling_demo_gold.rop_features_train

Transformations applied:
  • ts           = COALESCE(ts_original, _ingest_ts)
  • mse          = Teale mechanical-specific-energy (psi)
  • d_rop_dt     = lag-based derivative of ROP     (ft/hr per minute)
  • d_torque_dt  = lag-based derivative of Torque  (ft-lbs per minute)
  • d_spp_dt     = lag-based derivative of SPP     (psi per minute)
  • window_id    = date_trunc('minute', ts)
"""

import math
import os
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, TimestampType

# ── Configuration ────────────────────────────────────────────
BRONZE_TABLE  = os.getenv("BRONZE_TABLE",  "drilling_demo_bronze.mseel_drilling_raw")
SILVER_TABLE  = os.getenv("SILVER_TABLE",  "drilling_demo_silver.mseel_drilling_clean")
GOLD_FEAT_TBL = os.getenv("GOLD_FEAT_TBL", "drilling_demo_gold.rop_features_train")

# Bit diameter for MSEEL lateral sections (typically 6″ for Marcellus laterals)
BIT_DIAMETER_IN = float(os.getenv("BIT_DIAMETER_IN", "6.0"))

# Minimum ROP (ft/hr) to avoid division-by-zero in MSE formula
MIN_ROP_FOR_MSE = float(os.getenv("MIN_ROP_FOR_MSE", "0.5"))

# ── Bit area ─────────────────────────────────────────────────
BIT_AREA_IN2 = math.pi * (BIT_DIAMETER_IN / 2.0) ** 2   # ≈ 28.27 in² for 6″


def get_spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def compute_mse(df):
    """
    Teale Mechanical Specific Energy (psi):

        MSE = WOB_lbs / A_b  +  (2π × N × T_ftlbs × 60) / (A_b × ROP_fthr)

    Units:
        WOB      : klbs  → multiply by 1 000 for lbf
        A_b      : in²
        N        : RPM
        T        : ft-lbs (surface torque — downhole torque approximation)
        ROP      : ft/hr
        Result   : psi

    Clamp ROP ≥ MIN_ROP_FOR_MSE to avoid inf; set MSE = null if ROP ≤ 0.
    """
    rop_safe = F.greatest(F.col("rop"), F.lit(MIN_ROP_FOR_MSE))
    mse_expr = (
        (F.col("wob") * 1000.0 / BIT_AREA_IN2)
        + (
            (2.0 * math.pi * F.col("rpm") * F.col("torque") * 60.0)
            / (BIT_AREA_IN2 * rop_safe)
        )
    )
    return df.withColumn(
        "mse",
        F.when(
            F.col("rop").isNotNull()
            & (F.col("rop") > 0)
            & F.col("wob").isNotNull()
            & F.col("rpm").isNotNull()
            & F.col("torque").isNotNull(),
            mse_expr
        ).otherwise(F.lit(None).cast(DoubleType()))
    )


def compute_lag_derivatives(df):
    """
    Compute lag-based first-order time derivatives partitioned by well_id.

      d_x_dt = (x_current - x_prev) / dt_minutes

    Where dt_minutes = elapsed minutes between consecutive records.
    """
    w = (
        Window.partitionBy("well_id")
        .orderBy("ts")
    )

    # Previous-row values
    df = (
        df
        .withColumn("_prev_ts",     F.lag("ts",     1).over(w))
        .withColumn("_prev_rop",    F.lag("rop",    1).over(w))
        .withColumn("_prev_torque", F.lag("torque", 1).over(w))
        .withColumn("_prev_spp",    F.lag("spp",    1).over(w))
    )

    # Elapsed time in minutes between rows
    dt_min = (
        (F.unix_timestamp("ts") - F.unix_timestamp("_prev_ts")) / 60.0
    )

    def safe_deriv(cur_col: str, prev_col: str):
        """Return derivative or null if dt ≤ 0 or either value is null."""
        return F.when(
            dt_min.isNotNull() & (dt_min > 0)
            & F.col(prev_col).isNotNull() & F.col(cur_col).isNotNull(),
            (F.col(cur_col) - F.col(prev_col)) / dt_min
        ).otherwise(F.lit(None).cast(DoubleType()))

    df = (
        df
        .withColumn("d_rop_dt",    safe_deriv("rop",    "_prev_rop"))
        .withColumn("d_torque_dt", safe_deriv("torque", "_prev_torque"))
        .withColumn("d_spp_dt",    safe_deriv("spp",    "_prev_spp"))
        .drop("_prev_ts", "_prev_rop", "_prev_torque", "_prev_spp")
    )
    return df


def bronze_to_silver(spark: SparkSession) -> int:
    print(f"\n── Bronze → Silver ──────────────────────────")
    print(f"   Source : {BRONZE_TABLE}")
    print(f"   Target : {SILVER_TABLE}")

    raw = spark.table(BRONZE_TABLE)
    count_in = raw.count()
    print(f"   Input rows: {count_in:,}")

    # Canonical timestamp
    df = raw.withColumn(
        "ts",
        F.coalesce(
            F.col("ts_original").cast(TimestampType()),
            F.col("_ingest_ts").cast(TimestampType())
        )
    )

    # Drop rows where ts is still null (can't window without time)
    df = df.filter(F.col("ts").isNotNull())

    # Drop obvious duplicates (same well, ts, md)
    df = df.dropDuplicates(["well_id", "ts", "md"])

    # Filter out non-drilling rows (rig_state ≠ 'Rotating' / similar, rop ≤ 0)
    # Keep all rows but flag — model training filters later
    df = df.filter(
        F.col("md").isNotNull()
        & F.col("md").between(0, 30_000)   # sanity: <30,000 ft MD
    )

    # Compute MSE
    df = compute_mse(df)

    # Compute lag-based derivatives
    df = compute_lag_derivatives(df)

    # window_id = minute-truncated timestamp
    df = df.withColumn(
        "window_id",
        F.date_trunc("minute", F.col("ts")).cast(TimestampType())
    )

    # Select Silver columns
    silver_cols = [
        "well_id", "ts", "md", "tvd", "wob", "rpm", "torque", "spp",
        "flow", "hookload", "rop", "rig_state",
        "mse", "d_rop_dt", "d_torque_dt", "d_spp_dt", "window_id"
    ]
    df = df.select(*silver_cols)

    count_out = df.count()
    print(f"   Output rows: {count_out:,}")

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(SILVER_TABLE)
    )
    print(f"   ✓ Written to {SILVER_TABLE}")
    return count_out


def silver_to_gold_features(spark: SparkSession) -> int:
    print(f"\n── Silver → Gold (training features) ───────")
    print(f"   Source : {SILVER_TABLE}")
    print(f"   Target : {GOLD_FEAT_TBL}")

    silver = spark.table(SILVER_TABLE)

    feature_cols = [
        "well_id", "ts", "md", "tvd",
        "wob", "rpm", "torque", "spp", "flow", "hookload",
        "mse", "d_rop_dt", "d_torque_dt", "d_spp_dt",
    ]

    gold = (
        silver
        .select(*feature_cols, F.col("rop").alias("label_rop"))
        # Keep only rows where label and all core features are valid
        .filter(
            F.col("label_rop").isNotNull()
            & F.col("label_rop").between(0, 1000)    # ROP sanity (ft/hr)
            & F.col("wob").isNotNull()
            & F.col("rpm").isNotNull()
            & F.col("mse").isNotNull()
        )
        # Exclude stationary / off-bottom rows (ROP ≈ 0)
        .filter(F.col("label_rop") >= 1.0)
    )

    count = gold.count()
    print(f"   Training rows after filters: {count:,}")

    (
        gold.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(GOLD_FEAT_TBL)
    )
    print(f"   ✓ Written to {GOLD_FEAT_TBL}")
    return count


def run():
    spark = get_spark()

    print("=" * 60)
    print("Bronze → Silver → Gold Feature Pipeline")
    print(f"Bit diameter : {BIT_DIAMETER_IN}\" | Bit area: {BIT_AREA_IN2:.2f} in²")
    print("=" * 60)

    silver_rows = bronze_to_silver(spark)
    gold_rows   = silver_to_gold_features(spark)

    print("\n✅ Feature pipeline complete")
    print(f"   Silver rows : {silver_rows:,}")
    print(f"   Gold rows   : {gold_rows:,}")


if __name__ == "__main__":
    run()
