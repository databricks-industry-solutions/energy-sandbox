"""
03_train_rop_models.py
──────────────────────
Train an XGBoost ROP regressor on MSEEL Gold features.

Steps:
  1. Load drilling_demo_gold.rop_features_train → Pandas
  2. Impute, scale, and split (80 / 20 stratified by well)
  3. Train XGBoost with cross-validation
  4. Log metrics + artefacts to MLflow
  5. Register model as rop_xgb_mseel, promote to Production
  6. Stub rule-based hazard classifier (pending labelled dataset)

Dependencies (already on Databricks ML Runtime):
    xgboost, mlflow, scikit-learn
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import mlflow
import mlflow.xgboost
import mlflow.sklearn
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from pyspark.sql import SparkSession

warnings.filterwarnings("ignore")

# ── Configuration ─────────────────────────────────────────────
GOLD_FEAT_TBL  = os.getenv("GOLD_FEAT_TBL",  "drilling_demo_gold.rop_features_train")
MLFLOW_EXP     = os.getenv("MLFLOW_EXP",      "/Shared/ROP_Prediction_MSEEL")
MODEL_NAME     = os.getenv("MLFLOW_MODEL_NAME","rop_xgb_mseel")
TEST_SIZE      = float(os.getenv("TEST_SIZE",  "0.20"))
RANDOM_STATE   = int(os.getenv("RANDOM_STATE", "42"))

FEATURES = [
    "wob", "rpm", "torque", "spp", "flow", "hookload",
    "mse", "d_rop_dt", "d_torque_dt", "d_spp_dt",
    "md", "tvd",
]
TARGET = "label_rop"

# Hazard thresholds (rule-based stub)
ROP_GAP_THRESHOLD  = float(os.getenv("ROP_GAP_THRESHOLD",  "20.0"))   # ft/hr
MSE_HIGH_THRESHOLD = float(os.getenv("MSE_HIGH_THRESHOLD", "150000.0"))# psi
MSE_OPT_THRESHOLD  = float(os.getenv("MSE_OPT_THRESHOLD",  "50000.0")) # psi

XGB_PARAMS = {
    "n_estimators":      int(os.getenv("XGB_N_ESTIMATORS", "400")),
    "max_depth":         int(os.getenv("XGB_MAX_DEPTH",     "6")),
    "learning_rate":     float(os.getenv("XGB_LR",          "0.05")),
    "subsample":         float(os.getenv("XGB_SUBSAMPLE",   "0.8")),
    "colsample_bytree":  float(os.getenv("XGB_COLSAMPLE",   "0.8")),
    "reg_alpha":         float(os.getenv("XGB_ALPHA",        "0.1")),
    "reg_lambda":        float(os.getenv("XGB_LAMBDA",       "1.0")),
    "random_state":      RANDOM_STATE,
    "n_jobs":            -1,
    "tree_method":       "hist",    # GPU-compatible when using GPU cluster
}


def load_features(spark: SparkSession) -> pd.DataFrame:
    print(f"Loading features from {GOLD_FEAT_TBL} …")
    df = spark.table(GOLD_FEAT_TBL).toPandas()
    print(f"  Shape: {df.shape}  wells: {df['well_id'].unique().tolist()}")
    return df


def split_data(df: pd.DataFrame):
    """Stratified split by well_id to ensure test set contains all wells."""
    X = df[FEATURES].copy()
    y = df[TARGET].copy()

    # Use well_id as stratification group when multiple wells exist
    stratify = df["well_id"] if df["well_id"].nunique() > 1 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=stratify,
    )
    print(f"  Train: {len(X_train):,}  Test: {len(X_test):,}")
    return X_train, X_test, y_train, y_test


def build_pipeline():
    """Preprocessing → XGBoost pipeline."""
    try:
        import xgboost as xgb
        estimator = xgb.XGBRegressor(**XGB_PARAMS)
        print("  Using XGBoost")
    except ImportError:
        import lightgbm as lgb
        estimator = lgb.LGBMRegressor(
            n_estimators=XGB_PARAMS["n_estimators"],
            max_depth=XGB_PARAMS["max_depth"],
            learning_rate=XGB_PARAMS["learning_rate"],
            subsample=XGB_PARAMS["subsample"],
            random_state=RANDOM_STATE,
        )
        print("  XGBoost not available — using LightGBM")

    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("model",   estimator),
    ])
    return pipe


def evaluate(model, X_test, y_test) -> dict:
    y_pred = model.predict(X_test)
    rmse   = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae    = float(mean_absolute_error(y_test, y_pred))
    r2     = float(r2_score(y_test, y_pred))
    # Percent within ±10 ft/hr
    within10 = float(np.mean(np.abs(y_pred - y_test) <= 10.0))
    print(f"  RMSE={rmse:.3f}  MAE={mae:.3f}  R²={r2:.4f}  Within±10={within10:.2%}")
    return {"rmse": rmse, "mae": mae, "r2": r2, "within_10_pct": within10}


def feature_importance_dict(model, feature_names: list) -> dict:
    """Extract feature importances from the final estimator."""
    try:
        imp = model.named_steps["model"].feature_importances_
        return dict(sorted(zip(feature_names, imp.tolist()), key=lambda x: -x[1]))
    except AttributeError:
        return {}


def train_and_register(spark: SparkSession):
    df = load_features(spark)

    mlflow.set_experiment(MLFLOW_EXP)
    client = MlflowClient()

    with mlflow.start_run(run_name="rop_xgb_train") as run:
        run_id = run.info.run_id
        print(f"\nMLflow run: {run_id}")

        X_train, X_test, y_train, y_test = split_data(df)

        pipe = build_pipeline()
        print("  Training …")
        pipe.fit(X_train, y_train)

        metrics = evaluate(pipe, X_test, y_test)

        # Log params + metrics
        mlflow.log_params({
            "n_features":   len(FEATURES),
            "n_train":      len(X_train),
            "n_test":       len(X_test),
            "bit_features": ",".join(FEATURES),
            **{f"xgb_{k}": v for k, v in XGB_PARAMS.items() if k not in ("n_jobs",)},
        })
        mlflow.log_metrics(metrics)

        # Feature importance artifact
        fi = feature_importance_dict(pipe, FEATURES)
        mlflow.log_dict(fi, "feature_importance.json")
        print(f"  Top features: {list(fi.keys())[:5]}")

        # Infer signature
        sample_input = X_train.head(5)
        sample_preds = pd.DataFrame(pipe.predict(sample_input), columns=["rop_pred"])
        sig = infer_signature(sample_input, sample_preds)

        # Log model (sklearn-pipeline wrapping xgb)
        model_info = mlflow.sklearn.log_model(
            pipe,
            artifact_path="rop_model",
            signature=sig,
            input_example=sample_input,
            registered_model_name=MODEL_NAME,
        )
        print(f"  Model logged: {model_info.model_uri}")

        # Promote to Production
        model_versions = client.search_model_versions(f"name='{MODEL_NAME}'")
        latest_ver = max(int(mv.version) for mv in model_versions)
        client.transition_model_version_stage(
            name=MODEL_NAME,
            version=str(latest_ver),
            stage="Production",
            archive_existing_versions=True,
        )
        print(f"  ✓ {MODEL_NAME} v{latest_ver} → Production")

        # Persist metrics to Lakebase model_versions table if available
        _try_log_to_lakebase(MODEL_NAME, str(latest_ver), "Production", metrics, FEATURES)

    return run_id, metrics


def _try_log_to_lakebase(model_name, version, stage, metrics, features):
    """Mirror model metadata to Lakebase for fast app reads (best-effort)."""
    try:
        from sqlalchemy import text
        from app.db import get_engine
        eng = get_engine()
        with eng.begin() as conn:
            conn.execute(text("""
                INSERT INTO model_versions (model_name, version, stage, rmse, r2, feature_list)
                VALUES (:mn, :v, :s, :rmse, :r2, :fl)
                ON CONFLICT (model_name, version) DO UPDATE
                  SET stage=EXCLUDED.stage, rmse=EXCLUDED.rmse, r2=EXCLUDED.r2
            """), {
                "mn": model_name, "v": version, "s": stage,
                "rmse": metrics["rmse"], "r2": metrics["r2"],
                "fl": json.dumps(features),
            })
        print("  ✓ Model metadata mirrored to Lakebase")
    except Exception as e:
        print(f"  ⚠ Could not mirror to Lakebase (non-fatal): {e}")


def stub_hazard_classifier(df: pd.DataFrame):
    """
    Rule-based hazard labeller — placeholder until a labelled dataset exists.

    Hazard categories:
      INEFFICIENT_DRILLING : ROP significantly below MSE-optimal (high MSE + low ROP)
      HIGH_MSE             : MSE above hard threshold (possible bit balling / vibration)
      OPTIMAL              : drilling near optimum (low MSE, acceptable ROP)
      NORMAL               : all other states

    A future version should replace these rules with a multi-class classifier
    trained on manually labelled or physics-labelled events.
    """
    def classify(row):
        if pd.isna(row.get("mse")) or pd.isna(row.get("label_rop")):
            return "UNKNOWN"
        if row["mse"] > MSE_HIGH_THRESHOLD:
            return "HIGH_MSE"
        if row["mse"] > MSE_HIGH_THRESHOLD * 0.6 and row["label_rop"] < 10.0:
            return "INEFFICIENT_DRILLING"
        if row["mse"] < MSE_OPT_THRESHOLD and row["label_rop"] >= 10.0:
            return "OPTIMAL"
        return "NORMAL"

    df["hazard_label"] = df.apply(classify, axis=1)
    dist = df["hazard_label"].value_counts().to_dict()
    print(f"  Hazard label distribution: {dist}")
    return df


def run():
    spark = SparkSession.builder.getOrCreate()

    print("=" * 60)
    print(f"ROP Model Training — {MODEL_NAME}")
    print(f"Features: {FEATURES}")
    print("=" * 60)

    run_id, metrics = train_and_register(spark)

    # Demonstrate hazard labeller on training data
    print("\n── Hazard Classifier Stub ───────────────────")
    df = spark.table(GOLD_FEAT_TBL).limit(5000).toPandas()
    df = stub_hazard_classifier(df)

    print("\n✅ Training complete")
    print(f"   Run ID : {run_id}")
    print(f"   Metrics: RMSE={metrics['rmse']:.3f}  R²={metrics['r2']:.4f}")
    print(f"   Model  : {MODEL_NAME} (Production)")


if __name__ == "__main__":
    run()
