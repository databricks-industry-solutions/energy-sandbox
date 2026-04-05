#!/usr/bin/env python3
"""Seed demo data for ESP Predictive Maintenance app."""

import json
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

PROFILE = "YOUR-PROFILE"
WAREHOUSE_ID = "<your-warehouse-id>"
CATALOG = "oil_pump_monitor_catalog"

def execute_sql(statement, label="SQL"):
    """Execute SQL via Databricks REST API."""
    payload = json.dumps({
        "warehouse_id": WAREHOUSE_ID,
        "statement": statement,
        "wait_timeout": "50s",
    })
    result = subprocess.run(
        [
            "databricks", "api", "post", "/api/2.0/sql/statements",
            "--json", payload,
            "--profile", PROFILE,
        ],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"  FAILED ({label}): {result.stderr}")
        return None
    resp = json.loads(result.stdout)
    state = resp.get("status", {}).get("state", "UNKNOWN")
    if state == "SUCCEEDED":
        rows = resp.get("result", {}).get("data_array", [])
        if rows:
            print(f"  OK: {label} => {rows}")
        else:
            print(f"  OK: {label}")
    else:
        error = resp.get("status", {}).get("error", {})
        print(f"  {state} ({label}): {error}")
    return resp


# ── Step 2: Create schemas and tables ─────────────────────────────────

print(f"\n=== Step 2: Create schemas and tables in {CATALOG} ===")

ddl_statements = [
    (f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.raw", "Create schema raw"),
    (f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.gold", "Create schema gold"),
    (f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.ref", "Create schema ref"),
    (f"""CREATE TABLE IF NOT EXISTS {CATALOG}.gold.esp_failure_predictions (
  esp_id STRING NOT NULL,
  prediction_ts TIMESTAMP NOT NULL,
  prediction_date DATE NOT NULL,
  failure_risk_score DOUBLE NOT NULL,
  risk_bucket STRING NOT NULL,
  priority_score DOUBLE,
  top_feature_1 STRING,
  top_feature_2 STRING,
  top_feature_3 STRING,
  top_feature_1_value DOUBLE,
  top_feature_2_value DOUBLE,
  top_feature_3_value DOUBLE,
  model_version STRING,
  model_run_id STRING
) USING DELTA PARTITIONED BY (prediction_date)""", "Create esp_failure_predictions table"),
    (f"""CREATE TABLE IF NOT EXISTS {CATALOG}.raw.esp_telemetry_bronze (
  esp_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  reading_date DATE NOT NULL,
  pressure DOUBLE,
  temperature DOUBLE,
  current DOUBLE,
  frequency DOUBLE,
  vibration DOUBLE,
  flow_rate DOUBLE,
  status STRING,
  raw_payload STRING,
  _ingest_ts TIMESTAMP NOT NULL,
  _source_topic STRING,
  _batch_id BIGINT
) USING DELTA PARTITIONED BY (reading_date)""", "Create esp_telemetry_bronze table"),
]

for sql, label in ddl_statements:
    resp = execute_sql(sql, label)
    if resp is None:
        print("Fatal error, aborting.")
        sys.exit(1)
    state = resp.get("status", {}).get("state", "UNKNOWN")
    if state == "FAILED":
        print(f"  DDL failed for: {label} - continuing to see if table already exists")


# ── Step 3: Insert synthetic predictions ────────────────────────────────

print("\n=== Step 3: Insert synthetic failure predictions ===")

ESP_IDS = [f"ESP-WELL-{i:04d}" for i in range(1, 11)]

RISK_MAP = {
    "ESP-WELL-0001": "HIGH",
    "ESP-WELL-0002": "MEDIUM",
    "ESP-WELL-0003": "LOW",
    "ESP-WELL-0004": "HIGH",
    "ESP-WELL-0005": "MEDIUM",
    "ESP-WELL-0006": "LOW",
    "ESP-WELL-0007": "HIGH",
    "ESP-WELL-0008": "MEDIUM",
    "ESP-WELL-0009": "LOW",
    "ESP-WELL-0010": "LOW",
}

RISK_RANGES = {
    "HIGH":   (0.70, 0.92),
    "MEDIUM": (0.35, 0.65),
    "LOW":    (0.05, 0.28),
}

FEATURES = [
    "vibration_std_1h",
    "current_roc_10m",
    "days_since_last_preventive",
    "gaslock_score",
    "trips_last_7d",
    "pressure_roc_10m",
]

random.seed(42)
now = datetime.now(timezone.utc)

# Build all 240 rows
prediction_rows = []
for esp_id in ESP_IDS:
    bucket = RISK_MAP[esp_id]
    lo, hi = RISK_RANGES[bucket]
    for h in range(24):
        ts = now - timedelta(hours=23 - h)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
        date_str = ts.strftime("%Y-%m-%d")
        score = round(random.uniform(lo, hi), 4)
        priority = round(score * random.uniform(0.85, 1.15), 4)
        feats = random.sample(FEATURES, 3)
        f1_val = round(random.uniform(0.1, 0.9), 4)
        f2_val = round(random.uniform(0.1, 0.9), 4)
        f3_val = round(random.uniform(0.1, 0.9), 4)
        prediction_rows.append(
            f"('{esp_id}', TIMESTAMP '{ts_str}', DATE '{date_str}', {score}, '{bucket}', {priority}, "
            f"'{feats[0]}', '{feats[1]}', '{feats[2]}', {f1_val}, {f2_val}, {f3_val}, "
            f"'v2.1.0', 'run-20260222-seed')"
        )

# Insert in batches of 60
BATCH = 60
total_batches = (len(prediction_rows) + BATCH - 1) // BATCH
for i in range(0, len(prediction_rows), BATCH):
    batch = prediction_rows[i:i + BATCH]
    sql = (
        f"INSERT INTO {CATALOG}.gold.esp_failure_predictions "
        "(esp_id, prediction_ts, prediction_date, failure_risk_score, risk_bucket, priority_score, "
        "top_feature_1, top_feature_2, top_feature_3, "
        "top_feature_1_value, top_feature_2_value, top_feature_3_value, "
        "model_version, model_run_id) VALUES\n"
        + ",\n".join(batch)
    )
    execute_sql(sql, f"Insert predictions batch {i // BATCH + 1}/{total_batches}")

print(f"  Total prediction rows generated: {len(prediction_rows)}")


# ── Step 4: Insert synthetic telemetry ──────────────────────────────────

print("\n=== Step 4: Insert synthetic telemetry ===")

# Base profiles per ESP for realistic variance
BASE_PROFILES = {
    "ESP-WELL-0001": {"pressure": 3200, "temperature": 98, "current": 58, "frequency": 60.1, "vibration": 0.28, "flow_rate": 1100},
    "ESP-WELL-0002": {"pressure": 2900, "temperature": 88, "current": 52, "frequency": 59.8, "vibration": 0.15, "flow_rate": 1350},
    "ESP-WELL-0003": {"pressure": 2700, "temperature": 82, "current": 47, "frequency": 60.0, "vibration": 0.08, "flow_rate": 1450},
    "ESP-WELL-0004": {"pressure": 3400, "temperature": 105, "current": 62, "frequency": 60.5, "vibration": 0.30, "flow_rate": 900},
    "ESP-WELL-0005": {"pressure": 3000, "temperature": 91, "current": 54, "frequency": 59.5, "vibration": 0.18, "flow_rate": 1250},
    "ESP-WELL-0006": {"pressure": 2600, "temperature": 79, "current": 44, "frequency": 60.2, "vibration": 0.07, "flow_rate": 1500},
    "ESP-WELL-0007": {"pressure": 3350, "temperature": 102, "current": 60, "frequency": 61.0, "vibration": 0.25, "flow_rate": 950},
    "ESP-WELL-0008": {"pressure": 2950, "temperature": 90, "current": 51, "frequency": 59.9, "vibration": 0.14, "flow_rate": 1300},
    "ESP-WELL-0009": {"pressure": 2650, "temperature": 80, "current": 45, "frequency": 60.1, "vibration": 0.06, "flow_rate": 1480},
    "ESP-WELL-0010": {"pressure": 2750, "temperature": 84, "current": 48, "frequency": 60.0, "vibration": 0.09, "flow_rate": 1420},
}

telemetry_rows = []
batch_id = int(now.timestamp())

for esp_id in ESP_IDS:
    base = BASE_PROFILES[esp_id]
    for m in range(576):  # 48h * 12 readings/h
        ts = now - timedelta(hours=48) + timedelta(minutes=5 * m)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
        date_str = ts.strftime("%Y-%m-%d")
        ingest_str = (ts + timedelta(seconds=random.randint(1, 10))).strftime("%Y-%m-%dT%H:%M:%S")

        pressure = round(base["pressure"] + random.gauss(0, 50), 1)
        temperature = round(base["temperature"] + random.gauss(0, 3), 1)
        current = round(base["current"] + random.gauss(0, 2), 2)
        frequency = round(base["frequency"] + random.gauss(0, 0.3), 2)
        vibration = round(max(0.01, base["vibration"] + random.gauss(0, 0.03)), 4)
        flow_rate = round(base["flow_rate"] + random.gauss(0, 40), 1)
        status = "IDLE" if random.random() < 0.03 else "RUNNING"

        telemetry_rows.append(
            f"('{esp_id}', TIMESTAMP '{ts_str}', DATE '{date_str}', {pressure}, {temperature}, {current}, "
            f"{frequency}, {vibration}, {flow_rate}, '{status}', NULL, "
            f"TIMESTAMP '{ingest_str}', 'iot/esp/{esp_id}', {batch_id})"
        )

print(f"  Generated {len(telemetry_rows)} telemetry rows, inserting in batches of 100...")

BATCH = 100
total_batches = (len(telemetry_rows) + BATCH - 1) // BATCH
for i in range(0, len(telemetry_rows), BATCH):
    batch = telemetry_rows[i:i + BATCH]
    sql = (
        f"INSERT INTO {CATALOG}.raw.esp_telemetry_bronze "
        "(esp_id, timestamp, reading_date, pressure, temperature, current, frequency, vibration, "
        "flow_rate, status, raw_payload, _ingest_ts, _source_topic, _batch_id) VALUES\n"
        + ",\n".join(batch)
    )
    batch_num = i // BATCH + 1
    execute_sql(sql, f"Insert telemetry batch {batch_num}/{total_batches}")

print(f"  Total telemetry rows generated: {len(telemetry_rows)}")


# ── Verify counts ───────────────────────────────────────────────────────

print("\n=== Verification ===")
execute_sql(f"SELECT COUNT(*) AS cnt FROM {CATALOG}.gold.esp_failure_predictions", "Prediction row count")
execute_sql(f"SELECT COUNT(*) AS cnt FROM {CATALOG}.raw.esp_telemetry_bronze", "Telemetry row count")
execute_sql(f"SELECT risk_bucket, COUNT(*) AS cnt FROM {CATALOG}.gold.esp_failure_predictions GROUP BY risk_bucket ORDER BY risk_bucket", "Risk bucket distribution")

print("\nDone!")
