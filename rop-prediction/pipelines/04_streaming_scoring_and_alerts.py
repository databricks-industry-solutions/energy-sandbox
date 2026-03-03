"""
04_streaming_scoring_and_alerts.py
────────────────────────────────────
Spark Structured Streaming job:
  Input  : drilling_demo_silver.mseel_drilling_clean  (streaming Delta read)
           OR a Kafka/Zerobus topic  (see STREAM_SOURCE env var)
  Output : drilling_demo_gold.rop_predictions_stream  (Delta sink)
           + Lakebase.predictions  (foreachBatch bulk insert)
           + Lakebase.alerts       (foreachBatch bulk insert)

The MLflow model rop_xgb_mseel is loaded once and broadcast to all executors
via a Pandas UDF for vectorised, low-latency inference.

Environment variables:
    MLFLOW_MODEL_NAME    : registered model name (default rop_xgb_mseel)
    GOLD_PRED_TABLE      : output Delta table
    STREAM_SOURCE        : delta | kafka  (default delta)
    KAFKA_BOOTSTRAP      : broker:9092 (only for kafka source)
    KAFKA_TOPIC          : topic name
    CHECKPOINT_PATH      : Delta checkpoint location
    ROP_GAP_THRESHOLD    : ft/hr above which to flag hazard
    MSE_HIGH_THRESHOLD   : psi above which to flag HIGH_MSE
    TRIGGER_INTERVAL     : streaming trigger interval (default "10 seconds")
"""

import os
import json
import time
import math
from datetime import datetime, timezone
import mlflow
import mlflow.pyfunc
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, TimestampType, LongType
)

# ── Configuration ─────────────────────────────────────────────
MODEL_NAME       = os.getenv("MLFLOW_MODEL_NAME",   "rop_xgb_mseel")
SILVER_TABLE     = os.getenv("SILVER_TABLE",         "drilling_demo_silver.mseel_drilling_clean")
GOLD_PRED_TABLE  = os.getenv("GOLD_PRED_TABLE",      "drilling_demo_gold.rop_predictions_stream")
CHECKPOINT_PATH  = os.getenv("CHECKPOINT_PATH",      "/tmp/ckpt/rop_streaming")
STREAM_SOURCE    = os.getenv("STREAM_SOURCE",         "delta")  # delta | kafka
KAFKA_BOOTSTRAP  = os.getenv("KAFKA_BOOTSTRAP",       "localhost:9092")
KAFKA_TOPIC      = os.getenv("KAFKA_TOPIC",           "drilling_mseel_stream")
TRIGGER_INTERVAL = os.getenv("TRIGGER_INTERVAL",      "10 seconds")

ROP_GAP_THRESHOLD  = float(os.getenv("ROP_GAP_THRESHOLD",  "20.0"))
MSE_HIGH_THRESHOLD = float(os.getenv("MSE_HIGH_THRESHOLD", "150000.0"))
MSE_OPT_THRESHOLD  = float(os.getenv("MSE_OPT_THRESHOLD",  "50000.0"))

# Lakebase connection (injected by Databricks App resource)
PGHOST     = os.getenv("PGHOST",     "localhost")
PGPORT     = os.getenv("PGPORT",     "5432")
PGDATABASE = os.getenv("PGDATABASE", "drilling_demo_app")
PGUSER     = os.getenv("PGUSER",     "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")

FEATURES = [
    "wob", "rpm", "torque", "spp", "flow", "hookload",
    "mse", "d_rop_dt", "d_torque_dt", "d_spp_dt", "md", "tvd",
]

# Kafka event schema (matches 05_mseel_replay_producer.py output)
KAFKA_SCHEMA = StructType([
    StructField("well_id",   StringType(),    True),
    StructField("ts",        StringType(),    True),   # ISO-8601 string
    StructField("md",        DoubleType(),    True),
    StructField("tvd",       DoubleType(),    True),
    StructField("wob",       DoubleType(),    True),
    StructField("rpm",       DoubleType(),    True),
    StructField("torque",    DoubleType(),    True),
    StructField("spp",       DoubleType(),    True),
    StructField("flow",      DoubleType(),    True),
    StructField("hookload",  DoubleType(),    True),
    StructField("rop",       DoubleType(),    True),
    StructField("rig_state", StringType(),    True),
    StructField("mse",       DoubleType(),    True),
    StructField("d_rop_dt",  DoubleType(),    True),
    StructField("d_torque_dt", DoubleType(),  True),
    StructField("d_spp_dt",  DoubleType(),    True),
])


# ── Model broadcast ──────────────────────────────────────────
def load_production_model_uri() -> str:
    client = mlflow.tracking.MlflowClient()
    versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    if not versions:
        raise RuntimeError(f"No Production version found for model '{MODEL_NAME}'")
    uri = f"models:/{MODEL_NAME}/{versions[0].version}"
    print(f"  Loaded model: {uri}")
    return uri


def make_score_udf(model_uri: str):
    """
    Returns a Pandas UDF that scores a DataFrame of features.
    The model is loaded once per executor process (not per row).
    """
    import pandas as pd
    import mlflow.pyfunc

    def _score_batch(features_pdf: pd.DataFrame) -> pd.Series:
        # Lazy-load model once per executor
        if not hasattr(_score_batch, "_model"):
            _score_batch._model = mlflow.pyfunc.load_model(model_uri)
        model = _score_batch._model
        try:
            preds = model.predict(features_pdf[FEATURES].fillna(0.0))
            if isinstance(preds, pd.DataFrame):
                preds = preds.iloc[:, 0]
            return pd.Series(preds.values, name="rop_pred").clip(lower=0.0)
        except Exception as e:
            print(f"Scoring error: {e}")
            return pd.Series([float("nan")] * len(features_pdf), name="rop_pred")

    from pyspark.sql.functions import pandas_udf

    @pandas_udf(DoubleType())
    def score_udf(*cols) -> pd.Series:
        pdf = pd.concat(list(cols), axis=1)
        pdf.columns = FEATURES
        return _score_batch(pdf)

    return score_udf


def apply_hazard_rules(df: DataFrame) -> DataFrame:
    """Classify each scored row into a hazard category."""
    return df.withColumn(
        "hazard_flag",
        F.when(
            F.col("mse").isNotNull() & (F.col("mse") > MSE_HIGH_THRESHOLD),
            F.lit("HIGH_MSE")
        ).when(
            F.col("rop_gap").isNotNull()
            & (F.col("rop_gap") > ROP_GAP_THRESHOLD)
            & F.col("mse").isNotNull()
            & (F.col("mse") > MSE_OPT_THRESHOLD),
            F.lit("INEFFICIENT_DRILLING")
        ).when(
            F.col("rop_actual").isNotNull()
            & (F.col("rop_actual") < 2.0)
            & F.col("wob").isNotNull()
            & (F.col("wob") > 15.0),
            F.lit("STUCK_PIPE")
        ).otherwise(F.lit("NORMAL"))
    )


# ── Streaming read ───────────────────────────────────────────
def build_stream(spark: SparkSession) -> DataFrame:
    if STREAM_SOURCE == "kafka":
        raw = (
            spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
            .option("subscribe", KAFKA_TOPIC)
            .option("startingOffsets", "latest")
            .option("failOnDataLoss", "false")
            .load()
        )
        df = (
            raw.select(
                F.from_json(
                    F.col("value").cast(StringType()),
                    KAFKA_SCHEMA
                ).alias("e")
            )
            .select("e.*")
            .withColumn("ts", F.to_timestamp(F.col("ts")))
        )
        return df

    # Default: Delta streaming table
    return (
        spark.readStream
        .format("delta")
        .table(SILVER_TABLE)
    )


# ── Lakebase sink (foreachBatch) ─────────────────────────────
def _lakebase_dsn() -> str:
    return (
        f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}"
        f"@{PGHOST}:{PGPORT}/{PGDATABASE}"
    )


def write_to_lakebase(batch_df: DataFrame, batch_id: int):
    """
    foreachBatch function: bulk-insert predictions and alerts into Lakebase.
    Uses psycopg2 executemany for batched commits — NOT per-row.
    """
    if batch_df.rdd.isEmpty():
        return

    pdf = batch_df.toPandas()
    scored_ts = datetime.now(timezone.utc)

    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            host=PGHOST, port=int(PGPORT),
            dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD,
            connect_timeout=10,
        )
        cur = conn.cursor()

        # ── Bulk insert predictions ─────────────────────────
        pred_rows = [
            (
                str(row.well_id),
                row.ts.isoformat() if hasattr(row.ts, "isoformat") else str(row.ts),
                _float(row, "md"),
                _float(row, "rop_actual"),
                _float(row, "rop_pred"),
                _float(row, "rop_gap"),
                _float(row, "mse"),
                str(row.hazard_flag) if row.hazard_flag else "NORMAL",
            )
            for _, row in pdf.iterrows()
        ]
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO predictions
              (well_id, ts, md, rop_actual, rop_pred, rop_gap, mse, hazard_flag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            pred_rows,
            page_size=500,
        )

        # ── Bulk insert alerts (only hazardous rows) ────────
        alert_rows = [
            (
                str(row.well_id),
                row.ts.isoformat() if hasattr(row.ts, "isoformat") else str(row.ts),
                str(row.hazard_flag),
                _alert_severity(str(row.hazard_flag)),
                _alert_message(row),
            )
            for _, row in pdf.iterrows()
            if str(row.get("hazard_flag", "NORMAL")) != "NORMAL"
        ]
        if alert_rows:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO alerts (well_id, ts, alert_type, severity, message)
                VALUES (%s, %s, %s, %s, %s)
                """,
                alert_rows,
                page_size=200,
            )

        conn.commit()
        cur.close()
        conn.close()
        print(
            f"  Batch {batch_id}: {len(pred_rows)} predictions, "
            f"{len(alert_rows)} alerts → Lakebase"
        )

    except Exception as e:
        print(f"  ⚠ Lakebase write failed for batch {batch_id}: {e}")


def _float(row, col: str):
    v = getattr(row, col, None)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


def _alert_severity(hazard_flag: str) -> str:
    return {
        "STUCK_PIPE":          "CRITICAL",
        "HIGH_MSE":            "WARNING",
        "INEFFICIENT_DRILLING":"WARNING",
    }.get(hazard_flag, "INFO")


def _alert_message(row) -> str:
    flag = str(getattr(row, "hazard_flag", ""))
    msgs = {
        "HIGH_MSE": (
            f"MSE={_safe_fmt(row,'mse',0)} psi exceeds threshold "
            f"{MSE_HIGH_THRESHOLD:.0f} psi at MD={_safe_fmt(row,'md',0)} ft"
        ),
        "INEFFICIENT_DRILLING": (
            f"ROP gap={_safe_fmt(row,'rop_gap',1)} ft/hr — "
            f"actual {_safe_fmt(row,'rop_actual',1)} vs predicted "
            f"{_safe_fmt(row,'rop_pred',1)} ft/hr"
        ),
        "STUCK_PIPE": (
            f"Potential stuck pipe — ROP={_safe_fmt(row,'rop_actual',1)} ft/hr "
            f"with WOB={_safe_fmt(row,'wob',1)} klbs at MD={_safe_fmt(row,'md',0)} ft"
        ),
    }
    return msgs.get(flag, flag)


def _safe_fmt(row, col: str, decimals: int) -> str:
    v = getattr(row, col, None)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"{v:.{decimals}f}"


# ── Main streaming job ───────────────────────────────────────
def run():
    spark = SparkSession.builder.getOrCreate()
    spark.conf.set("spark.sql.streaming.schemaInference", "true")

    print("=" * 60)
    print("Streaming ROP Scoring & Hazard Detection")
    print(f"Model  : {MODEL_NAME}")
    print(f"Source : {STREAM_SOURCE.upper()} — {SILVER_TABLE if STREAM_SOURCE=='delta' else KAFKA_TOPIC}")
    print(f"Sink   : {GOLD_PRED_TABLE} + Lakebase")
    print("=" * 60)

    model_uri = load_production_model_uri()
    score_udf = make_score_udf(model_uri)

    stream_df = build_stream(spark)

    # Compute MSE inline for Kafka source (Silver already has it for Delta source)
    BIT_AREA = math.pi * (6.0 / 2.0) ** 2
    if STREAM_SOURCE == "kafka":
        stream_df = stream_df.withColumn(
            "mse",
            F.when(
                F.col("rop").isNotNull() & (F.col("rop") > 0.5),
                (F.col("wob") * 1000.0 / BIT_AREA)
                + (2.0 * math.pi * F.col("rpm") * F.col("torque") * 60.0)
                / (BIT_AREA * F.col("rop"))
            ).otherwise(F.lit(None))
        )

    # Fill nulls for features going into UDF
    feature_cols = [F.col(c) for c in FEATURES]

    scored = (
        stream_df
        .withColumn("rop_pred",   score_udf(*feature_cols))
        .withColumn("rop_actual", F.col("rop"))
        .withColumn("rop_gap",    F.col("rop_pred") - F.col("rop_actual"))
    )

    scored = apply_hazard_rules(scored)

    # Add streaming metadata
    scored = (
        scored
        .withColumn("_scored_ts", F.current_timestamp())
    )

    # Output schema for Delta sink
    delta_cols = [
        "well_id", "ts", "md", "rop_actual", "rop_pred",
        "rop_gap", "mse", "hazard_flag", "_scored_ts",
    ]

    # ── Write to Gold Delta ──────────────────────────────────
    delta_query = (
        scored
        .select(*delta_cols)
        .writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{CHECKPOINT_PATH}/delta")
        .option("mergeSchema", "true")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .toTable(GOLD_PRED_TABLE)
    )

    # ── Write to Lakebase via foreachBatch ───────────────────
    lakebase_query = (
        scored
        .select(
            "well_id", "ts", "md",
            "rop_actual", "rop_pred", "rop_gap", "mse",
            "hazard_flag", "wob",
        )
        .writeStream
        .foreachBatch(write_to_lakebase)
        .option("checkpointLocation", f"{CHECKPOINT_PATH}/lakebase")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .start()
    )

    print("\n✅ Both streaming queries started. Awaiting termination …")
    lakebase_query.awaitTermination()


if __name__ == "__main__":
    run()
