# Databricks notebook source
# MAGIC %md
# MAGIC # ESP Real-Time Inference — Structured Streaming Job
# MAGIC
# MAGIC Reads new feature snapshots from the Gold feature table via Change Data Feed,
# MAGIC runs the production XGBoost model, and writes predictions to
# MAGIC `esp_ai.gold.esp_failure_predictions`.
# MAGIC
# MAGIC **Trigger:** Continuous (ProcessingTime = "5 minutes") or AvailableNow for batch backfill
# MAGIC **Input:**  `esp_ai.gold.esp_features` (CDF enabled)
# MAGIC **Output:** `esp_ai.gold.esp_failure_predictions`

# COMMAND ----------

import mlflow
import mlflow.xgboost
import pandas as pd
import numpy as np
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType

mlflow.set_registry_uri("databricks-uc")

MODEL_NAME   = "esp_ai.gold.esp_failure_72h_model"
MODEL_ALIAS  = "production"
FEAT_TNAME   = "esp_ai.gold.esp_features"
PRED_TNAME   = "esp_ai.gold.esp_failure_predictions"
CHECKPOINT   = "/Volumes/esp_ai/gold/checkpoints/inference_streaming"

FEATURE_COLS = [
    "current_mean_1h", "current_std_1h", "current_mean_24h", "current_std_24h", "current_roc_10m",
    "pressure_mean_1h", "pressure_std_1h", "pressure_roc_10m",
    "vibration_std_1h", "vibration_roc_10m",
    "starts_last_24h", "trips_last_7d", "minor_alarms_last_7d",
    "gaslock_score", "load_factor",
    "days_since_last_preventive", "days_since_last_corrective",
    "repeat_failure_same_cause_180d", "orders_per_runtime_hour_365d",
    "average_mtbf_hours", "sum_actual_cost_365d",
    "num_critical_parts_available",
]

# Priority score weights
W_RISK  = 0.6
W_PARTS = 0.2
W_COST  = 0.2
MAX_COST_NORM = 50_000.0

# COMMAND ----------
# MAGIC %md ## 1. Load production model

# COMMAND ----------

model_uri = f"models:/{MODEL_NAME}@{MODEL_ALIAS}"
loaded_model = mlflow.xgboost.load_model(model_uri)

# Capture model metadata for prediction rows
client = mlflow.MlflowClient()
mv = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
MODEL_VERSION = mv.version
MODEL_RUN_ID  = mv.run_id

print(f"Loaded {MODEL_NAME}@{MODEL_ALIAS}  version={MODEL_VERSION}  run_id={MODEL_RUN_ID}")

# COMMAND ----------
# MAGIC %md ## 2. Define inference UDF

# COMMAND ----------

# Broadcast model to workers
bc_model = spark.sparkContext.broadcast(loaded_model)

def run_inference_batch(pandas_df: pd.DataFrame) -> pd.DataFrame:
    """Score a micro-batch of feature rows, return prediction columns."""
    model = bc_model.value
    X = pandas_df[FEATURE_COLS].fillna(-1)
    probs = model.predict_proba(X)[:, 1]

    # Risk bucket
    risk_buckets = np.where(probs >= 0.65, "HIGH",
                   np.where(probs >= 0.30, "MEDIUM", "LOW"))

    # Compute SHAP for top-3 features
    import shap
    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(X)   # shape (n, n_features)
    top3_idx   = np.argsort(np.abs(shap_vals), axis=1)[:, -3:][:, ::-1]

    feat_names = np.array(FEATURE_COLS)

    pandas_df["failure_risk_score"] = probs
    pandas_df["risk_bucket"]        = risk_buckets

    # Priority score
    parts_factor = np.where(pandas_df.get("critical_parts_available", False), 1.0, 0.7)
    cost_norm    = np.clip(pandas_df.get("sum_actual_cost_365d", 0).fillna(0) / MAX_COST_NORM, 0, 1)
    pandas_df["priority_score"] = (
        probs * W_RISK
        + parts_factor * W_PARTS
        + cost_norm.values * W_COST
    )

    pandas_df["top_feature_1"] = feat_names[top3_idx[:, 0]]
    pandas_df["top_feature_2"] = feat_names[top3_idx[:, 1]]
    pandas_df["top_feature_3"] = feat_names[top3_idx[:, 2]]
    pandas_df["top_feature_1_value"] = shap_vals[np.arange(len(shap_vals)), top3_idx[:, 0]]
    pandas_df["top_feature_2_value"] = shap_vals[np.arange(len(shap_vals)), top3_idx[:, 1]]
    pandas_df["top_feature_3_value"] = shap_vals[np.arange(len(shap_vals)), top3_idx[:, 2]]

    pandas_df["model_version"]    = MODEL_VERSION
    pandas_df["model_run_id"]     = MODEL_RUN_ID
    pandas_df["prediction_ts"]    = pandas_df["snapshot_ts"]

    return pandas_df[[
        "esp_id", "prediction_ts", "failure_risk_score", "risk_bucket",
        "priority_score",
        "top_feature_1", "top_feature_2", "top_feature_3",
        "top_feature_1_value", "top_feature_2_value", "top_feature_3_value",
        "model_version", "model_run_id",
    ]]

# COMMAND ----------
# MAGIC %md ## 3. Streaming read from CDF

# COMMAND ----------

stream_df = (
    spark.readStream
    .format("delta")
    .option("readChangeFeed", "true")
    .option("startingVersion", "latest")
    .table(FEAT_TNAME)
    # Only process INSERT operations (new feature snapshots)
    .filter(F.col("_change_type") == "insert")
    .drop("_change_type", "_commit_version", "_commit_timestamp")
    # Include fields needed for priority score
    .select(
        ["esp_id", "snapshot_ts", "critical_parts_available", "sum_actual_cost_365d"]
        + FEATURE_COLS
    )
)

# COMMAND ----------
# MAGIC %md ## 4. foreachBatch write function

# COMMAND ----------

def write_predictions(micro_batch_df, batch_id):
    if micro_batch_df.isEmpty():
        return

    # Run pandas inference
    result_pd = micro_batch_df.toPandas()
    preds_pd  = run_inference_batch(result_pd)
    preds_spark = spark.createDataFrame(preds_pd)

    # Append to predictions table
    (
        preds_spark.write
        .format("delta")
        .mode("append")
        .saveAsTable(PRED_TNAME)
    )

    print(f"Batch {batch_id}: scored {len(preds_pd)} rows  "
          f"HIGH={sum(preds_pd['risk_bucket']=='HIGH')}  "
          f"MEDIUM={sum(preds_pd['risk_bucket']=='MEDIUM')}")

# COMMAND ----------
# MAGIC %md ## 5. Start streaming query

# COMMAND ----------

query = (
    stream_df.writeStream
    .foreachBatch(write_predictions)
    .option("checkpointLocation", CHECKPOINT)
    .trigger(processingTime="5 minutes")   # change to availableNow=True for backfill
    .queryName("esp_inference_streaming")
    .start()
)

print(f"Streaming query started: {query.id}")
print("Waiting for termination signal...")
# In production the job runs indefinitely; in a notebook use query.awaitTermination(timeout_secs)
# query.awaitTermination()
