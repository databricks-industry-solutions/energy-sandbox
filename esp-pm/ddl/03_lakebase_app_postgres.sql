-- ============================================================
-- DDL: Lakebase (PostgreSQL) — transactional app tables
-- ============================================================
-- Run against your Databricks Lakebase instance using psycopg2
-- or the Lakebase admin panel.  These tables back the alert &
-- work-order management flows in the Databricks App.
--
-- Connection: use the app's injected PGHOST/PGUSER/PGPASSWORD
--             (Lakebase resource binding).
-- Database:   esp_pm_app   (create first if it doesn't exist)
-- ============================================================

-- ── Extensions ───────────────────────────────────────────────
-- gen_random_uuid() for auto-generated UUIDs
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- esp_alerts
-- ============================================================
-- Created automatically when the inference job detects a new
-- HIGH or MEDIUM risk prediction.  Operators acknowledge and
-- create work orders from this table.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_alerts (
  alert_id              TEXT         PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  esp_id                TEXT         NOT NULL,
  prediction_ts         TIMESTAMPTZ  NOT NULL,
  failure_risk_score    DOUBLE PRECISION NOT NULL,
  risk_bucket           TEXT         NOT NULL CHECK (risk_bucket IN ('LOW','MEDIUM','HIGH')),
  priority_score        DOUBLE PRECISION,

  -- How early did we warn before the actual failure?
  -- NULL until the failure is confirmed (alert CLOSED with failure event)
  lead_time_hours       DOUBLE PRECISION,

  -- Workflow status
  status                TEXT         NOT NULL DEFAULT 'NEW'
                          CHECK (status IN ('NEW','ACK','IN_PROGRESS','CLOSED')),

  -- Who acted on it
  created_by            TEXT         NOT NULL DEFAULT 'system',
  acknowledged_by       TEXT,
  acknowledged_ts       TIMESTAMPTZ,

  -- SAP linkage — set when a work order is synced to SAP
  sap_order_id          TEXT,

  -- Free-text operator notes
  comments              TEXT,

  -- Standard audit
  created_ts            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_ts            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Indexes for the dashboard queries
CREATE INDEX IF NOT EXISTS esp_alerts_esp_id_idx
  ON esp_alerts (esp_id, prediction_ts DESC);

CREATE INDEX IF NOT EXISTS esp_alerts_status_idx
  ON esp_alerts (status, priority_score DESC)
  WHERE status IN ('NEW','ACK','IN_PROGRESS');   -- partial index for open alerts

CREATE INDEX IF NOT EXISTS esp_alerts_created_idx
  ON esp_alerts (created_ts DESC);

-- Auto-update updated_ts on every row change
CREATE OR REPLACE FUNCTION _set_updated_ts()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_ts = NOW();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER esp_alerts_updated_ts
  BEFORE UPDATE ON esp_alerts
  FOR EACH ROW EXECUTE FUNCTION _set_updated_ts();


-- ============================================================
-- esp_work_orders
-- ============================================================
-- Operator-created work orders, linked to alerts and optionally
-- synced to SAP PM orders via the BDC integration layer.
-- Status lifecycle:
--   DRAFT → REQUESTED → SYNCED_TO_SAP → COMPLETED
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_work_orders (
  work_order_id           TEXT         PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  esp_id                  TEXT         NOT NULL,
  alert_id                TEXT         REFERENCES esp_alerts (alert_id) ON DELETE SET NULL,

  -- Recommended action text (pre-populated by GenAI, editable by operator)
  suggested_action        TEXT,
  description             TEXT,        -- full operator description

  -- Workflow status
  status                  TEXT         NOT NULL DEFAULT 'DRAFT'
                            CHECK (status IN ('DRAFT','REQUESTED','SYNCED_TO_SAP','COMPLETED','CANCELLED')),

  -- Ownership
  created_by              TEXT         NOT NULL,
  assigned_to             TEXT,        -- technician or crew

  -- SAP cross-references
  sap_order_id            TEXT,        -- PM order number returned by SAP
  sap_notification_id     TEXT,        -- PM notification number

  -- Scheduling
  planned_start_ts        TIMESTAMPTZ,
  planned_end_ts          TIMESTAMPTZ,
  actual_start_ts         TIMESTAMPTZ,
  actual_end_ts           TIMESTAMPTZ,

  -- KPIs (estimated at creation time, actual filled on close)
  estimated_downtime_hours  DOUBLE PRECISION,
  estimated_cost            DOUBLE PRECISION,
  actual_downtime_hours     DOUBLE PRECISION,
  actual_cost               DOUBLE PRECISION,

  -- JSON blob for any extra SAP fields returned by integration
  sap_response_payload    JSONB,

  -- Standard audit
  created_ts              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_ts              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS esp_wo_esp_id_idx
  ON esp_work_orders (esp_id, created_ts DESC);

CREATE INDEX IF NOT EXISTS esp_wo_status_idx
  ON esp_work_orders (status, planned_start_ts)
  WHERE status NOT IN ('COMPLETED','CANCELLED');

CREATE INDEX IF NOT EXISTS esp_wo_alert_idx
  ON esp_work_orders (alert_id);

CREATE INDEX IF NOT EXISTS esp_wo_sap_order_idx
  ON esp_work_orders (sap_order_id)
  WHERE sap_order_id IS NOT NULL;

CREATE OR REPLACE TRIGGER esp_work_orders_updated_ts
  BEFORE UPDATE ON esp_work_orders
  FOR EACH ROW EXECUTE FUNCTION _set_updated_ts();


-- ============================================================
-- esp_alert_comments
-- ============================================================
-- Append-only comment log for alerts (full audit trail).
-- The esp_alerts.comments column holds the latest summary;
-- this table holds the full history.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_alert_comments (
  comment_id    TEXT         PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  alert_id      TEXT         NOT NULL REFERENCES esp_alerts (alert_id) ON DELETE CASCADE,
  author        TEXT         NOT NULL,
  body          TEXT         NOT NULL,
  created_ts    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS esp_alert_comments_alert_idx
  ON esp_alert_comments (alert_id, created_ts DESC);


-- ============================================================
-- esp_ui_configs
-- ============================================================
-- Per-user or per-org UI preferences and threshold overrides
-- (e.g. custom alert thresholds per plant, notification settings).
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_ui_configs (
  config_id       TEXT         PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  scope           TEXT         NOT NULL,   -- 'user' | 'plant' | 'global'
  scope_key       TEXT         NOT NULL,   -- username | plant code | 'default'
  config_key      TEXT         NOT NULL,
  config_value    TEXT         NOT NULL,
  updated_by      TEXT,
  updated_ts      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  UNIQUE (scope, scope_key, config_key)
);

-- Seed global defaults
INSERT INTO esp_ui_configs (scope, scope_key, config_key, config_value, updated_by)
VALUES
  ('global', 'default', 'alert_threshold_medium', '0.30',  'system'),
  ('global', 'default', 'alert_threshold_high',   '0.65',  'system'),
  ('global', 'default', 'default_time_window_days','7',    'system'),
  ('global', 'default', 'auto_create_alert_risk',  'MEDIUM','system'),
  ('global', 'default', 'lead_time_target_hours',  '48',   'system')
ON CONFLICT (scope, scope_key, config_key) DO NOTHING;


-- ============================================================
-- esp_ai_chat_sessions
-- ============================================================
-- Persists GenAI assistant conversation history per user/ESP,
-- enabling multi-turn context and interaction traceability.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_ai_chat_sessions (
  session_id    TEXT         PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id       TEXT         NOT NULL,
  esp_id        TEXT,                    -- NULL for general questions
  created_ts    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_ts    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS esp_ai_chat_messages (
  message_id    TEXT         PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  session_id    TEXT         NOT NULL REFERENCES esp_ai_chat_sessions (session_id) ON DELETE CASCADE,
  role          TEXT         NOT NULL CHECK (role IN ('user','assistant','system')),
  content       TEXT         NOT NULL,
  -- context snapshot embedded at query time for traceability
  context_snapshot  JSONB,
  model_version     TEXT,
  created_ts    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_messages_session_idx
  ON esp_ai_chat_messages (session_id, created_ts ASC);

CREATE OR REPLACE TRIGGER esp_chat_sessions_updated_ts
  BEFORE UPDATE ON esp_ai_chat_sessions
  FOR EACH ROW EXECUTE FUNCTION _set_updated_ts();
