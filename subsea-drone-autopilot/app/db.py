"""Database layer – Databricks SQL (Delta) + Lakebase (PostgreSQL)."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import psycopg2
from databricks.sdk import WorkspaceClient

from config import (
    WAREHOUSE_ID, CATALOG, SCHEMA,
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE,
)

logger = logging.getLogger(__name__)

# ── Databricks SQL helpers ──────────────────────────────────

def _client() -> WorkspaceClient:
    # Fresh client each time to avoid stale OAuth tokens
    return WorkspaceClient()

def sql_query(query: str, params: dict | None = None) -> list[dict]:
    """Execute SQL on the Databricks warehouse and return rows as dicts."""
    try:
        ws = _client()
        from databricks.sdk.service.sql import StatementState, Format, Disposition

        resp = ws.statement_execution.execute_statement(
            warehouse_id=WAREHOUSE_ID,
            statement=query,
            catalog=CATALOG,
            schema=SCHEMA,
            wait_timeout="30s",
            disposition=Disposition.INLINE,
            format=Format.JSON_ARRAY,
        )

        # Wait for completion if still running
        attempts = 0
        while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
            import time
            time.sleep(1)
            attempts += 1
            if attempts > 30:
                logger.error("SQL query timeout after 30 attempts")
                return []
            resp = ws.statement_execution.get_statement(resp.statement_id)

        if resp.status and resp.status.state == StatementState.FAILED:
            err = resp.status.error
            logger.error(f"SQL failed: {err}")
            return []

        if not resp.result or not resp.result.data_array:
            logger.info(f"SQL returned 0 rows for: {query[:80]}")
            return []

        cols = [c.name for c in resp.manifest.schema.columns]
        rows = [dict(zip(cols, row)) for row in resp.result.data_array]
        logger.info(f"SQL returned {len(rows)} rows for: {query[:60]}")
        return rows

    except Exception as e:
        logger.error(f"SQL query exception: {e}")
        return []

# ── Drone status & limits ───────────────────────────────────

def get_all_drones() -> list[dict]:
    return sql_query("""
        SELECT s.*, l.max_depth_m, l.max_duration_min,
               l.min_battery_reserve_pct_low_risk,
               l.min_battery_reserve_pct_med_risk,
               l.min_battery_reserve_pct_high_risk
        FROM subsea.drone_status s
        JOIN subsea.drone_limits l USING (drone_id)
    """)

def get_drone(drone_id: str) -> dict | None:
    rows = sql_query(f"""
        SELECT s.*, l.max_depth_m, l.max_duration_min,
               l.min_battery_reserve_pct_low_risk,
               l.min_battery_reserve_pct_med_risk,
               l.min_battery_reserve_pct_high_risk
        FROM subsea.drone_status s
        JOIN subsea.drone_limits l USING (drone_id)
        WHERE s.drone_id = '{drone_id}'
    """)
    return rows[0] if rows else None

# ── Telemetry ───────────────────────────────────────────────

def get_telemetry_features(mission_id: str) -> list[dict]:
    return sql_query(f"""
        SELECT * FROM subsea.telemetry_features
        WHERE mission_id = '{mission_id}'
        ORDER BY window_start_ts
    """)

def get_latest_anomaly(drone_id: str) -> dict | None:
    rows = sql_query(f"""
        SELECT anomaly_score, health_label
        FROM subsea.telemetry_features
        WHERE drone_id = '{drone_id}'
        ORDER BY window_end_ts DESC LIMIT 1
    """)
    return rows[0] if rows else None

# ── Inspections ─────────────────────────────────────────────

def get_inspection(mission_id: str) -> dict | None:
    rows = sql_query(f"""
        SELECT * FROM subsea.inspections
        WHERE mission_id = '{mission_id}'
    """)
    return rows[0] if rows else None

def create_inspection(mission_id: str, asset_id: str, asset_type: str, requested_by: str) -> None:
    sql_query(f"""
        INSERT INTO subsea.inspections
        (mission_id, asset_id, asset_type, requested_by, start_ts, status)
        VALUES ('{mission_id}', '{asset_id}', '{asset_type}', '{requested_by}',
                current_timestamp(), 'requested')
    """)

def update_inspection_status(mission_id: str, status: str, summary_json: str | None = None) -> None:
    extra = f", summary_json = '{summary_json}'" if summary_json else ""
    end = ", end_ts = current_timestamp()" if status in ("completed", "aborted", "failed") else ""
    sql_query(f"""
        UPDATE subsea.inspections
        SET status = '{status}'{end}{extra}
        WHERE mission_id = '{mission_id}'
    """)

# ── Inspection Frames ───────────────────────────────────────

def get_inspection_frames(mission_id: str, limit: int = 50) -> list[dict]:
    return sql_query(f"""
        SELECT * FROM subsea.inspection_frames
        WHERE mission_id = '{mission_id}'
        ORDER BY severity_score DESC
        LIMIT {limit}
    """)

# ── Autopilot Decisions (audit) ─────────────────────────────

def log_autopilot_decision(
    decision_id: str, mission_id: str | None, decision_type: str,
    input_json: str, tool_outputs_json: str, final_plan_json: str,
) -> None:
    sql_query(f"""
        INSERT INTO subsea.autopilot_decisions
        (decision_id, ts, mission_id, decision_type, input_json, tool_outputs_json, final_plan_json)
        VALUES ('{decision_id}', current_timestamp(), {f"'{mission_id}'" if mission_id else 'NULL'},
                '{decision_type}', '{input_json}', '{tool_outputs_json}', '{final_plan_json}')
    """)

# ── Lakebase (PostgreSQL) helpers ───────────────────────────

_pg_host = "ep-bold-mode-d2m0j9ek.database.us-east-1.cloud.databricks.com"
_pg_db = "subsea_ops"

def pg_conn():
    """Connect to Lakebase. Uses env vars if available (app resource binding),
    falls back to SDK OAuth token generation."""
    # Try env vars first (injected by app.yaml lakebase resource)
    if PG_HOST and PG_PASSWORD:
        return psycopg2.connect(
            host=PG_HOST, port=PG_PORT, user=PG_USER,
            password=PG_PASSWORD, dbname=PG_DATABASE,
            sslmode="require",
        )

    # Fallback: use SDK API to generate OAuth credential
    try:
        ws = _client()
        user = ws.current_user.me().user_name
        # Use the SDK's raw API to generate a database credential
        import httpx as _httpx
        host = ws.config.host.rstrip("/")
        headers = {"Authorization": f"Bearer {ws.config.token}"}
        r = _httpx.post(
            f"{host}/api/2.0/postgres/projects/subsea-ops/branches/production/endpoints/primary:generateDatabaseCredential",
            headers=headers, json={}, timeout=15,
        )
        r.raise_for_status()
        resp = r.json()
        token = resp.get("token", "")
        if not token:
            raise ValueError("No token in credential response")
        return psycopg2.connect(
            host=_pg_host, port=5432, user=user,
            password=token, dbname=_pg_db,
            sslmode="require",
        )
    except Exception as e:
        logger.error(f"Lakebase connection failed: {e}")
        raise

def pg_query(sql: str, params: tuple = ()) -> list[dict]:
    try:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Lakebase query failed: {e}")
        return []

def pg_execute(sql: str, params: tuple = ()) -> None:
    try:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
    except Exception as e:
        logger.error(f"Lakebase execute failed: {e}")

# ── Lakebase-specific queries ───────────────────────────────

def pg_get_alerts(acknowledged: bool = False, limit: int = 20) -> list[dict]:
    return pg_query(
        "SELECT * FROM operational_alerts WHERE acknowledged = %s ORDER BY created_at DESC LIMIT %s",
        (acknowledged, limit),
    )

def pg_get_mission_state(mission_id: str) -> dict | None:
    rows = pg_query("SELECT * FROM mission_state WHERE mission_id = %s", (mission_id,))
    return rows[0] if rows else None

def pg_upsert_mission(mission_id: str, drone_id: str, asset_id: str, asset_type: str,
                      status: str, plan_json: str = None, summary: str = None) -> None:
    pg_execute("""
        INSERT INTO mission_state (mission_id, drone_id, asset_id, asset_type, status, plan_json, summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (mission_id) DO UPDATE SET
            status = EXCLUDED.status, updated_at = NOW(),
            plan_json = COALESCE(EXCLUDED.plan_json, mission_state.plan_json),
            summary = COALESCE(EXCLUDED.summary, mission_state.summary)
    """, (mission_id, drone_id, asset_id, asset_type, status, plan_json, summary))

def pg_create_alert(alert_id: str, drone_id: str, alert_type: str, severity: str,
                    message: str, mission_id: str = None) -> None:
    pg_execute("""
        INSERT INTO operational_alerts (alert_id, drone_id, alert_type, severity, message, mission_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (alert_id) DO NOTHING
    """, (alert_id, drone_id, alert_type, severity, message, mission_id))

def pg_acknowledge_alert(alert_id: str, user: str) -> None:
    pg_execute("""
        UPDATE operational_alerts SET acknowledged = TRUE, acknowledged_by = %s, acknowledged_at = NOW()
        WHERE alert_id = %s
    """, (user, alert_id))

# ── Vector Search (RAG) ────────────────────────────────────

def query_manual_chunks(query_text: str, num_results: int = 5) -> list[dict]:
    """Query the subsea manuals vector index."""
    ws = _client()
    from config import VS_INDEX, VS_ENDPOINT
    idx = ws.vector_search_indexes.query_index(
        index_name=VS_INDEX,
        columns=["doc_name", "section", "chunk_text"],
        query_text=query_text,
        num_results=num_results,
    )
    return [
        {"doc": r[0], "section": r[1], "chunk_text": r[2]}
        for r in (idx.result.data_array or [])
    ]
