"""
app/db.py
----------
Database connection layer:
  - Lakebase (psycopg2) for transactional app tables
  - Databricks SQL (SDK) for Delta gold tables
"""

from __future__ import annotations
import os
import functools
import logging
from typing import Optional

import psycopg2
import psycopg2.extras
import pandas as pd
import streamlit as st

from config import config

logger = logging.getLogger(__name__)

LAKEBASE_INSTANCE = "esp-pm-db"
LAKEBASE_HOST     = "instance-144fec57-c1ae-40a9-9d3a-ed74397cc232.database.cloud.databricks.com"

# ── Lakebase helpers ──────────────────────────────────────────────────────────

def _get_pg_conn():
    """Return a psycopg2 connection using native PostgreSQL credentials."""
    host     = os.getenv("PGHOST", LAKEBASE_HOST)
    port     = config.pg_port
    dbname   = config.pg_database
    user     = os.getenv("PGUSER", config.pg_user or "esp_app")
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


# ── Databricks SQL helpers ────────────────────────────────────────────────────

@st.cache_resource(ttl=120)
def _get_dbx_client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient(
        host=config.databricks_host or os.getenv("DATABRICKS_HOST"),
        token=config.databricks_token or os.getenv("DATABRICKS_TOKEN"),
    )


def dbx_query(sql: str) -> pd.DataFrame:
    """Execute SQL against Databricks SQL warehouse; return DataFrame."""
    try:
        wc = _get_dbx_client()
        wh_id = config.databricks_warehouse_id
        result = wc.statement_execution.execute_statement(
            warehouse_id=wh_id,
            statement=sql,
            wait_timeout="30s",
        )
        if result.status.state.value != "SUCCEEDED":
            logger.error(f"DBX query failed: {result.status}")
            return pd.DataFrame()
        cols = [c.name for c in result.manifest.schema.columns]
        rows = [list(r) for r in result.result.data_array or []]
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        logger.error(f"dbx_query error: {e}\nSQL: {sql[:200]}")
        return pd.DataFrame()


# ── Domain queries ────────────────────────────────────────────────────────────

def get_fleet_summary(days: int = 7) -> pd.DataFrame:
    """Latest prediction per ESP with fleet KPIs."""
    return dbx_query(f"""
        WITH latest AS (
            SELECT esp_id, MAX(prediction_ts) AS max_ts
            FROM oil_pump_monitor_catalog.gold.esp_failure_predictions
            WHERE prediction_ts >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
            GROUP BY esp_id
        )
        SELECT p.*
        FROM oil_pump_monitor_catalog.gold.esp_failure_predictions p
        JOIN latest ON p.esp_id = latest.esp_id AND p.prediction_ts = latest.max_ts
        ORDER BY p.priority_score DESC
    """)


def get_esp_telemetry(esp_id: str, hours: int = 48) -> pd.DataFrame:
    """Recent telemetry for a single ESP."""
    return dbx_query(f"""
        SELECT timestamp, pressure, temperature, current, frequency,
               vibration, flow_rate, status
        FROM oil_pump_monitor_catalog.raw.esp_telemetry_bronze
        WHERE esp_id = '{esp_id}'
          AND timestamp >= CURRENT_TIMESTAMP() - INTERVAL {hours} HOURS
        ORDER BY timestamp
    """)


def get_esp_predictions(esp_id: str, days: int = 14) -> pd.DataFrame:
    return dbx_query(f"""
        SELECT prediction_ts, failure_risk_score, risk_bucket, priority_score,
               top_feature_1, top_feature_2, top_feature_3,
               top_feature_1_value, top_feature_2_value, top_feature_3_value
        FROM oil_pump_monitor_catalog.gold.esp_failure_predictions
        WHERE esp_id = '{esp_id}'
          AND prediction_ts >= CURRENT_TIMESTAMP() - INTERVAL {days} DAYS
        ORDER BY prediction_ts
    """)


def get_open_alerts(limit: int = 200) -> pd.DataFrame:
    return pg_query("""
        SELECT alert_id, esp_id, prediction_ts, failure_risk_score, risk_bucket,
               priority_score, status, acknowledged_by, acknowledged_ts,
               lead_time_hours, sap_order_id, comments, created_ts
        FROM esp_alerts
        WHERE status IN ('NEW', 'ACK', 'IN_PROGRESS')
        ORDER BY priority_score DESC NULLS LAST, created_ts DESC
        LIMIT %s
    """, (limit,))


def get_all_alerts(days: int = 30) -> pd.DataFrame:
    return pg_query("""
        SELECT alert_id, esp_id, prediction_ts, failure_risk_score, risk_bucket,
               priority_score, status, acknowledged_by, sap_order_id, created_ts
        FROM esp_alerts
        WHERE created_ts >= NOW() - INTERVAL '30 days'
        ORDER BY created_ts DESC
    """)


def get_work_orders(status_filter: Optional[list] = None) -> pd.DataFrame:
    if status_filter:
        placeholders = ",".join(["%s"] * len(status_filter))
        return pg_query(
            f"SELECT * FROM esp_work_orders WHERE status IN ({placeholders}) ORDER BY created_ts DESC",
            tuple(status_filter),
        )
    return pg_query("SELECT * FROM esp_work_orders ORDER BY created_ts DESC LIMIT 200")


def get_chat_history(session_id: str) -> pd.DataFrame:
    return pg_query(
        "SELECT role, content, created_ts FROM esp_ai_chat_messages "
        "WHERE session_id = %s ORDER BY created_ts ASC",
        (session_id,),
    )


def save_chat_message(session_id: str, role: str, content: str,
                      context_snapshot: dict = None, model_version: str = None) -> bool:
    import json
    return pg_execute(
        """INSERT INTO esp_ai_chat_messages (session_id, role, content, context_snapshot, model_version)
           VALUES (%s, %s, %s, %s, %s)""",
        (session_id, role, content,
         json.dumps(context_snapshot) if context_snapshot else None,
         model_version),
    )


def ensure_chat_session(user_id: str, esp_id: Optional[str] = None) -> str:
    """Return existing open session or create a new one. Returns session_id."""
    row = pg_query(
        "SELECT session_id FROM esp_ai_chat_sessions "
        "WHERE user_id = %s AND (esp_id = %s OR (%s IS NULL AND esp_id IS NULL)) "
        "ORDER BY updated_ts DESC LIMIT 1",
        (user_id, esp_id, esp_id),
    )
    if not row.empty:
        return row.iloc[0]["session_id"]
    pg_execute(
        "INSERT INTO esp_ai_chat_sessions (user_id, esp_id) VALUES (%s, %s)",
        (user_id, esp_id),
    )
    row = pg_query(
        "SELECT session_id FROM esp_ai_chat_sessions "
        "WHERE user_id = %s ORDER BY created_ts DESC LIMIT 1",
        (user_id,),
    )
    return row.iloc[0]["session_id"] if not row.empty else "unknown"


def acknowledge_alert(alert_id: str, user: str) -> bool:
    return pg_execute(
        """UPDATE esp_alerts
           SET status = 'ACK', acknowledged_by = %s, acknowledged_ts = NOW()
           WHERE alert_id = %s AND status = 'NEW'""",
        (user, alert_id),
    )


def create_work_order(esp_id: str, alert_id: str, description: str,
                      suggested_action: str, created_by: str) -> Optional[str]:
    pg_execute(
        """INSERT INTO esp_work_orders
           (esp_id, alert_id, description, suggested_action, created_by, status)
           VALUES (%s, %s, %s, %s, %s, 'DRAFT')""",
        (esp_id, alert_id, description, suggested_action, created_by),
    )
    row = pg_query(
        "SELECT work_order_id FROM esp_work_orders WHERE esp_id = %s ORDER BY created_ts DESC LIMIT 1",
        (esp_id,),
    )
    return row.iloc[0]["work_order_id"] if not row.empty else None
