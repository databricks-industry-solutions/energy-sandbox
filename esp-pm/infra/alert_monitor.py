"""
infra/alert_monitor.py
-----------------------
Alert Monitor — STEP 6 alert & work-order logic.
Reads new predictions from esp_ai.gold.esp_failure_predictions via Change Data Feed,
creates/deduplicates esp_alerts in Lakebase, and optionally writes SAP PM
notifications via BDC write-back.

Run as a Databricks Job (continuous cluster) or scheduled notebook.
"""

from __future__ import annotations
import os
import sys
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import psycopg2
import psycopg2.extras
from databricks.sdk import WorkspaceClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
PRED_TABLE       = "esp_ai.gold.esp_failure_predictions"
DEDUP_WINDOW_H   = 4        # suppress duplicate alerts within this window per ESP
THRESHOLD_HIGH   = float(os.getenv("THRESHOLD_HIGH",   "0.65"))
THRESHOLD_MEDIUM = float(os.getenv("THRESHOLD_MEDIUM", "0.30"))
POLL_INTERVAL_S  = int(os.getenv("POLL_INTERVAL_SEC",  "60"))

PG_HOST     = os.getenv("PGHOST",     "localhost")
PG_PORT     = int(os.getenv("PGPORT", "5432"))
PG_DB       = os.getenv("PGDATABASE", "esp_pm_app")
PG_USER     = os.getenv("PGUSER",     "postgres")
PG_PASSWORD = os.getenv("PGPASSWORD", "")

WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")


# ── Database helpers ───────────────────────────────────────────────────────────
def pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
        connect_timeout=10, sslmode="require",
    )


def get_wc() -> WorkspaceClient:
    return WorkspaceClient()


def get_warehouse_id(wc: WorkspaceClient) -> str:
    if WAREHOUSE_ID:
        return WAREHOUSE_ID
    whs = wc.warehouses.list()
    running = [w for w in whs if w.state and w.state.value == "RUNNING"]
    if not running:
        raise RuntimeError("No running SQL warehouse found.")
    return running[0].id


# ── Main polling loop ──────────────────────────────────────────────────────────
def read_new_predictions(wc: WorkspaceClient, wh_id: str, since_ts: str) -> list[dict]:
    """Poll new HIGH/MEDIUM predictions since last run."""
    sql = f"""
        SELECT esp_id, prediction_ts, failure_risk_score, risk_bucket, priority_score,
               top_feature_1, top_feature_2, top_feature_3,
               model_version, model_run_id
        FROM {PRED_TABLE}
        WHERE prediction_ts > '{since_ts}'
          AND risk_bucket IN ('HIGH', 'MEDIUM')
        ORDER BY prediction_ts ASC
        LIMIT 500
    """
    result = wc.statement_execution.execute_statement(
        warehouse_id=wh_id, statement=sql, wait_timeout="30s"
    )
    if result.status.state.value != "SUCCEEDED":
        log.warning(f"Prediction query failed: {result.status}")
        return []

    cols = [c.name for c in result.manifest.schema.columns]
    rows = result.result.data_array or []
    return [dict(zip(cols, row.values)) for row in rows]


def alert_exists(conn, esp_id: str, risk_bucket: str, window_h: int) -> bool:
    """Return True if an open alert already exists for this ESP within the dedup window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_h)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM esp_alerts
            WHERE esp_id = %s
              AND risk_bucket = %s
              AND status IN ('NEW', 'ACK', 'IN_PROGRESS')
              AND created_ts >= %s
            LIMIT 1
        """, (esp_id, risk_bucket, cutoff))
        return cur.fetchone() is not None


def create_alert(conn, row: dict) -> Optional[str]:
    """Insert a new alert row; return alert_id."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO esp_alerts
              (esp_id, prediction_ts, failure_risk_score, risk_bucket, priority_score, created_by)
            VALUES (%s, %s, %s, %s, %s, 'alert_monitor')
            RETURNING alert_id
        """, (
            row["esp_id"],
            row["prediction_ts"],
            float(row["failure_risk_score"]),
            row["risk_bucket"],
            float(row["priority_score"]) if row.get("priority_score") else None,
        ))
        result = cur.fetchone()
    conn.commit()
    return result[0] if result else None


def maybe_create_sap_notification(alert_id: str, row: dict):
    """
    Placeholder: write a SAP PM notification via BDC write-back.
    In production this calls the BDC API Gateway / Joule endpoint.
    """
    log.info(
        f"[SAP-STUB] Would create SAP PM notification for alert={alert_id} "
        f"esp={row['esp_id']} risk={row['risk_bucket']}"
    )
    # Example (pseudo):
    # sap_client.create_notification(
    #     equipment_id = lookup_sap_equipment(row["esp_id"]),
    #     notif_type   = "M1",   # Maintenance request
    #     priority     = "1" if row["risk_bucket"] == "HIGH" else "2",
    #     short_text   = f"AI alert: {row['risk_bucket']} failure risk",
    #     long_text    = f"ML risk score {row['failure_risk_score']:.3f}. "
    #                    f"Top features: {row.get('top_feature_1')}, {row.get('top_feature_2')}",
    # )


def run():
    wc    = get_wc()
    wh_id = get_warehouse_id(wc)
    log.info(f"Alert monitor started | warehouse={wh_id} | poll_interval={POLL_INTERVAL_S}s")

    # Start from 1 hour ago to catch recent predictions
    since_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    while True:
        try:
            predictions = read_new_predictions(wc, wh_id, since_ts)
            if predictions:
                log.info(f"Found {len(predictions)} new HIGH/MEDIUM predictions")

            conn = pg_conn()
            alerts_created = 0
            for row in predictions:
                esp_id     = row["esp_id"]
                risk_bucket = row["risk_bucket"]

                if alert_exists(conn, esp_id, risk_bucket, window_h=DEDUP_WINDOW_H):
                    log.debug(f"Dedup: skipping {esp_id} {risk_bucket} (alert exists)")
                    continue

                alert_id = create_alert(conn, row)
                if alert_id:
                    log.info(f"Created alert {alert_id}  esp={esp_id}  risk={risk_bucket}  "
                             f"score={row['failure_risk_score']}")
                    maybe_create_sap_notification(alert_id, row)
                    alerts_created += 1

            conn.close()

            if predictions:
                # Advance watermark to last processed prediction_ts
                since_ts = predictions[-1]["prediction_ts"]
                log.info(f"Watermark advanced to {since_ts}. Alerts created: {alerts_created}")

        except KeyboardInterrupt:
            log.info("Alert monitor stopped by user.")
            break
        except Exception as e:
            log.error(f"Alert monitor error: {e}", exc_info=True)

        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    run()
