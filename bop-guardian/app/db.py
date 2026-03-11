"""
app/db.py
----------
Database connection layer for BOP Guardian.
Lakebase (psycopg2) for persistent telemetry, anomalies, work orders, and crew data.
Falls back to in-memory mock data when Lakebase is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

from app.config import config

logger = logging.getLogger(__name__)

LAKEBASE_INSTANCE = "bop-guardian-db"

# ── Connection helpers ────────────────────────────────────────────────────────

def _get_pg_conn():
    """Return a psycopg2 connection using native PostgreSQL credentials."""
    host     = os.getenv("PGHOST", "localhost")
    port     = config.pg_port
    dbname   = config.pg_database
    user     = os.getenv("PGUSER", config.pg_user or "bop_app")
    password = os.getenv("PGPASSWORD", config.pg_password or "")
    return psycopg2.connect(
        host=host, port=port, dbname=dbname,
        user=user, password=password,
        connect_timeout=10, sslmode="require",
    )


@st.cache_resource(ttl=30)
def get_pg_conn():
    try:
        conn = _get_pg_conn()
        logger.info("Lakebase connection established.")
        return conn
    except Exception as e:
        logger.error(f"Lakebase connection failed: {e}")
        return None


def pg_query(sql: str, params=None) -> pd.DataFrame:
    conn = get_pg_conn()
    if conn is None:
        return pd.DataFrame()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return pd.DataFrame(rows)
    except Exception as e:
        conn.rollback()
        logger.error(f"pg_query error: {e}\nSQL: {sql}")
        return pd.DataFrame()


def pg_execute(sql: str, params=None) -> bool:
    conn = get_pg_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"pg_execute error: {e}\nSQL: {sql}")
        return False


def is_connected() -> bool:
    """Check if Lakebase is reachable."""
    return get_pg_conn() is not None


# ── Schema bootstrap ─────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS bop_components (
    asset_id        VARCHAR(50)  PRIMARY KEY,
    component_type  VARCHAR(50)  NOT NULL,
    name            VARCHAR(200) NOT NULL,
    rig_id          VARCHAR(50)  NOT NULL DEFAULT 'RIG-SENTINEL'
);

CREATE TABLE IF NOT EXISTS bop_telemetry (
    id          SERIAL       PRIMARY KEY,
    rig_id      VARCHAR(50)  NOT NULL,
    asset_id    VARCHAR(50)  NOT NULL,
    tag         VARCHAR(100) NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    unit        VARCHAR(20),
    ts          TIMESTAMPTZ  NOT NULL,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_telemetry_asset_ts ON bop_telemetry (asset_id, ts DESC);

CREATE TABLE IF NOT EXISTS bop_anomalies (
    anomaly_id      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    rig_id          VARCHAR(50)  NOT NULL,
    asset_id        VARCHAR(50)  NOT NULL,
    component_type  VARCHAR(50),
    anomaly_type    VARCHAR(100),
    severity        INT          DEFAULT 2,
    ts              TIMESTAMPTZ  NOT NULL,
    acknowledged_by VARCHAR(255),
    acknowledged_ts TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_anomaly_ts ON bop_anomalies (ts DESC);

CREATE TABLE IF NOT EXISTS bop_events (
    event_id    SERIAL       PRIMARY KEY,
    rig_id      VARCHAR(50)  NOT NULL,
    asset_id    VARCHAR(50),
    event_type  VARCHAR(100) NOT NULL,
    severity    INT          DEFAULT 1,
    message     TEXT,
    ts          TIMESTAMPTZ  NOT NULL,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bop_work_orders (
    work_order_id   SERIAL       PRIMARY KEY,
    wo_id           VARCHAR(50)  UNIQUE,
    rig_id          VARCHAR(50),
    equipment_id    VARCHAR(50),
    description     TEXT,
    status          VARCHAR(20)  DEFAULT 'OPEN',
    priority        INT          DEFAULT 3,
    failure_code    VARCHAR(50),
    maintenance_activity VARCHAR(50),
    start_date      DATE,
    finish_date     DATE,
    created_by      VARCHAR(255),
    created_ts      TIMESTAMPTZ  DEFAULT NOW(),
    updated_ts      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bop_spare_parts (
    material_id     VARCHAR(50)  PRIMARY KEY,
    description     TEXT,
    component_type  VARCHAR(50),
    available_qty   INT          DEFAULT 0,
    min_stock       INT          DEFAULT 1,
    lead_time_days  INT          DEFAULT 14,
    unit_price      NUMERIC(12,2),
    plant           VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS bop_crew (
    crew_id     VARCHAR(20)  PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    role        VARCHAR(100),
    company     VARCHAR(100),
    shift       VARCHAR(10),
    zone        VARCHAR(50),
    is_on_rig   BOOLEAN      DEFAULT TRUE,
    certs       TEXT[]
);

CREATE TABLE IF NOT EXISTS bop_rul_predictions (
    asset_id            VARCHAR(50)  PRIMARY KEY,
    component_type      VARCHAR(50),
    predicted_rul_days  INT,
    failure_prob_7d     DOUBLE PRECISION,
    failure_prob_30d    DOUBLE PRECISION,
    model_version       VARCHAR(50),
    updated_ts          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bop_agent_recommendations (
    rec_id      SERIAL       PRIMARY KEY,
    agent       VARCHAR(50)  NOT NULL,
    severity    INT          DEFAULT 1,
    title       VARCHAR(500),
    detail      TEXT,
    actions     JSONB,
    asset_id    VARCHAR(50),
    assigned_crew JSONB,
    tick        INT,
    ts          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bop_chat_messages (
    message_id  SERIAL       PRIMARY KEY,
    role        VARCHAR(20)  NOT NULL,
    content     TEXT         NOT NULL,
    created_ts  TIMESTAMPTZ  DEFAULT NOW()
);
"""


def bootstrap_schema():
    """Create all tables if they don't exist."""
    for statement in DDL.split(";"):
        statement = statement.strip()
        if statement:
            pg_execute(statement + ";")
    logger.info("Lakebase schema bootstrapped.")


# ── Seed data ────────────────────────────────────────────────────────────────

def seed_if_empty():
    """Populate tables with mock data if they are empty."""
    from app.mock_data import (
        SAP_WORK_ORDERS, SAP_SPARES, CREW, RUL_PREDICTIONS,
    )
    from app.simulator import COMPONENTS, RIG_ID

    # Components
    row = pg_query("SELECT COUNT(*) AS cnt FROM bop_components")
    if row.empty or int(row.iloc[0]["cnt"]) == 0:
        for c in COMPONENTS:
            pg_execute(
                "INSERT INTO bop_components (asset_id, component_type, name, rig_id) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (c["asset_id"], c["component_type"], c["name"], RIG_ID),
            )

    # Work orders
    row = pg_query("SELECT COUNT(*) AS cnt FROM bop_work_orders")
    if row.empty or int(row.iloc[0]["cnt"]) == 0:
        for wo in SAP_WORK_ORDERS:
            pg_execute(
                "INSERT INTO bop_work_orders (wo_id, rig_id, equipment_id, description, "
                "status, priority, failure_code, maintenance_activity, start_date, finish_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (wo["wo_id"], wo["rig_id"], wo["equipment_id"], wo["description"],
                 wo["status"], wo["priority"], wo.get("failure_code", ""),
                 wo.get("maintenance_activity", ""), wo["start_date"], wo["finish_date"]),
            )

    # Spare parts
    row = pg_query("SELECT COUNT(*) AS cnt FROM bop_spare_parts")
    if row.empty or int(row.iloc[0]["cnt"]) == 0:
        for sp in SAP_SPARES:
            pg_execute(
                "INSERT INTO bop_spare_parts (material_id, description, component_type, "
                "available_qty, min_stock, lead_time_days, unit_price, plant) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (sp["material_id"], sp["description"], sp["component_type"],
                 sp["available_qty"], sp["min_stock"], sp["lead_time_days"],
                 sp["unit_price"], sp["plant"]),
            )

    # Crew
    row = pg_query("SELECT COUNT(*) AS cnt FROM bop_crew")
    if row.empty or int(row.iloc[0]["cnt"]) == 0:
        for cr in CREW:
            pg_execute(
                "INSERT INTO bop_crew (crew_id, name, role, company, shift, zone, is_on_rig, certs) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (cr["crew_id"], cr["name"], cr["role"], cr["company"],
                 cr["shift"], cr["zone"], cr["is_on_rig"], cr.get("certs", [])),
            )

    # RUL predictions
    row = pg_query("SELECT COUNT(*) AS cnt FROM bop_rul_predictions")
    if row.empty or int(row.iloc[0]["cnt"]) == 0:
        for rul in RUL_PREDICTIONS:
            pg_execute(
                "INSERT INTO bop_rul_predictions (asset_id, component_type, predicted_rul_days, "
                "failure_prob_7d, failure_prob_30d, model_version) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (rul["asset_id"], rul["component_type"], rul["predicted_rul_days"],
                 rul["failure_prob_7d"], rul["failure_prob_30d"], rul["model_version"]),
            )

    logger.info("Lakebase seed data loaded.")


# ── Domain queries ────────────────────────────────────────────────────────────

def save_telemetry_batch(readings: list[dict]) -> bool:
    """Bulk insert telemetry readings from a simulator tick."""
    conn = get_pg_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO bop_telemetry (rig_id, asset_id, tag, value, unit, ts) "
                "VALUES %s",
                [(r["rig_id"], r["asset_id"], r["tag"], r["value"],
                  r["unit"], r["ts"]) for r in readings],
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"save_telemetry_batch error: {e}")
        return False


def save_anomaly(rig_id: str, asset_id: str, component_type: str,
                 anomaly_type: str, severity: int, ts: str) -> bool:
    return pg_execute(
        "INSERT INTO bop_anomalies (rig_id, asset_id, component_type, anomaly_type, severity, ts) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (rig_id, asset_id, component_type, anomaly_type, severity, ts),
    )


def save_event(rig_id: str, asset_id: str, event_type: str,
               severity: int, message: str, ts: str) -> bool:
    return pg_execute(
        "INSERT INTO bop_events (rig_id, asset_id, event_type, severity, message, ts) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (rig_id, asset_id, event_type, severity, message, ts),
    )


def save_recommendation(agent: str, severity: int, title: str, detail: str,
                        actions: list[str], asset_id: str, assigned_crew: list[str],
                        tick: int) -> bool:
    return pg_execute(
        "INSERT INTO bop_agent_recommendations (agent, severity, title, detail, actions, "
        "asset_id, assigned_crew, tick) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (agent, severity, title, detail, json.dumps(actions), asset_id,
         json.dumps(assigned_crew), tick),
    )


def save_chat_message(role: str, content: str) -> bool:
    return pg_execute(
        "INSERT INTO bop_chat_messages (role, content) VALUES (%s, %s)",
        (role, content),
    )


def get_recent_telemetry(asset_id: str = None, tag: str = None,
                         limit: int = 200) -> pd.DataFrame:
    conditions = []
    params = []
    if asset_id:
        conditions.append("asset_id = %s")
        params.append(asset_id)
    if tag:
        conditions.append("tag = %s")
        params.append(tag)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)
    return pg_query(
        f"SELECT rig_id, asset_id, tag, value, unit, ts "
        f"FROM bop_telemetry {where} ORDER BY ts DESC LIMIT %s",
        tuple(params),
    )


def get_recent_anomalies(limit: int = 50) -> pd.DataFrame:
    return pg_query(
        "SELECT anomaly_id, rig_id, asset_id, component_type, anomaly_type, severity, "
        "ts, acknowledged_by, acknowledged_ts FROM bop_anomalies "
        "ORDER BY ts DESC LIMIT %s",
        (limit,),
    )


def get_unacknowledged_anomalies(limit: int = 50) -> pd.DataFrame:
    return pg_query(
        "SELECT anomaly_id, rig_id, asset_id, component_type, anomaly_type, severity, ts "
        "FROM bop_anomalies WHERE acknowledged_ts IS NULL "
        "ORDER BY ts DESC LIMIT %s",
        (limit,),
    )


def acknowledge_anomaly(anomaly_id: str, user: str) -> bool:
    return pg_execute(
        "UPDATE bop_anomalies SET acknowledged_by = %s, acknowledged_ts = NOW() "
        "WHERE anomaly_id = %s",
        (user, str(anomaly_id)),
    )


def get_recent_events(limit: int = 50) -> pd.DataFrame:
    return pg_query(
        "SELECT event_id, rig_id, asset_id, event_type, severity, message, ts "
        "FROM bop_events ORDER BY ts DESC LIMIT %s",
        (limit,),
    )


def get_work_orders(status_filter: Optional[list] = None) -> pd.DataFrame:
    if status_filter:
        placeholders = ",".join(["%s"] * len(status_filter))
        return pg_query(
            f"SELECT * FROM bop_work_orders WHERE status IN ({placeholders}) "
            f"ORDER BY created_ts DESC",
            tuple(status_filter),
        )
    return pg_query("SELECT * FROM bop_work_orders ORDER BY created_ts DESC LIMIT 200")


def get_spare_parts() -> pd.DataFrame:
    return pg_query("SELECT * FROM bop_spare_parts ORDER BY component_type, material_id")


def get_crew() -> pd.DataFrame:
    return pg_query("SELECT * FROM bop_crew ORDER BY crew_id")


def get_rul_predictions() -> pd.DataFrame:
    return pg_query(
        "SELECT * FROM bop_rul_predictions ORDER BY predicted_rul_days ASC"
    )


def get_recommendations(limit: int = 20) -> pd.DataFrame:
    return pg_query(
        "SELECT * FROM bop_agent_recommendations ORDER BY ts DESC LIMIT %s",
        (limit,),
    )


def get_chat_history(limit: int = 50) -> pd.DataFrame:
    return pg_query(
        "SELECT role, content, created_ts FROM bop_chat_messages "
        "ORDER BY created_ts ASC LIMIT %s",
        (limit,),
    )


def get_telemetry_stats() -> pd.DataFrame:
    """Aggregate stats for each component's sensors."""
    return pg_query("""
        SELECT asset_id, tag, COUNT(*) as readings,
               ROUND(AVG(value)::numeric, 2) as avg_value,
               ROUND(MIN(value)::numeric, 2) as min_value,
               ROUND(MAX(value)::numeric, 2) as max_value,
               MAX(ts) as latest_ts
        FROM bop_telemetry
        GROUP BY asset_id, tag
        ORDER BY asset_id, tag
    """)
