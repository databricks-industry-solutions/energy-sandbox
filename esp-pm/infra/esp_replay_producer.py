"""
infra/esp_replay_producer.py
-----------------------------
Synthetic ESP telemetry replay producer.
Inserts realistic sensor readings into esp_ai.raw.esp_telemetry_bronze
to simulate live well data for demo purposes.

Usage (on Databricks cluster or locally with DATABRICKS_HOST + TOKEN):
    python esp_replay_producer.py [--esps 5] [--rate-sec 10] [--batch-size 10]
"""

import argparse
import math
import random
import time
import uuid
from datetime import datetime, timezone, timedelta

import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import VolumeType

# ── ESP fleet configuration ────────────────────────────────────────────────────
ESP_IDS = [
    "ESP-WELL-0001", "ESP-WELL-0002", "ESP-WELL-0003",
    "ESP-WELL-0004", "ESP-WELL-0005",
]

# Realistic baseline sensor ranges per ESP class
ESP_PROFILES = {
    "ESP-WELL-0001": dict(pressure_base=2800, current_base=48, vibration_base=0.12, flow_base=1200),
    "ESP-WELL-0002": dict(pressure_base=3100, current_base=52, vibration_base=0.15, flow_base=980),
    "ESP-WELL-0003": dict(pressure_base=2600, current_base=44, vibration_base=0.10, flow_base=1500),
    "ESP-WELL-0004": dict(pressure_base=3400, current_base=56, vibration_base=0.20, flow_base=850),
    "ESP-WELL-0005": dict(pressure_base=2900, current_base=50, vibration_base=0.13, flow_base=1100),
}

# Degradation state per ESP (simulated)
DEGRADATION = {esp_id: 0.0 for esp_id in ESP_IDS}


def sinusoidal_drift(t: float, period: float, amplitude: float) -> float:
    return amplitude * math.sin(2 * math.pi * t / period)


def generate_reading(esp_id: str, ts: datetime, batch_id: int) -> dict:
    profile = ESP_PROFILES.get(esp_id, ESP_PROFILES["ESP-WELL-0001"])
    t = ts.timestamp()
    deg = DEGRADATION[esp_id]

    # Add gradual degradation + diurnal noise
    pressure    = profile["pressure_base"] * (1 - 0.15 * deg) + sinusoidal_drift(t, 86400, 80) + random.gauss(0, 30)
    current     = profile["current_base"]  * (1 + 0.10 * deg) + sinusoidal_drift(t, 3600, 2) + random.gauss(0, 1.5)
    vibration   = profile["vibration_base"]* (1 + 0.40 * deg) + abs(random.gauss(0, 0.02 + 0.05 * deg))
    flow_rate   = profile["flow_base"]     * (1 - 0.20 * deg) + sinusoidal_drift(t, 43200, 50) + random.gauss(0, 20)
    temperature = 85 + 15 * deg + random.gauss(0, 2)
    frequency   = 60.0 + random.gauss(0, 0.3)

    # Status logic
    if deg > 0.85 and random.random() < 0.05:
        status = "TRIP"
    elif deg > 0.6 and random.random() < 0.02:
        status = "IDLE"
    else:
        status = "RUNNING"

    return {
        "esp_id":        esp_id,
        "timestamp":     ts.isoformat(),
        "pressure":      round(max(0, pressure), 2),
        "temperature":   round(temperature, 2),
        "current":       round(max(0, current), 2),
        "frequency":     round(frequency, 2),
        "vibration":     round(max(0, vibration), 4),
        "flow_rate":     round(max(0, flow_rate), 1),
        "status":        status,
        "raw_payload":   None,
        "_ingest_ts":    datetime.now(timezone.utc).isoformat(),
        "_source_topic": "esp-telemetry-replay",
        "_batch_id":     batch_id,
    }


def insert_batch(wc: WorkspaceClient, warehouse_id: str, rows: list[dict]):
    """Insert a batch of rows into the Bronze table via SQL INSERT."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    # Build VALUES clause
    vals = []
    for _, r in df.iterrows():
        vals.append(
            f"('{r.esp_id}', TIMESTAMP '{r.timestamp}', "
            f"{r.pressure}, {r.temperature}, {r.current}, "
            f"{r.frequency}, {r.vibration}, {r.flow_rate}, "
            f"'{r.status}', NULL, "
            f"TIMESTAMP '{r._ingest_ts}', '{r._source_topic}', {r._batch_id})"
        )
    sql = (
        "INSERT INTO esp_ai.raw.esp_telemetry_bronze "
        "(esp_id, timestamp, pressure, temperature, current, frequency, vibration, flow_rate, "
        " status, raw_payload, _ingest_ts, _source_topic, _batch_id) VALUES "
        + ",\n".join(vals)
    )
    result = wc.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="30s",
    )
    if result.status.state.value != "SUCCEEDED":
        print(f"[WARN] Insert failed: {result.status}")


def gradually_degrade(esp_id: str, rate: float = 0.0002):
    """Slowly increment degradation; wrap around after simulated failure."""
    DEGRADATION[esp_id] = min(1.0, DEGRADATION[esp_id] + rate * random.uniform(0.5, 1.5))
    if DEGRADATION[esp_id] > 0.95:
        print(f"[RESET] {esp_id} degradation reset (simulated repair)")
        DEGRADATION[esp_id] = 0.0


def main():
    parser = argparse.ArgumentParser(description="ESP telemetry replay producer")
    parser.add_argument("--esps",       type=int, default=5,  help="Number of ESPs to simulate")
    parser.add_argument("--rate-sec",   type=int, default=10, help="Seconds between batches")
    parser.add_argument("--batch-size", type=int, default=10, help="Readings per batch (per ESP)")
    parser.add_argument("--warehouse",  type=str, default="",  help="SQL warehouse ID (or set DATABRICKS_WAREHOUSE_ID)")
    args = parser.parse_args()

    import os
    wc = WorkspaceClient()
    warehouse_id = args.warehouse or os.getenv("DATABRICKS_WAREHOUSE_ID", "")
    if not warehouse_id:
        # Auto-select first running warehouse
        whs = wc.warehouses.list()
        running = [w for w in whs if w.state and w.state.value == "RUNNING"]
        if not running:
            print("[ERROR] No running SQL warehouse found. Pass --warehouse <id>.")
            return
        warehouse_id = running[0].id
        print(f"[INFO] Using warehouse: {warehouse_id}")

    active_esps = ESP_IDS[:args.esps]
    batch_id = int(time.time())
    print(f"[INFO] Starting replay for {active_esps}  rate={args.rate_sec}s  batch={args.batch_size}")

    while True:
        now = datetime.now(timezone.utc)
        all_rows = []
        for esp_id in active_esps:
            for i in range(args.batch_size):
                ts = now - timedelta(seconds=(args.batch_size - i) * 60)
                all_rows.append(generate_reading(esp_id, ts, batch_id))
            gradually_degrade(esp_id)

        insert_batch(wc, warehouse_id, all_rows)
        print(f"[{now:%H:%M:%S}] Inserted {len(all_rows)} rows  "
              f"degradation={[f'{e}:{DEGRADATION[e]:.2f}' for e in active_esps]}")

        batch_id += 1
        time.sleep(args.rate_sec)


if __name__ == "__main__":
    main()
