-- ============================================================
-- 02_create_lakebase_schema.sql
-- Lakebase (managed Postgres) schema for the ROP Prediction App
--
-- Prerequisites:
--   1. Create a Lakebase instance named "drilling-demo-lakebase" in your
--      Databricks workspace (Compute → Lakebase → Create Instance)
--   2. Create a database "drilling_demo_app" inside the instance
--   3. Note the App role name from Lakebase → Roles and substitute
--      ${APP_ROLE} below (or use \set app_role '<role>' in psql).
--   4. Connect:  psql "$(databricks lakebase connection-string drilling-demo-lakebase)"
--
-- Run order: execute this file as the Lakebase owner/superuser.
-- ============================================================

-- ── Wells dimension ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wells (
  id       SERIAL       PRIMARY KEY,
  well_id  TEXT UNIQUE  NOT NULL,
  name     TEXT,
  field    TEXT         DEFAULT 'MSEEL',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed well records
INSERT INTO wells (well_id, name) VALUES
  ('MIP_3H', 'MSEEL MIP-3H Horizontal'),
  ('MIP_4H', 'MSEEL MIP-4H Horizontal')
ON CONFLICT (well_id) DO NOTHING;


-- ── Predictions (high-frequency streaming sink, partitioned by ingestion day) ─
-- Databricks streaming job bulk-inserts here via foreachBatch.
CREATE TABLE IF NOT EXISTS predictions (
  id          BIGSERIAL     PRIMARY KEY,
  well_id     TEXT          NOT NULL,
  ts          TIMESTAMPTZ   NOT NULL,
  md          DOUBLE PRECISION,
  rop_actual  DOUBLE PRECISION,
  rop_pred    DOUBLE PRECISION,
  rop_gap     DOUBLE PRECISION,                -- rop_pred - rop_actual
  mse         DOUBLE PRECISION,
  hazard_flag TEXT,
  created_at  TIMESTAMPTZ   DEFAULT NOW()
);

-- Composite index for well_id + time-range queries (Live Ops tab)
CREATE INDEX IF NOT EXISTS predictions_well_ts_idx
  ON predictions (well_id, ts DESC);

-- Partial index for fast "latest N points" lookup
CREATE INDEX IF NOT EXISTS predictions_well_recent_idx
  ON predictions (well_id, ts DESC)
  WHERE ts > NOW() - INTERVAL '24 hours';


-- ── Alerts (acknowledgeable events) ─────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
  id               BIGSERIAL   PRIMARY KEY,
  well_id          TEXT        NOT NULL,
  ts               TIMESTAMPTZ NOT NULL,
  alert_type       TEXT        NOT NULL,   -- INEFFICIENT_DRILLING | HIGH_MSE | STUCK_PIPE | …
  severity         TEXT        NOT NULL DEFAULT 'WARNING',  -- INFO | WARNING | CRITICAL
  message          TEXT,
  acknowledged     BOOLEAN     DEFAULT FALSE,
  acknowledged_by  TEXT,
  acknowledged_at  TIMESTAMPTZ,
  CONSTRAINT valid_severity CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL'))
);

CREATE INDEX IF NOT EXISTS alerts_well_unack_idx
  ON alerts (well_id, acknowledged, ts DESC);

CREATE INDEX IF NOT EXISTS alerts_active_idx
  ON alerts (acknowledged, ts DESC)
  WHERE acknowledged = FALSE;


-- ── Model registry mirror (optional read cache) ─────────────
-- Mirrors MLflow model version metadata so the app avoids
-- calling the MLflow API on every page load.
CREATE TABLE IF NOT EXISTS model_versions (
  id            SERIAL      PRIMARY KEY,
  model_name    TEXT        NOT NULL,
  version       TEXT        NOT NULL,
  stage         TEXT,                          -- Staging | Production | Archived
  rmse          DOUBLE PRECISION,
  r2            DOUBLE PRECISION,
  feature_list  TEXT,                          -- JSON array
  registered_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (model_name, version)
);


-- ── Grant access to the Databricks App service principal ─────
-- The Databricks App runtime injects PGUSER automatically;
-- that role is what you should substitute for ${APP_ROLE}.
-- Example:  \set app_role 'app_svc_rop_pred'

GRANT CONNECT ON DATABASE drilling_demo_app TO "${APP_ROLE}";
GRANT USAGE   ON SCHEMA public TO "${APP_ROLE}";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO "${APP_ROLE}";
GRANT USAGE, SELECT                  ON ALL SEQUENCES IN SCHEMA public TO "${APP_ROLE}";

-- Ensure future tables are accessible too
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES    TO "${APP_ROLE}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT                  ON SEQUENCES TO "${APP_ROLE}";
