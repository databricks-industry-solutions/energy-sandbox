-- ============================================================
-- DDL: esp_ai catalog — Delta tables in Unity Catalog
-- ============================================================
-- Run on Databricks SQL or a cluster notebook.
-- All tables use Delta format with auto-optimize and Z-ORDER
-- hints where appropriate.
-- ============================================================

-- ── Catalog & Schemas ────────────────────────────────────────
CREATE CATALOG IF NOT EXISTS esp_ai
  COMMENT 'ESP Predictive Maintenance — all AI/ML and app-layer assets';

CREATE SCHEMA IF NOT EXISTS esp_ai.raw
  COMMENT 'Landing zone — raw ESP telemetry, exactly-once ingested';

CREATE SCHEMA IF NOT EXISTS esp_ai.ref
  COMMENT 'Reference / mapping tables — static or slowly-changing';

CREATE SCHEMA IF NOT EXISTS esp_ai.gold
  COMMENT 'Gold-layer features, labels, and ML predictions';

CREATE SCHEMA IF NOT EXISTS esp_ai.app
  COMMENT 'App-layer views over Lakebase transactional data (see 03_lakebase)';


-- ============================================================
-- esp_ai.raw.esp_telemetry_bronze
-- ============================================================
-- Append-only raw ingest from the ESP telemetry stream.
-- Columns match the wire schema; no transformations applied.
-- Partition by ingestion date for efficient time-based pruning.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_ai.raw.esp_telemetry_bronze (
  esp_id             STRING         NOT NULL COMMENT 'Unique ESP unit identifier (e.g. ESP-WELL-0042)',
  timestamp          TIMESTAMP      NOT NULL COMMENT 'Sensor reading timestamp (UTC)',
  pressure           DOUBLE         COMMENT 'Pump intake pressure, psi',
  temperature        DOUBLE         COMMENT 'Motor winding temperature, °C',
  current            DOUBLE         COMMENT 'Motor phase current, amperes',
  frequency          DOUBLE         COMMENT 'Drive frequency, Hz',
  vibration          DOUBLE         COMMENT 'Vibration magnitude, g (RMS)',
  flow_rate          DOUBLE         COMMENT 'Produced fluid flow rate, bbl/day',
  status             STRING         COMMENT 'Controller status code: RUNNING | TRIP | IDLE | SHUTDOWN',
  raw_payload        STRING         COMMENT 'Full raw JSON/Avro message for reprocessing lineage',
  -- audit columns added at ingest time
  _ingest_ts         TIMESTAMP      NOT NULL COMMENT 'Wall-clock time this row was written to Delta',
  _source_topic      STRING         COMMENT 'Kafka/Event Hub topic or replay tag',
  _batch_id          BIGINT         COMMENT 'Structured Streaming batch id for deduplication'
)
USING DELTA
PARTITIONED BY (DATE(timestamp))          -- daily partitions keep scans tight
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'delta.enableChangeDataFeed'       = 'true',   -- CDF for downstream streaming reads
  'pipelines.autoOptimize.managed'   = 'true'
)
COMMENT 'Bronze landing table — raw ESP sensor telemetry, append-only, never modified after write';


-- ============================================================
-- esp_ai.ref.esp_equipment_map
-- ============================================================
-- Bridge between ESP IDs (operational/telemetry) and SAP
-- equipment numbers / functional locations.
-- Maintained by the asset management team; use MERGE to upsert.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_ai.ref.esp_equipment_map (
  esp_id                  STRING   NOT NULL COMMENT 'Telemetry-side ESP identifier',
  equipment_id            STRING   NOT NULL COMMENT 'SAP equipment number (EQUNR) from PM module',
  functional_location_id  STRING   COMMENT 'SAP functional location (TPLNR)',
  plant                   STRING   COMMENT 'SAP plant code (WERKS)',
  field                   STRING   COMMENT 'Oil/gas field or production area name',
  well_name               STRING   COMMENT 'Well name or API number',
  commissioning_date      DATE     COMMENT 'Date ESP was commissioned / put in service',
  decommission_date       DATE     COMMENT 'Date ESP was decommissioned; NULL if still active',
  -- audit
  updated_ts              TIMESTAMP COMMENT 'Last upsert timestamp',
  updated_by              STRING    COMMENT 'User or job that last updated this row'
)
USING DELTA
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.enableChangeDataFeed'       = 'true'
)
COMMENT 'Reference mapping: ESP telemetry ID ↔ SAP equipment / functional location';


-- ============================================================
-- esp_ai.gold.esp_features
-- ============================================================
-- Feature store snapshot table.  One row per (esp_id, snapshot_ts).
-- Written by the feature engineering job (see notebooks/).
-- snapshot_ts = the trailing edge of the feature computation window.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_ai.gold.esp_features (
  esp_id                           STRING    NOT NULL,
  snapshot_ts                      TIMESTAMP NOT NULL,

  -- ── Telemetry: current ─────────────────────────────────────
  current_mean_1h                  DOUBLE    COMMENT 'Mean motor current, 1h trailing window, A',
  current_std_1h                   DOUBLE    COMMENT 'Std dev motor current, 1h window, A',
  current_mean_24h                 DOUBLE    COMMENT 'Mean motor current, 24h window, A',
  current_std_24h                  DOUBLE    COMMENT 'Std dev motor current, 24h window, A',
  current_roc_10m                  DOUBLE    COMMENT 'Rate of change of current, 10m window, A/min',

  -- ── Telemetry: pressure ────────────────────────────────────
  pressure_mean_1h                 DOUBLE    COMMENT 'Mean pump intake pressure, 1h window, psi',
  pressure_std_1h                  DOUBLE    COMMENT 'Std dev pump intake pressure, 1h window',
  pressure_roc_10m                 DOUBLE    COMMENT 'Rate of change of pressure, 10m window, psi/min',

  -- ── Telemetry: vibration ───────────────────────────────────
  vibration_std_1h                 DOUBLE    COMMENT 'Std dev vibration, 1h window, g',
  vibration_roc_10m                DOUBLE    COMMENT 'Rate of change of vibration, 10m window, g/min',

  -- ── Operational counters ───────────────────────────────────
  starts_last_24h                  INT       COMMENT 'Number of IDLE→RUNNING transitions in last 24h',
  trips_last_7d                    INT       COMMENT 'Number of trip/protection shutdowns in last 7d',
  minor_alarms_last_7d             INT       COMMENT 'Non-trip alarm events in last 7d',

  -- ── Physics-derived scores ─────────────────────────────────
  gaslock_score                    DOUBLE    COMMENT 'Gas-lock risk score [0..1]: high pressure_roc + low flow + high current',
  load_factor                      DOUBLE    COMMENT 'Ratio of actual current to nameplate FLA',
  operating_near_limits_flag       BOOLEAN   COMMENT 'True if current or frequency outside 90-110% of nameplate band',

  -- ── SAP/Maintenance features ───────────────────────────────
  days_since_last_preventive       DOUBLE    COMMENT 'Calendar days since last PM order (order_type=PM01/PM02)',
  days_since_last_corrective       DOUBLE    COMMENT 'Calendar days since last corrective order (CM/ZCM)',
  variance_from_recommended_interval DOUBLE  COMMENT 'Actual interval − recommended_interval_days; positive = overdue',
  callbacks_30d                    INT       COMMENT 'SAP notifications or orders created within 30d of last repair (repeat-visit proxy)',
  repeat_failure_same_cause_180d   INT       COMMENT 'Count of failures with the same symptom/cause code in last 180d',
  orders_per_runtime_hour_365d     DOUBLE    COMMENT 'Total maintenance orders / cumulative runtime hours in last 365d',
  average_mtbf_hours               DOUBLE    COMMENT 'Mean time between SAP failure events (breakdown_indicator=Y), hours',

  -- ── Cost features ──────────────────────────────────────────
  sum_actual_cost_365d             DOUBLE    COMMENT 'Total SAP actual order cost in last 365d, USD',
  sum_parts_cost_365d              DOUBLE    COMMENT 'Total parts (MM) cost component from orders in last 365d, USD',

  -- ── Parts availability ─────────────────────────────────────
  critical_parts_available         BOOLEAN   COMMENT 'True if ALL critical spare parts have on-hand stock > 0',
  num_critical_parts_available     INT       COMMENT 'Count of distinct critical part numbers with stock > 0',

  -- ── Audit ──────────────────────────────────────────────────
  feature_job_version              STRING    COMMENT 'Version tag of the feature engineering job that wrote this row'
)
USING DELTA
PARTITIONED BY (DATE(snapshot_ts))
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'delta.enableChangeDataFeed'       = 'true'
)
COMMENT 'Gold feature store — one row per ESP per snapshot; input to ML training and real-time inference';

-- Accelerate point lookups and the training join
-- (run after first load, or as part of the OPTIMIZE job)
-- OPTIMIZE esp_ai.gold.esp_features ZORDER BY (esp_id, snapshot_ts);


-- ============================================================
-- esp_ai.gold.esp_failure_labels
-- ============================================================
-- Ground-truth labels derived from SAP PM notifications /orders.
-- Joined with esp_features by the training pipeline.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_ai.gold.esp_failure_labels (
  esp_id             STRING    NOT NULL,
  snapshot_ts        TIMESTAMP NOT NULL COMMENT 'Feature snapshot this label corresponds to',
  label_failure_72h  INT       NOT NULL COMMENT '1 if an unplanned failure begins within 72h of snapshot_ts, else 0',
  failure_type       STRING    COMMENT 'Failure category: ELECTRICAL | HYDRAULIC | MECHANICAL | GAS_LOCK | OTHER | NULL if no failure',
  failure_start_ts   TIMESTAMP COMMENT 'Actual failure start (SAP notification failure_start_ts); NULL if label=0',
  failure_end_ts     TIMESTAMP COMMENT 'Actual failure end / repair completion; NULL if label=0 or still open',
  sap_notification_id STRING   COMMENT 'Source SAP notification id used to derive this label',
  label_version      STRING    COMMENT 'Label generation job version tag'
)
USING DELTA
PARTITIONED BY (DATE(snapshot_ts))
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true'
)
COMMENT 'Binary failure labels (72h horizon) derived from SAP PM breakdown notifications';


-- ============================================================
-- esp_ai.gold.esp_failure_predictions
-- ============================================================
-- Output of the real-time inference streaming job.
-- Consumed by the alert-generation logic and the app front-end.
-- ============================================================
CREATE TABLE IF NOT EXISTS esp_ai.gold.esp_failure_predictions (
  esp_id               STRING    NOT NULL,
  prediction_ts        TIMESTAMP NOT NULL COMMENT 'Timestamp at which inference was run',
  failure_risk_score   DOUBLE    NOT NULL COMMENT 'Model output probability [0..1] of failure within 72h',
  risk_bucket          STRING    NOT NULL COMMENT 'LOW (<0.3) | MEDIUM (0.3–0.65) | HIGH (>0.65)',
  priority_score       DOUBLE    COMMENT 'Composite score = f(risk, downtime_cost, parts_available) used for triage ordering',
  -- detail for explainability
  top_feature_1        STRING    COMMENT 'Name of highest-SHAP feature for this prediction',
  top_feature_2        STRING    COMMENT 'Name of second-highest SHAP feature',
  top_feature_3        STRING    COMMENT 'Name of third-highest SHAP feature',
  top_feature_1_value  DOUBLE    COMMENT 'SHAP contribution value for top_feature_1',
  top_feature_2_value  DOUBLE    COMMENT 'SHAP contribution value for top_feature_2',
  top_feature_3_value  DOUBLE    COMMENT 'SHAP contribution value for top_feature_3',
  model_version        STRING    COMMENT 'MLflow model version used (e.g. "3")',
  model_run_id         STRING    COMMENT 'MLflow run_id for full reproducibility'
)
USING DELTA
PARTITIONED BY (DATE(prediction_ts))
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'delta.enableChangeDataFeed'       = 'true'   -- alert job reads CDF to pick up new predictions
)
COMMENT 'Real-time failure risk predictions — one row per ESP per inference cycle';

-- OPTIMIZE esp_ai.gold.esp_failure_predictions ZORDER BY (esp_id, prediction_ts);
