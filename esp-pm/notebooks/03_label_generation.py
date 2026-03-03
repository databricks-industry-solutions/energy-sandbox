# Databricks notebook source
# MAGIC %md
# MAGIC # ESP Failure Label Generation
# MAGIC
# MAGIC Derives binary 72-hour failure labels from SAP PM breakdown notifications.
# MAGIC For each feature snapshot, label = 1 if an unplanned failure begins within
# MAGIC 72 hours of snapshot_ts, else 0.
# MAGIC
# MAGIC **Schedule:** Daily (can be re-run historically)
# MAGIC **Input:** `esp_ai.gold.esp_features`, `sap_curated.pm.notifications`, `esp_ai.ref.esp_equipment_map`
# MAGIC **Output:** `esp_ai.gold.esp_failure_labels`

# COMMAND ----------

from pyspark.sql import functions as F
from datetime import datetime, timezone

FEAT_TNAME   = "esp_ai.gold.esp_features"
NOTIF_TNAME  = "sap_curated.pm.notifications"
LABEL_TNAME  = "esp_ai.gold.esp_failure_labels"
LABEL_VERSION = spark.conf.get("spark.databricks.clusterUsageTags.runId", "local")
HORIZON_H    = 72   # hours

print(f"Label generation  |  horizon={HORIZON_H}h  |  version={LABEL_VERSION}")

# COMMAND ----------
# MAGIC %md ## 1. Load feature snapshots

# COMMAND ----------

features = spark.read.table(FEAT_TNAME).select("esp_id", "snapshot_ts")
print(f"Feature snapshots: {features.count()}")

# COMMAND ----------
# MAGIC %md ## 2. Load breakdown notifications from SAP

# COMMAND ----------

eq_map = spark.read.table("esp_ai.ref.esp_equipment_map").select("esp_id", "equipment_id")

breakdowns = (
    spark.read.table(NOTIF_TNAME)
    .filter(F.col("breakdown_indicator") == True)
    .select("equipment_id", "failure_start_ts", "failure_end_ts", "notif_type", "cause_code", "notification_id")
    .join(eq_map, "equipment_id", "inner")
    .select("esp_id", "failure_start_ts", "failure_end_ts", "notif_type", "cause_code", "notification_id")
)

print(f"Breakdown notifications: {breakdowns.count()}")

# COMMAND ----------
# MAGIC %md ## 3. Classify failure type from cause codes

# COMMAND ----------

# Failure type mapping (extend to match your SAP cause code taxonomy)
# cause_code prefixes: EL=Electrical, HY=Hydraulic, ME=Mechanical, GL=Gas Lock
failure_type_expr = (
    F.when(F.col("cause_code").startswith("EL") | F.col("cause_code").startswith("INS"), "ELECTRICAL")
     .when(F.col("cause_code").startswith("HY") | F.col("cause_code").startswith("PU"), "HYDRAULIC")
     .when(F.col("cause_code").startswith("ME") | F.col("cause_code").startswith("BE"), "MECHANICAL")
     .when(F.col("cause_code").startswith("GL") | F.col("cause_code").startswith("GAS"), "GAS_LOCK")
     .otherwise("OTHER")
)

breakdowns = breakdowns.withColumn("failure_type", failure_type_expr)

# COMMAND ----------
# MAGIC %md ## 4. Join features with breakdowns on 72h horizon

# COMMAND ----------

# Cross-join on esp_id, then filter by time window
labeled = (
    features.alias("f")
    .join(breakdowns.alias("b"), "esp_id", "left")
    .withColumn("within_horizon",
        (F.col("b.failure_start_ts") >= F.col("f.snapshot_ts")) &
        (F.col("b.failure_start_ts") <= F.col("f.snapshot_ts") + F.expr(f"INTERVAL {HORIZON_H} HOURS"))
    )
)

# For each (esp_id, snapshot_ts) find the earliest failure within horizon
earliest_failure = (
    labeled
    .filter(F.col("within_horizon") == True)
    .groupBy("f.esp_id", "f.snapshot_ts")
    .agg(
        F.min("b.failure_start_ts").alias("failure_start_ts"),
        F.first("b.failure_end_ts").alias("failure_end_ts"),
        F.first("b.failure_type").alias("failure_type"),
        F.first("b.notification_id").alias("sap_notification_id"),
    )
    .withColumn("label_failure_72h", F.lit(1))
)

# All snapshots with label=0 (no failure within horizon)
all_snapshots = features.withColumnRenamed("esp_id", "esp_id").withColumnRenamed("snapshot_ts", "snapshot_ts")

labels = (
    all_snapshots
    .join(earliest_failure, ["esp_id", "snapshot_ts"], "left")
    .withColumn("label_failure_72h",
        F.coalesce(F.col("label_failure_72h"), F.lit(0))
    )
    .withColumn("label_version", F.lit(LABEL_VERSION))
    .select(
        "esp_id",
        "snapshot_ts",
        "label_failure_72h",
        "failure_type",
        "failure_start_ts",
        "failure_end_ts",
        "sap_notification_id",
        "label_version",
    )
)

# COMMAND ----------
# MAGIC %md ## 5. Label distribution check

# COMMAND ----------

label_dist = labels.groupBy("label_failure_72h").count()
display(label_dist)

pos_rate = labels.filter(F.col("label_failure_72h") == 1).count() / labels.count()
print(f"Positive rate (failure within 72h): {pos_rate:.3%}")

failure_type_dist = labels.filter(F.col("label_failure_72h") == 1).groupBy("failure_type").count()
display(failure_type_dist)

# COMMAND ----------
# MAGIC %md ## 6. Write labels (merge/append — avoid duplicating existing)

# COMMAND ----------

# Use MERGE to upsert: update if exists, insert if new
labels.createOrReplaceTempView("new_labels")

spark.sql(f"""
MERGE INTO {LABEL_TNAME} AS target
USING new_labels AS source
  ON target.esp_id = source.esp_id AND target.snapshot_ts = source.snapshot_ts
WHEN MATCHED THEN
  UPDATE SET
    label_failure_72h   = source.label_failure_72h,
    failure_type        = source.failure_type,
    failure_start_ts    = source.failure_start_ts,
    failure_end_ts      = source.failure_end_ts,
    sap_notification_id = source.sap_notification_id,
    label_version       = source.label_version
WHEN NOT MATCHED THEN
  INSERT *
""")

print(f"Label upsert complete. Total rows: {spark.read.table(LABEL_TNAME).count()}")
