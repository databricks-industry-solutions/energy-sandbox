# Databricks notebook source
# MAGIC %md
# MAGIC # ESP Feature Engineering Pipeline
# MAGIC
# MAGIC Computes rolling telemetry statistics, physics-derived scores, and SAP maintenance
# MAGIC features for every active ESP. Writes results to `esp_ai.gold.esp_features`.
# MAGIC
# MAGIC **Schedule:** Hourly (via Databricks Jobs)
# MAGIC **Input:** `esp_ai.raw.esp_telemetry_bronze`, `sap_curated.pm.*`, `sap_curated.mm.*`
# MAGIC **Output:** `esp_ai.gold.esp_features`

# COMMAND ----------

from pyspark.sql import Window, functions as F
from pyspark.sql.types import BooleanType
from datetime import datetime, timezone
import mlflow

CATALOG   = "esp_ai"
RAW_TNAME = f"{CATALOG}.raw.esp_telemetry_bronze"
FEAT_TNAME = f"{CATALOG}.gold.esp_features"
JOB_VERSION = spark.conf.get("spark.databricks.clusterUsageTags.runId", "local")

print(f"Feature engineering run  |  version={JOB_VERSION}  |  ts={datetime.now(timezone.utc)}")

# COMMAND ----------
# MAGIC %md ## 1. Load raw telemetry (trailing 7-day window for rolling stats)

# COMMAND ----------

bronze = (
    spark.read.table(RAW_TNAME)
    .filter(F.col("timestamp") >= F.current_timestamp() - F.expr("INTERVAL 7 DAYS"))
    .filter(F.col("status") != "SHUTDOWN")
)

# COMMAND ----------
# MAGIC %md ## 2. Rolling telemetry statistics

# COMMAND ----------

# Window specs
w1h  = Window.partitionBy("esp_id").orderBy(F.col("timestamp").cast("long")).rangeBetween(-3600, 0)
w24h = Window.partitionBy("esp_id").orderBy(F.col("timestamp").cast("long")).rangeBetween(-86400, 0)
w10m = Window.partitionBy("esp_id").orderBy(F.col("timestamp").cast("long")).rangeBetween(-600, 0)
w7d  = Window.partitionBy("esp_id").orderBy(F.col("timestamp").cast("long")).rangeBetween(-604800, 0)

telemetry_stats = bronze.select(
    "esp_id",
    "timestamp",
    "current",
    "pressure",
    "vibration",
    "flow_rate",
    "frequency",
    "status",
    # Current 1h / 24h
    F.avg("current").over(w1h).alias("current_mean_1h"),
    F.stddev("current").over(w1h).alias("current_std_1h"),
    F.avg("current").over(w24h).alias("current_mean_24h"),
    F.stddev("current").over(w24h).alias("current_std_24h"),
    # Current rate of change (10m)
    (
        (F.last("current").over(w10m) - F.first("current").over(w10m)) /
        F.greatest(F.lit(1), F.count("current").over(w10m) - 1)
    ).alias("current_roc_10m"),
    # Pressure 1h / 10m
    F.avg("pressure").over(w1h).alias("pressure_mean_1h"),
    F.stddev("pressure").over(w1h).alias("pressure_std_1h"),
    (
        (F.last("pressure").over(w10m) - F.first("pressure").over(w10m)) /
        F.greatest(F.lit(1), F.count("pressure").over(w10m) - 1)
    ).alias("pressure_roc_10m"),
    # Vibration
    F.stddev("vibration").over(w1h).alias("vibration_std_1h"),
    (
        (F.last("vibration").over(w10m) - F.first("vibration").over(w10m)) /
        F.greatest(F.lit(1), F.count("vibration").over(w10m) - 1)
    ).alias("vibration_roc_10m"),
)

# COMMAND ----------
# MAGIC %md ## 3. Operational counters (starts, trips, alarms)

# COMMAND ----------

w24h_count = Window.partitionBy("esp_id").orderBy(F.col("timestamp").cast("long")).rangeBetween(-86400, 0)
w7d_count  = Window.partitionBy("esp_id").orderBy(F.col("timestamp").cast("long")).rangeBetween(-604800, 0)

prev_status = F.lag("status").over(Window.partitionBy("esp_id").orderBy("timestamp"))

operational = bronze.withColumn("prev_status", prev_status).select(
    "esp_id",
    "timestamp",
    # IDLE→RUNNING transitions (motor starts)
    F.sum(
        F.when((F.col("status") == "RUNNING") & (F.col("prev_status") == "IDLE"), 1).otherwise(0)
    ).over(w24h_count).alias("starts_last_24h"),
    # TRIP events in last 7d
    F.sum(
        F.when(F.col("status") == "TRIP", 1).otherwise(0)
    ).over(w7d_count).alias("trips_last_7d"),
    # Minor alarms (non-trip anomalous status codes) in 7d — extend pattern as needed
    F.sum(
        F.when(F.col("status").isin("IDLE") & (F.col("prev_status") == "RUNNING"), 1).otherwise(0)
    ).over(w7d_count).alias("minor_alarms_last_7d"),
)

# COMMAND ----------
# MAGIC %md ## 4. Physics-derived scores

# COMMAND ----------

# Gaslock score: high pressure_roc (negative, dropping) + low flow + high current
# Sigmoid-based composite [0..1]
gaslock_raw = (
    -F.col("pressure_roc_10m") / F.lit(5.0)      # pressure dropping fast → positive
    + F.when(F.col("flow_rate") < 500, 1.0).otherwise(0.0)   # low flow
    + F.when(F.col("current_mean_1h") > 60, 1.0).otherwise(0.0)  # overcurrent
)
gaslock_score = F.lit(1.0) / (F.lit(1.0) + F.exp(-gaslock_raw / F.lit(3.0)))

NAMEPLATE_FLA = 55.0   # amperes — adjust per equipment class
NAMEPLATE_FREQ_LO = 45.0
NAMEPLATE_FREQ_HI = 65.0

physics = telemetry_stats.withColumn("gaslock_raw", gaslock_raw) \
    .withColumn("gaslock_score",
        F.lit(1.0) / (F.lit(1.0) + F.exp(-F.col("gaslock_raw") / F.lit(3.0)))
    ) \
    .withColumn("load_factor",
        F.col("current_mean_1h") / F.lit(NAMEPLATE_FLA)
    ) \
    .withColumn("operating_near_limits_flag",
        (
            (F.col("current_mean_1h") < NAMEPLATE_FLA * 0.9) |
            (F.col("current_mean_1h") > NAMEPLATE_FLA * 1.1) |
            (F.col("frequency") < NAMEPLATE_FREQ_LO) |
            (F.col("frequency") > NAMEPLATE_FREQ_HI)
        ).cast(BooleanType())
    )

# COMMAND ----------
# MAGIC %md ## 5. SAP maintenance features

# COMMAND ----------

sap_summary = spark.read.table("sap_curated.pm.equipment_maintenance_summary")
eq_map      = spark.read.table("esp_ai.ref.esp_equipment_map") \
                   .select("esp_id", "equipment_id")

# Callbacks: orders created within 30d of the last repair — using SAP orders
orders = spark.read.table("sap_curated.pm.orders") \
              .select("equipment_id", "created_ts", "actual_end_ts", "order_type", "actual_cost")

# MTBF from breakdown notifications
notifs = spark.read.table("sap_curated.pm.notifications") \
              .filter(F.col("breakdown_indicator") == True) \
              .select("equipment_id", "failure_start_ts") \
              .orderBy("equipment_id", "failure_start_ts")

w_eq = Window.partitionBy("equipment_id").orderBy("failure_start_ts")
notifs_mtbf = notifs \
    .withColumn("prev_ts", F.lag("failure_start_ts").over(w_eq)) \
    .withColumn("hours_between",
        (F.col("failure_start_ts").cast("long") - F.col("prev_ts").cast("long")) / 3600.0
    ) \
    .groupBy("equipment_id") \
    .agg(F.avg("hours_between").alias("average_mtbf_hours"))

# Repeat failures same cause (180d)
repeat_failures = spark.read.table("sap_curated.pm.notifications") \
    .filter(F.col("failure_start_ts") >= F.current_timestamp() - F.expr("INTERVAL 180 DAYS")) \
    .groupBy("equipment_id", "cause_code") \
    .agg(F.count("*").alias("cnt")) \
    .groupBy("equipment_id") \
    .agg(F.max("cnt").alias("repeat_failure_same_cause_180d"))

sap_features = eq_map \
    .join(sap_summary, "equipment_id", "left") \
    .join(notifs_mtbf, "equipment_id", "left") \
    .join(repeat_failures, "equipment_id", "left") \
    .withColumn("days_since_last_preventive",
        (F.current_timestamp().cast("long") - F.col("last_preventive_ts").cast("long")) / 86400.0
    ) \
    .withColumn("days_since_last_corrective",
        (F.current_timestamp().cast("long") - F.col("last_corrective_ts").cast("long")) / 86400.0
    ) \
    .withColumn("sum_actual_cost_365d", F.col("sum_actual_cost_365d").cast("double")) \
    .withColumn("order_count_365d", F.col("order_count_365d").cast("int")) \
    .select(
        "esp_id",
        "days_since_last_preventive",
        "days_since_last_corrective",
        "sum_actual_cost_365d",
        "order_count_365d",
        "average_mtbf_hours",
        F.coalesce("repeat_failure_same_cause_180d", F.lit(0)).alias("repeat_failure_same_cause_180d"),
    )

# COMMAND ----------
# MAGIC %md ## 6. Critical parts availability

# COMMAND ----------

critical_stock = spark.read.table("sap_curated.mm.critical_materials") \
    .groupBy("plant") \
    .agg(
        (F.sum(F.when(F.col("in_stock"), 1).otherwise(0)) == F.count("*")).alias("critical_parts_available"),
        F.sum(F.when(F.col("in_stock"), 1).otherwise(0)).alias("num_critical_parts_available"),
    )

eq_map_plant = spark.read.table("esp_ai.ref.esp_equipment_map") \
    .select("esp_id", "plant") \
    .join(critical_stock, "plant", "left")

# COMMAND ----------
# MAGIC %md ## 7. Snapshot timestamp and final assembly

# COMMAND ----------

snapshot_ts = datetime.now(timezone.utc)

# Take latest row per ESP from physics stats
latest_w = Window.partitionBy("esp_id").orderBy(F.col("timestamp").desc())
latest_physics = (
    physics
    .join(operational.select("esp_id", "timestamp", "starts_last_24h", "trips_last_7d", "minor_alarms_last_7d"),
          ["esp_id", "timestamp"], "left")
    .withColumn("rn", F.row_number().over(latest_w))
    .filter(F.col("rn") == 1)
    .drop("rn")
)

features_df = (
    latest_physics
    .join(sap_features, "esp_id", "left")
    .join(eq_map_plant.select("esp_id", "critical_parts_available", "num_critical_parts_available"),
          "esp_id", "left")
    .withColumn("snapshot_ts", F.lit(snapshot_ts.isoformat()).cast("timestamp"))
    .withColumn("feature_job_version", F.lit(JOB_VERSION))
    .select(
        "esp_id", "snapshot_ts",
        "current_mean_1h", "current_std_1h", "current_mean_24h", "current_std_24h", "current_roc_10m",
        "pressure_mean_1h", "pressure_std_1h", "pressure_roc_10m",
        "vibration_std_1h", "vibration_roc_10m",
        F.coalesce("starts_last_24h", F.lit(0)).alias("starts_last_24h"),
        F.coalesce("trips_last_7d", F.lit(0)).alias("trips_last_7d"),
        F.coalesce("minor_alarms_last_7d", F.lit(0)).alias("minor_alarms_last_7d"),
        "gaslock_score", "load_factor", "operating_near_limits_flag",
        "days_since_last_preventive", "days_since_last_corrective",
        F.lit(None).cast("double").alias("variance_from_recommended_interval"),
        F.lit(None).cast("int").alias("callbacks_30d"),
        "repeat_failure_same_cause_180d",
        F.when(F.col("order_count_365d") > 0,
               F.col("order_count_365d") / F.lit(8760.0)
        ).otherwise(F.lit(None)).alias("orders_per_runtime_hour_365d"),
        "average_mtbf_hours",
        "sum_actual_cost_365d",
        F.lit(None).cast("double").alias("sum_parts_cost_365d"),
        "critical_parts_available", "num_critical_parts_available",
        "feature_job_version",
    )
)

# COMMAND ----------
# MAGIC %md ## 8. Write to Gold feature table

# COMMAND ----------

(
    features_df.write
    .format("delta")
    .mode("append")
    .saveAsTable(FEAT_TNAME)
)

print(f"Written {features_df.count()} feature rows to {FEAT_TNAME}")
display(features_df.limit(5))
