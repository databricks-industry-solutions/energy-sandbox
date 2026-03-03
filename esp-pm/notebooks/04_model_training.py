# Databricks notebook source
# MAGIC %md
# MAGIC # ESP Failure Prediction — XGBoost Model Training
# MAGIC
# MAGIC Trains a binary classifier to predict unplanned ESP failures within 72 hours.
# MAGIC Uses temporal (chronological) train/val/test split to prevent data leakage.
# MAGIC Logs everything to MLflow and registers the champion model.
# MAGIC
# MAGIC **Input:** `esp_ai.gold.esp_features` JOIN `esp_ai.gold.esp_failure_labels`
# MAGIC **Output:** MLflow registered model `esp_failure_72h_model@production`

# COMMAND ----------

import mlflow
import mlflow.xgboost
import xgboost as xgb
import shap
import pandas as pd
import numpy as np
from sklearn.metrics import (
    roc_auc_score, average_precision_score, f1_score,
    precision_score, recall_score, classification_report
)
from pyspark.sql import functions as F

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment("/Shared/ESP_Failure_72h")

FEAT_TNAME  = "esp_ai.gold.esp_features"
LABEL_TNAME = "esp_ai.gold.esp_failure_labels"
MODEL_NAME  = "esp_ai.gold.esp_failure_72h_model"  # UC 3-part name

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
TARGET_COL = "label_failure_72h"

# COMMAND ----------
# MAGIC %md ## 1. Load and join features + labels

# COMMAND ----------

features = spark.read.table(FEAT_TNAME)
labels   = spark.read.table(LABEL_TNAME)

dataset = (
    features
    .join(labels.select("esp_id", "snapshot_ts", TARGET_COL), ["esp_id", "snapshot_ts"], "inner")
    .select(["esp_id", "snapshot_ts"] + FEATURE_COLS + [TARGET_COL])
    .orderBy("snapshot_ts")
    .toPandas()
)

print(f"Dataset shape: {dataset.shape}")
print(f"Positive rate: {dataset[TARGET_COL].mean():.3%}")
dataset["snapshot_ts"] = pd.to_datetime(dataset["snapshot_ts"])

# COMMAND ----------
# MAGIC %md ## 2. Temporal train / val / test split (70 / 15 / 15)

# COMMAND ----------

n = len(dataset)
train_end = int(n * 0.70)
val_end   = int(n * 0.85)

train_df = dataset.iloc[:train_end].copy()
val_df   = dataset.iloc[train_end:val_end].copy()
test_df  = dataset.iloc[val_end:].copy()

print(f"Train: {len(train_df)} rows  ({train_df['snapshot_ts'].min()} → {train_df['snapshot_ts'].max()})")
print(f"Val:   {len(val_df)}   rows  ({val_df['snapshot_ts'].min()} → {val_df['snapshot_ts'].max()})")
print(f"Test:  {len(test_df)}  rows  ({test_df['snapshot_ts'].min()} → {test_df['snapshot_ts'].max()})")

X_train, y_train = train_df[FEATURE_COLS].fillna(-1), train_df[TARGET_COL]
X_val,   y_val   = val_df[FEATURE_COLS].fillna(-1),   val_df[TARGET_COL]
X_test,  y_test  = test_df[FEATURE_COLS].fillna(-1),  test_df[TARGET_COL]

# Class weight to handle imbalance
pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
print(f"scale_pos_weight: {pos_weight:.1f}")

# COMMAND ----------
# MAGIC %md ## 3. XGBoost training with MLflow autolog

# COMMAND ----------

params = {
    "objective":        "binary:logistic",
    "eval_metric":      ["logloss", "auc"],
    "n_estimators":     400,
    "max_depth":        6,
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "scale_pos_weight": pos_weight,
    "tree_method":      "hist",
    "random_state":     42,
    "n_jobs":           -1,
}

with mlflow.start_run(run_name="esp_xgb_train") as run:
    mlflow.log_params(params)
    mlflow.log_param("feature_count", len(FEATURE_COLS))
    mlflow.log_param("train_rows", len(train_df))
    mlflow.log_param("val_rows", len(val_df))
    mlflow.log_param("test_rows", len(test_df))
    mlflow.log_param("positive_rate_train", float(y_train.mean()))

    model = xgb.XGBClassifier(**params, early_stopping_rounds=30, verbosity=0)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=50,
    )

    # ── Evaluation ────────────────────────────────────────────────
    for split_name, X, y in [("val", X_val, y_val), ("test", X_test, y_test)]:
        probs = model.predict_proba(X)[:, 1]
        preds = (probs >= 0.5).astype(int)
        auc   = roc_auc_score(y, probs)
        ap    = average_precision_score(y, probs)
        f1    = f1_score(y, preds, zero_division=0)
        prec  = precision_score(y, preds, zero_division=0)
        rec   = recall_score(y, preds, zero_division=0)

        mlflow.log_metrics({
            f"{split_name}_auc_roc":          auc,
            f"{split_name}_avg_precision":    ap,
            f"{split_name}_f1":               f1,
            f"{split_name}_precision":        prec,
            f"{split_name}_recall":           rec,
        })
        print(f"\n── {split_name.upper()} ──")
        print(f"  AUC-ROC: {auc:.4f}  |  AP: {ap:.4f}  |  F1: {f1:.4f}")
        print(classification_report(y, preds, zero_division=0))

    # ── SHAP feature importance ───────────────────────────────────
    explainer    = shap.TreeExplainer(model)
    shap_values  = explainer.shap_values(X_test)
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    shap_df = pd.DataFrame({
        "feature":    FEATURE_COLS,
        "mean_shap":  mean_abs_shap,
    }).sort_values("mean_shap", ascending=False)

    print("\nTop SHAP features:")
    print(shap_df.head(10).to_string(index=False))
    mlflow.log_dict(shap_df.set_index("feature")["mean_shap"].to_dict(), "shap_importance.json")

    # ── Log model ─────────────────────────────────────────────────
    signature = mlflow.models.infer_signature(X_test, model.predict_proba(X_test)[:, 1])
    mlflow.xgboost.log_model(
        model,
        artifact_path="esp_failure_model",
        registered_model_name=MODEL_NAME,
        signature=signature,
        input_example=X_test.head(3),
    )

    run_id = run.info.run_id
    print(f"\nMLflow run_id: {run_id}")

# COMMAND ----------
# MAGIC %md ## 4. Promote to Production alias

# COMMAND ----------

from mlflow import MlflowClient
client = MlflowClient()

# Get the newly registered version
versions = client.search_model_versions(f"name='{MODEL_NAME}'")
latest   = max(versions, key=lambda v: int(v.version))

client.set_registered_model_alias(MODEL_NAME, "production", latest.version)
print(f"Promoted version {latest.version} to @production alias")
print(f"Model: {MODEL_NAME}@production")
print(f"Run:   {latest.run_id}")
