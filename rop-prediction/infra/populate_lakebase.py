#!/usr/bin/env python3
"""
populate_lakebase.py
====================
Connects to the drilling-demo-lakebase Lakebase instance, creates the
drilling_demo_app database (if needed), creates the schema tables,
generates realistic synthetic MSEEL drilling data, and populates
the predictions, alerts, wells, and model_versions tables.

Prerequisites:
  - asyncpg installed (pip install asyncpg)
  - Databricks CLI configured with profile fevm-oil-pump-monitor
  - Lakebase instance 'drilling-demo-lakebase' in AVAILABLE state

Usage:
  python3 infra/populate_lakebase.py
"""

import asyncio
import json
import math
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import asyncpg
import numpy as np

# ── Configuration ────────────────────────────────────────────────
LAKEBASE_HOST = "instance-f82f5f93-8ed2-4ebf-943c-64fca39d2970.database.cloud.databricks.com"
LAKEBASE_PORT = 5432
DATABASE_NAME = "drilling_demo_app"
ADMIN_DATABASE = "databricks_postgres"  # Connect here first to create the app database
APP_SERVICE_PRINCIPAL = "app-4he34r rop-prediction"

# Wells configuration
WELLS = [
    {"well_id": "MIP_3H", "name": "MSEEL MIP-3H Horizontal"},
    {"well_id": "MIP_4H", "name": "MSEEL MIP-4H Horizontal"},
]

# Data generation parameters
ROWS_PER_WELL = 10000
SAMPLE_INTERVAL_SEC = 1  # 1-second sampling


def get_oauth_token():
    """Get OAuth token from Databricks CLI."""
    result = subprocess.run(
        ["databricks", "auth", "token", "--profile=fe-vm-oil-pump-monitor"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get token: {result.stderr}")
    data = json.loads(result.stdout)
    return data["access_token"]


def generate_synthetic_drilling_data(well_id: str, n_rows: int) -> list[dict]:
    """
    Generate realistic synthetic MSEEL drilling data for one well.

    The data simulates lateral drilling through Marcellus shale with:
    - Gradual depth progression
    - Varying formation hardness zones (soft/medium/hard)
    - Realistic parameter correlations
    - Anomaly periods (high MSE, stuck pipe events)
    """
    np.random.seed(hash(well_id) % (2**31))
    random.seed(hash(well_id) % (2**31))

    # Time base: start ~3 hours ago so the "last 30 min" window has data
    # Actually, the app queries relative to NOW, so we place most data
    # within the last 2 hours to ensure the time window catches it
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(seconds=n_rows * SAMPLE_INTERVAL_SEC)

    # Depth progression: lateral section 5000 ft to ~15000 ft
    md_start = 5000.0 + random.uniform(0, 500)
    md_end = md_start + random.uniform(8000, 10000)
    md_values = np.linspace(md_start, md_end, n_rows)

    # TVD: relatively flat in lateral section (7000-8500 ft)
    tvd_base = 7500 + random.uniform(-300, 300)
    tvd_values = tvd_base + np.sin(np.linspace(0, 4 * np.pi, n_rows)) * 200 + \
                 np.random.normal(0, 15, n_rows)
    tvd_values = np.clip(tvd_values, 7000, 8500)

    # Formation hardness zones (affects ROP, WOB, Torque)
    # Create 5-8 zones of varying hardness
    n_zones = random.randint(5, 8)
    zone_boundaries = sorted(np.random.choice(n_rows, n_zones - 1, replace=False))
    zone_boundaries = [0] + list(zone_boundaries) + [n_rows]
    zone_hardness = [random.choice(["soft", "medium", "hard"]) for _ in range(n_zones)]

    hardness_map = np.zeros(n_rows)
    for i in range(n_zones):
        start_idx = zone_boundaries[i]
        end_idx = zone_boundaries[i + 1]
        if zone_hardness[i] == "soft":
            hardness_map[start_idx:end_idx] = 0.3
        elif zone_hardness[i] == "medium":
            hardness_map[start_idx:end_idx] = 0.6
        else:  # hard
            hardness_map[start_idx:end_idx] = 1.0

    # Smooth the hardness transitions
    kernel_size = 50
    kernel = np.ones(kernel_size) / kernel_size
    hardness_smooth = np.convolve(hardness_map, kernel, mode="same")

    # Anomaly periods (stuck pipe, vibration, high MSE)
    n_anomalies = random.randint(8, 15)
    anomaly_starts = sorted(random.sample(range(200, n_rows - 200), n_anomalies))
    anomaly_lengths = [random.randint(30, 150) for _ in range(n_anomalies)]
    anomaly_types = [random.choice(["high_mse", "stuck_pipe", "vibration", "inefficient"])
                     for _ in range(n_anomalies)]

    anomaly_mask = np.zeros(n_rows, dtype=int)  # 0=normal
    anomaly_type_arr = ["NORMAL"] * n_rows
    for start, length, atype in zip(anomaly_starts, anomaly_lengths, anomaly_types):
        end = min(start + length, n_rows)
        anomaly_mask[start:end] = 1
        for j in range(start, end):
            if atype == "high_mse":
                anomaly_type_arr[j] = "HIGH_MSE"
            elif atype == "stuck_pipe":
                anomaly_type_arr[j] = "STUCK_PIPE"
            elif atype == "vibration":
                anomaly_type_arr[j] = "VIBRATION"
            else:
                anomaly_type_arr[j] = "INEFFICIENT_DRILLING"

    # ── Generate drilling parameters ──────────────────────────
    records = []

    depth_factor = (md_values - md_start) / (md_end - md_start)

    # Base WOB: 8-20 klbs, higher in hard rock
    wob_base = 10 + hardness_smooth * 6
    wob = wob_base + np.random.normal(0, 1.0, n_rows)
    wob = np.clip(wob, 8, 22)

    # RPM: 80-160 rpm, lower in hard rock
    rpm_base = 130 - hardness_smooth * 40
    rpm = rpm_base + np.random.normal(0, 6, n_rows)
    rpm = np.clip(rpm, 70, 170)

    # Torque: 3000-12000 ft-lbs (scaled down for realistic MSE)
    torque_base = 4000 + hardness_smooth * 4000 + depth_factor * 2000
    torque = torque_base + np.random.normal(0, 500, n_rows)
    torque = np.clip(torque, 3000, 14000)

    # SPP: 2500-4500 psi
    spp_base = 3000 + depth_factor * 800 + hardness_smooth * 400
    spp = spp_base + np.random.normal(0, 100, n_rows)
    spp = np.clip(spp, 2500, 4500)

    # Flow: 350-550 gpm (relatively steady)
    flow_base = 420 + depth_factor * 80
    flow = flow_base + np.random.normal(0, 15, n_rows)
    flow = np.clip(flow, 350, 550)

    # Hookload: 280-450 klbs
    hookload_base = 320 + depth_factor * 80 + np.random.normal(0, 10, n_rows)
    hookload = np.clip(hookload_base, 280, 450)

    # ROP: 15-120 ft/hr — inversely correlated with hardness
    # Higher base ROP to keep MSE reasonable
    rop_base = 95 - hardness_smooth * 50
    rop = rop_base + np.random.normal(0, 8, n_rows)

    # Apply anomaly effects
    for i in range(n_rows):
        if anomaly_mask[i]:
            atype = anomaly_type_arr[i]
            if atype == "STUCK_PIPE":
                rop[i] = max(2, rop[i] * 0.08)
                torque[i] = min(14000, torque[i] * 1.6)
                wob[i] = min(22, wob[i] * 1.2)
            elif atype == "HIGH_MSE":
                rop[i] = max(5, rop[i] * 0.3)
                torque[i] = min(14000, torque[i] * 1.4)
            elif atype == "VIBRATION":
                rop[i] = max(8, rop[i] * 0.6 + random.uniform(-10, 10))
                torque[i] += random.uniform(-2000, 2000)
                torque[i] = np.clip(torque[i], 3000, 14000)
            elif atype == "INEFFICIENT_DRILLING":
                rop[i] = max(8, rop[i] * 0.45)

    rop = np.clip(rop, 2, 120)

    # MSE (Mechanical Specific Energy) — Teale formula
    # MSE = (480 * Torque * RPM) / (D^2 * ROP) + (4 * WOB) / (pi * D^2)
    # D = bit diameter in inches = 6.0
    # WOB in lbs (multiply klbs * 1000)
    D = 6.0
    mse = (480.0 * torque * rpm) / (D**2 * np.maximum(rop, 1)) + \
          (4.0 * wob * 1000) / (math.pi * D**2)

    # Scale MSE to realistic range: target median ~60K, with anomalies > 150K
    # The raw formula produces very high values, so we normalize
    mse_median = np.median(mse)
    target_median = 65000.0
    mse = mse * (target_median / mse_median)

    # Boost MSE during anomaly periods
    for i in range(n_rows):
        if anomaly_mask[i]:
            atype = anomaly_type_arr[i]
            if atype == "HIGH_MSE":
                mse[i] = mse[i] * random.uniform(2.0, 3.5)
            elif atype == "STUCK_PIPE":
                mse[i] = mse[i] * random.uniform(3.0, 5.0)
            elif atype == "VIBRATION":
                mse[i] = mse[i] * random.uniform(1.3, 2.0)
            elif atype == "INEFFICIENT_DRILLING":
                mse[i] = mse[i] * random.uniform(1.5, 2.5)

    # ROP predicted: model prediction (similar to actual but with some offset)
    # Simulate a decent model (R^2 ~ 0.85-0.90)
    rop_pred = rop * (1 + np.random.normal(0, 0.12, n_rows))
    # Add a slight positive bias (model is slightly optimistic)
    rop_pred = rop_pred + np.random.normal(2, 1.5, n_rows)
    rop_pred = np.clip(rop_pred, 5, 130)

    rop_gap = rop_pred - rop

    # Hazard flags: primarily based on anomaly periods, then MSE/gap thresholds
    hazard_flags = []
    for i in range(n_rows):
        if anomaly_type_arr[i] != "NORMAL":
            hazard_flags.append(anomaly_type_arr[i])
        elif mse[i] > 150000:
            hazard_flags.append("HIGH_MSE")
        elif rop_gap[i] > 20:
            hazard_flags.append("INEFFICIENT_DRILLING")
        else:
            hazard_flags.append("NORMAL")

    # Build records
    for i in range(n_rows):
        ts = start_time + timedelta(seconds=i * SAMPLE_INTERVAL_SEC)
        records.append({
            "well_id": well_id,
            "ts": ts,
            "md": round(float(md_values[i]), 2),
            "tvd": round(float(tvd_values[i]), 2),
            "wob": round(float(wob[i]), 2),
            "rpm": round(float(rpm[i]), 1),
            "torque": round(float(torque[i]), 1),
            "spp": round(float(spp[i]), 1),
            "flow": round(float(flow[i]), 1),
            "hookload": round(float(hookload[i]), 1),
            "rop_actual": round(float(rop[i]), 2),
            "rop_pred": round(float(rop_pred[i]), 2),
            "rop_gap": round(float(rop_gap[i]), 2),
            "mse": round(float(mse[i]), 2),
            "hazard_flag": hazard_flags[i],
        })

    return records


def generate_alerts(predictions: list[dict], well_id: str) -> list[dict]:
    """Generate sample alerts from prediction data anomalies."""
    alerts = []
    alert_messages = {
        "HIGH_MSE": [
            "MSE exceeded threshold at {md:.0f} ft — check bit wear or formation change",
            "Elevated MSE detected ({mse:.0f} psi) — consider adjusting WOB/RPM",
            "MSE spike at {md:.0f} ft MD — possible formation transition",
        ],
        "STUCK_PIPE": [
            "Stuck pipe detected at {md:.0f} ft — ROP near zero with high torque",
            "Possible differential sticking at {md:.0f} ft MD — initiate jar sequence",
            "Pack-off risk at {md:.0f} ft — flow restriction and torque increase",
        ],
        "INEFFICIENT_DRILLING": [
            "Drilling inefficiency at {md:.0f} ft — actual ROP {rop:.0f}% below predicted",
            "Suboptimal parameters at {md:.0f} ft — ROP gap {gap:.1f} ft/hr",
            "Consider parameter optimization — {gap:.1f} ft/hr improvement potential at {md:.0f} ft",
        ],
        "VIBRATION": [
            "Lateral vibration detected at {md:.0f} ft — torque fluctuation exceeds normal",
            "Stick-slip detected at {md:.0f} ft — RPM variation abnormal",
        ],
    }

    severity_map = {
        "STUCK_PIPE": "CRITICAL",
        "HIGH_MSE": "WARNING",
        "INEFFICIENT_DRILLING": "WARNING",
        "VIBRATION": "INFO",
    }

    # Sample anomalous predictions for alerts (not every anomaly row)
    anomalous = [p for p in predictions if p["hazard_flag"] != "NORMAL"]

    # Take a subset — one alert per ~5-10 anomaly rows
    if len(anomalous) > 100:
        alert_sources = random.sample(anomalous, min(80, len(anomalous) // 5))
    else:
        alert_sources = anomalous[:50]

    for p in alert_sources:
        flag = p["hazard_flag"]
        if flag not in alert_messages:
            continue

        msg_template = random.choice(alert_messages[flag])
        rop_pct = (1 - p["rop_actual"] / max(p["rop_pred"], 1)) * 100
        message = msg_template.format(
            md=p["md"], mse=p["mse"], rop=rop_pct, gap=p["rop_gap"],
        )

        alerts.append({
            "well_id": well_id,
            "ts": p["ts"],
            "alert_type": flag,
            "severity": severity_map.get(flag, "WARNING"),
            "message": message,
            "acknowledged": random.random() < 0.3,  # 30% already acknowledged
        })

    return alerts


async def setup_database(token: str):
    """Create the drilling_demo_app database if it doesn't exist."""
    print("Connecting to admin database to check/create drilling_demo_app...")
    conn = await asyncpg.connect(
        host=LAKEBASE_HOST,
        port=LAKEBASE_PORT,
        database=ADMIN_DATABASE,
        user="reishin.toolsi@databricks.com",
        password=token,
        ssl="require",
    )
    try:
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", DATABASE_NAME
        )
        if not exists:
            print(f"Creating database '{DATABASE_NAME}'...")
            await conn.execute(f'CREATE DATABASE "{DATABASE_NAME}"')
            print(f"Database '{DATABASE_NAME}' created.")
        else:
            print(f"Database '{DATABASE_NAME}' already exists.")
    finally:
        await conn.close()


async def create_schema(conn):
    """Create all tables in the drilling_demo_app database."""
    print("Creating schema tables...")

    # Wells
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS wells (
            id       SERIAL       PRIMARY KEY,
            well_id  TEXT UNIQUE  NOT NULL,
            name     TEXT,
            field    TEXT         DEFAULT 'MSEEL',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Predictions
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id          BIGSERIAL     PRIMARY KEY,
            well_id     TEXT          NOT NULL,
            ts          TIMESTAMPTZ   NOT NULL,
            md          DOUBLE PRECISION,
            rop_actual  DOUBLE PRECISION,
            rop_pred    DOUBLE PRECISION,
            rop_gap     DOUBLE PRECISION,
            mse         DOUBLE PRECISION,
            hazard_flag TEXT,
            created_at  TIMESTAMPTZ   DEFAULT NOW()
        )
    """)

    # Indexes on predictions
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS predictions_well_ts_idx
        ON predictions (well_id, ts DESC)
    """)

    # Alerts
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id               BIGSERIAL   PRIMARY KEY,
            well_id          TEXT        NOT NULL,
            ts               TIMESTAMPTZ NOT NULL,
            alert_type       TEXT        NOT NULL,
            severity         TEXT        NOT NULL DEFAULT 'WARNING',
            message          TEXT,
            acknowledged     BOOLEAN     DEFAULT FALSE,
            acknowledged_by  TEXT,
            acknowledged_at  TIMESTAMPTZ,
            CONSTRAINT valid_severity CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL'))
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS alerts_well_unack_idx
        ON alerts (well_id, acknowledged, ts DESC)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS alerts_active_idx
        ON alerts (acknowledged, ts DESC)
        WHERE acknowledged = FALSE
    """)

    # Model versions
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS model_versions (
            id            SERIAL      PRIMARY KEY,
            model_name    TEXT        NOT NULL,
            version       TEXT        NOT NULL,
            stage         TEXT,
            rmse          DOUBLE PRECISION,
            r2            DOUBLE PRECISION,
            feature_list  TEXT,
            registered_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (model_name, version)
        )
    """)

    print("Schema tables created successfully.")


async def grant_app_permissions(conn, app_role: str):
    """Grant permissions to the app service principal."""
    print(f"Granting permissions to '{app_role}'...")

    # Check if role exists
    role_exists = await conn.fetchval(
        "SELECT 1 FROM pg_roles WHERE rolname = $1", app_role
    )
    if not role_exists:
        print(f"  Role '{app_role}' not found in pg_roles — this is normal if "
              f"the app hasn't connected yet. Skipping grants (the app resource "
              f"binding will create the role automatically).")
        return

    try:
        await conn.execute(f'GRANT USAGE ON SCHEMA public TO "{app_role}"')
        await conn.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{app_role}"'
        )
        await conn.execute(
            f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{app_role}"'
        )
        await conn.execute(
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{app_role}"'
        )
        await conn.execute(
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            f'GRANT USAGE, SELECT ON SEQUENCES TO "{app_role}"'
        )
        print(f"  Permissions granted to '{app_role}'.")
    except Exception as e:
        print(f"  Warning: Could not grant permissions: {e}")
        print(f"  This may be fine — the app resource binding handles permissions.")


async def populate_wells(conn):
    """Insert well records."""
    print("Populating wells table...")
    for well in WELLS:
        await conn.execute(
            """
            INSERT INTO wells (well_id, name, field)
            VALUES ($1, $2, 'MSEEL')
            ON CONFLICT (well_id) DO NOTHING
            """,
            well["well_id"], well["name"],
        )
    count = await conn.fetchval("SELECT COUNT(*) FROM wells")
    print(f"  Wells table: {count} rows")


async def populate_predictions(conn, records: list[dict]):
    """Bulk insert prediction records."""
    print(f"  Inserting {len(records)} prediction rows...")

    # Use COPY for speed
    rows = [
        (
            r["well_id"], r["ts"], r["md"],
            r["rop_actual"], r["rop_pred"], r["rop_gap"],
            r["mse"], r["hazard_flag"],
        )
        for r in records
    ]

    await conn.copy_records_to_table(
        "predictions",
        records=rows,
        columns=["well_id", "ts", "md", "rop_actual", "rop_pred", "rop_gap", "mse", "hazard_flag"],
    )

    count = await conn.fetchval("SELECT COUNT(*) FROM predictions")
    print(f"  Predictions table: {count} total rows")


async def populate_alerts(conn, alerts: list[dict]):
    """Bulk insert alert records."""
    print(f"  Inserting {len(alerts)} alert rows...")

    rows = [
        (
            a["well_id"], a["ts"], a["alert_type"],
            a["severity"], a["message"], a["acknowledged"],
        )
        for a in alerts
    ]

    await conn.copy_records_to_table(
        "alerts",
        records=rows,
        columns=["well_id", "ts", "alert_type", "severity", "message", "acknowledged"],
    )

    count = await conn.fetchval("SELECT COUNT(*) FROM alerts")
    print(f"  Alerts table: {count} total rows")


async def populate_model_versions(conn):
    """Insert sample model version metadata."""
    print("Populating model_versions table...")

    models = [
        {
            "model_name": "rop_xgb_mseel",
            "version": "1",
            "stage": "Archived",
            "rmse": 8.42,
            "r2": 0.8234,
            "feature_list": json.dumps(["wob", "rpm", "torque", "spp", "flow", "hookload", "md", "mse"]),
        },
        {
            "model_name": "rop_xgb_mseel",
            "version": "2",
            "stage": "Archived",
            "rmse": 6.17,
            "r2": 0.8891,
            "feature_list": json.dumps(["wob", "rpm", "torque", "spp", "flow", "hookload", "md", "tvd", "mse", "d_rop_dt"]),
        },
        {
            "model_name": "rop_xgb_mseel",
            "version": "3",
            "stage": "Production",
            "rmse": 5.34,
            "r2": 0.9147,
            "feature_list": json.dumps(["wob", "rpm", "torque", "spp", "flow", "hookload", "md", "tvd", "mse", "d_rop_dt", "d_torque_dt", "d_spp_dt"]),
        },
        {
            "model_name": "rop_xgb_mseel",
            "version": "4",
            "stage": "Staging",
            "rmse": 5.11,
            "r2": 0.9203,
            "feature_list": json.dumps(["wob", "rpm", "torque", "spp", "flow", "hookload", "md", "tvd", "mse", "d_rop_dt", "d_torque_dt", "d_spp_dt"]),
        },
    ]

    for m in models:
        await conn.execute(
            """
            INSERT INTO model_versions (model_name, version, stage, rmse, r2, feature_list)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (model_name, version) DO UPDATE
            SET stage = $3, rmse = $4, r2 = $5, feature_list = $6
            """,
            m["model_name"], m["version"], m["stage"],
            m["rmse"], m["r2"], m["feature_list"],
        )

    count = await conn.fetchval("SELECT COUNT(*) FROM model_versions")
    print(f"  Model versions table: {count} rows")


async def main():
    print("=" * 60)
    print("MSEEL ROP Prediction — Lakebase Data Population")
    print("=" * 60)

    # Get OAuth token
    print("\nStep 1: Getting OAuth token...")
    token = get_oauth_token()
    print("  Token obtained.")

    # Create database if needed
    print("\nStep 2: Checking/creating database...")
    await setup_database(token)

    # Connect to the app database
    print(f"\nStep 3: Connecting to '{DATABASE_NAME}'...")
    conn = await asyncpg.connect(
        host=LAKEBASE_HOST,
        port=LAKEBASE_PORT,
        database=DATABASE_NAME,
        user="reishin.toolsi@databricks.com",
        password=token,
        ssl="require",
    )

    try:
        # Create schema
        print("\nStep 4: Creating schema...")
        await create_schema(conn)

        # Clear existing data for clean population
        print("\nStep 5: Clearing existing data...")
        await conn.execute("DELETE FROM alerts")
        await conn.execute("DELETE FROM predictions")
        await conn.execute("DELETE FROM model_versions")
        print("  Existing data cleared.")

        # Grant permissions to app service principal
        print("\nStep 6: Granting permissions...")
        await grant_app_permissions(conn, APP_SERVICE_PRINCIPAL)

        # Populate wells
        print("\nStep 7: Populating wells...")
        await populate_wells(conn)

        # Generate and insert synthetic data for each well
        all_predictions = []
        all_alerts = []

        for well in WELLS:
            wid = well["well_id"]
            print(f"\nStep 8: Generating synthetic data for {wid}...")
            predictions = generate_synthetic_drilling_data(wid, ROWS_PER_WELL)
            alerts = generate_alerts(predictions, wid)
            all_predictions.extend(predictions)
            all_alerts.extend(alerts)
            print(f"  Generated {len(predictions)} predictions, {len(alerts)} alerts for {wid}")

        # Bulk insert predictions
        print(f"\nStep 9: Inserting {len(all_predictions)} predictions...")
        await populate_predictions(conn, all_predictions)

        # Bulk insert alerts
        print(f"\nStep 10: Inserting {len(all_alerts)} alerts...")
        await populate_alerts(conn, all_alerts)

        # Model versions
        print("\nStep 11: Populating model versions...")
        await populate_model_versions(conn)

        # Verification
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        wells_count = await conn.fetchval("SELECT COUNT(*) FROM wells")
        pred_count = await conn.fetchval("SELECT COUNT(*) FROM predictions")
        alerts_count = await conn.fetchval("SELECT COUNT(*) FROM alerts")
        unacked_count = await conn.fetchval("SELECT COUNT(*) FROM alerts WHERE acknowledged = FALSE")
        mv_count = await conn.fetchval("SELECT COUNT(*) FROM model_versions")

        # Check time range
        ts_min = await conn.fetchval("SELECT MIN(ts) FROM predictions")
        ts_max = await conn.fetchval("SELECT MAX(ts) FROM predictions")

        # Check per-well counts
        well_counts = await conn.fetch(
            "SELECT well_id, COUNT(*) as cnt FROM predictions GROUP BY well_id ORDER BY well_id"
        )

        print(f"  Wells:            {wells_count}")
        print(f"  Predictions:      {pred_count}")
        for row in well_counts:
            print(f"    {row['well_id']}: {row['cnt']} rows")
        print(f"  Time range:       {ts_min} to {ts_max}")
        print(f"  Alerts:           {alerts_count} ({unacked_count} unacknowledged)")
        print(f"  Model versions:   {mv_count}")

        # Check hazard distribution
        hazard_dist = await conn.fetch(
            "SELECT hazard_flag, COUNT(*) as cnt FROM predictions GROUP BY hazard_flag ORDER BY cnt DESC"
        )
        print("  Hazard distribution:")
        for row in hazard_dist:
            print(f"    {row['hazard_flag']}: {row['cnt']}")

        print("\n" + "=" * 60)
        print("DATA POPULATION COMPLETE")
        print("=" * 60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
