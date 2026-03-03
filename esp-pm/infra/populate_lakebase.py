"""
infra/populate_lakebase.py
---------------------------
Seeds Lakebase with realistic test data for demo purposes:
  - 15 esp_alerts (mix of NEW/ACK/IN_PROGRESS/CLOSED)
  - 8 esp_work_orders (linked to alerts)
  - 20 esp_alert_comments
  - UI config defaults (idempotent)
  - 2 chat sessions with sample messages

Run locally or from a Databricks notebook:
    python populate_lakebase.py
"""

import os
import uuid
import random
from datetime import datetime, timezone, timedelta

import psycopg2
import psycopg2.extras

PG_HOST     = os.getenv("PGHOST",     "localhost")
PG_PORT     = int(os.getenv("PGPORT", "5432"))
PG_DB       = os.getenv("PGDATABASE", "esp_pm_app")
PG_USER     = os.getenv("PGUSER",     "postgres")
PG_PASSWORD = os.getenv("PGPASSWORD", "")

ESP_IDS = [f"ESP-WELL-{str(i).zfill(4)}" for i in range(1, 11)]
USERS   = ["alice.operator", "bob.engineer", "charlie.tech", "system"]

random.seed(42)


def conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
        connect_timeout=10, sslmode="require",
    )


def random_ts(days_back: int = 30) -> datetime:
    delta = timedelta(seconds=random.randint(0, days_back * 86400))
    return datetime.now(timezone.utc) - delta


def seed_alerts(cur) -> list[str]:
    alert_ids = []
    buckets = ["HIGH"] * 5 + ["MEDIUM"] * 7 + ["LOW"] * 3
    statuses = ["NEW"] * 6 + ["ACK"] * 4 + ["IN_PROGRESS"] * 3 + ["CLOSED"] * 2
    random.shuffle(statuses)

    for i, (bucket, status) in enumerate(zip(buckets, statuses)):
        alert_id  = str(uuid.uuid4())
        esp_id    = random.choice(ESP_IDS)
        pred_ts   = random_ts(7)
        score     = random.uniform(0.65, 0.98) if bucket == "HIGH" else \
                    random.uniform(0.30, 0.65) if bucket == "MEDIUM" else \
                    random.uniform(0.05, 0.30)
        priority  = score * 0.6 + random.uniform(0.1, 0.4) * 0.4
        ack_by    = random.choice(USERS[:3]) if status != "NEW" else None
        ack_ts    = random_ts(3) if status != "NEW" else None
        lead_time = random.uniform(12, 72) if status == "CLOSED" else None
        sap_id    = f"PM{random.randint(1000000, 9999999)}" if status in ("SYNCED_TO_SAP", "CLOSED") else None

        cur.execute("""
            INSERT INTO esp_alerts
              (alert_id, esp_id, prediction_ts, failure_risk_score, risk_bucket,
               priority_score, status, acknowledged_by, acknowledged_ts,
               lead_time_hours, sap_order_id, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'system')
            ON CONFLICT (alert_id) DO NOTHING
        """, (alert_id, esp_id, pred_ts, score, bucket, priority, status,
              ack_by, ack_ts, lead_time, sap_id))
        alert_ids.append((alert_id, esp_id, status))

    print(f"  Seeded {len(alert_ids)} alerts")
    return alert_ids


def seed_work_orders(cur, alerts: list[tuple]):
    open_alerts = [(aid, eid) for aid, eid, st in alerts if st in ("ACK", "IN_PROGRESS")]
    wo_statuses = ["DRAFT", "REQUESTED", "SYNCED_TO_SAP", "COMPLETED", "CANCELLED"]
    created = 0

    for i in range(min(8, len(open_alerts))):
        alert_id, esp_id = open_alerts[i % len(open_alerts)]
        wo_status = random.choice(wo_statuses)
        planned_start = random_ts(10)
        planned_end   = planned_start + timedelta(hours=random.randint(4, 48))
        est_cost      = round(random.uniform(5000, 50000), 2)

        cur.execute("""
            INSERT INTO esp_work_orders
              (esp_id, alert_id, description, suggested_action, status,
               created_by, assigned_to, planned_start_ts, planned_end_ts,
               estimated_downtime_hours, estimated_cost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            esp_id, alert_id,
            f"Inspect and service {esp_id} following high-risk prediction.",
            "Pull ESP for bearing inspection. Check motor winding insulation resistance. "
            "Replace mechanical seal if vibration elevated.",
            wo_status,
            random.choice(USERS[:3]),
            "crew-alpha" if i % 2 == 0 else "crew-bravo",
            planned_start, planned_end,
            round(random.uniform(4, 24), 1),
            est_cost,
        ))
        created += 1

    print(f"  Seeded {created} work orders")


def seed_comments(cur, alerts: list[tuple]):
    templates = [
        "Reviewed sensor data — elevated vibration consistent with bearing wear.",
        "Ordered replacement mechanical seal. ETA 2 days.",
        "Crew dispatched to site. Well shut in for maintenance.",
        "Motor pulling unit on site. Beginning extraction.",
        "ESP pulled — confirmed bearing failure on thrust stage.",
        "New pump installed and tested. Well back on production.",
        "Monitoring closely. Will reassess in 24h if conditions persist.",
        "Coordinated with SAP PM team to create corrective order.",
    ]
    created = 0
    for alert_id, _, _ in random.sample(alerts, min(10, len(alerts))):
        for _ in range(random.randint(1, 3)):
            cur.execute("""
                INSERT INTO esp_alert_comments (alert_id, author, body)
                VALUES (%s, %s, %s)
            """, (alert_id, random.choice(USERS[:3]), random.choice(templates)))
            created += 1
    print(f"  Seeded {created} comments")


def seed_chat(cur):
    session_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO esp_ai_chat_sessions (session_id, user_id, esp_id)
        VALUES (%s, 'alice.operator', 'ESP-WELL-0003')
        ON CONFLICT DO NOTHING
    """, (session_id,))

    messages = [
        ("user", "Why is ESP-WELL-0003 showing elevated risk today?"),
        ("assistant",
         "ESP-WELL-0003 has a failure_risk_score of 0.72 (HIGH). "
         "The top contributing SHAP features are:\n"
         "1. **vibration_std_1h** (0.31): Vibration variability is significantly above baseline, "
         "suggesting early-stage mechanical wear.\n"
         "2. **days_since_last_preventive** (0.18): Last PM order was 87 days ago — "
         "approaching the recommended 90-day interval.\n"
         "3. **current_roc_10m** (0.14): Current draw is trending upward, consistent with "
         "increased drag from worn bearings.\n\n"
         "**Recommendation:** Schedule a visual inspection within 48h and prepare a PM work order. "
         "Critical spare parts (mechanical seal) are confirmed in stock at Plant 1001."),
        ("user", "What spare parts should I pre-stage?"),
        ("assistant",
         "Based on the failure signature (vibration + current trend), pre-stage the following:\n"
         "- **Mechanical seal kit** (SAP: 4000123) — 1 unit\n"
         "- **Thrust bearing assembly** (SAP: 4000456) — 1 set\n"
         "- **Motor protector** (SAP: 4000789) — 1 unit (precautionary)\n\n"
         "All three are currently in stock at Plant 1001 (confirmed via SAP MM). "
         "Estimated downtime if pulled now: 16–24h."),
    ]
    for role, content in messages:
        cur.execute("""
            INSERT INTO esp_ai_chat_messages (session_id, role, content, model_version)
            VALUES (%s, %s, %s, 'databricks-claude-sonnet-4-5')
        """, (session_id, role, content))

    print(f"  Seeded 1 chat session with {len(messages)} messages")


def main():
    print("Connecting to Lakebase...")
    try:
        c = conn()
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure PGHOST, PGUSER, PGPASSWORD, PGDATABASE are set.")
        return

    with c:
        with c.cursor() as cur:
            print("Seeding alerts...")
            alerts = seed_alerts(cur)
            print("Seeding work orders...")
            seed_work_orders(cur, alerts)
            print("Seeding comments...")
            seed_comments(cur, alerts)
            print("Seeding chat history...")
            seed_chat(cur)

    c.close()
    print("\nLakebase seed complete!")


if __name__ == "__main__":
    main()
