-- ============================================================
-- 01_create_lakehouse_tables.sql
-- Databricks Unity Catalog schemas and Delta tables
-- for MSEEL Real-Time ROP Prediction Demo
--
-- Run against your Unity Catalog:
--   %sql source /Workspace/.../infra/01_create_lakehouse_tables.sql
-- ============================================================

-- ── Bronze schema ─────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS drilling_demo_bronze
  COMMENT 'Raw ingested MSEEL drilling data (append-only, immutable)';

-- ── Silver schema ─────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS drilling_demo_silver
  COMMENT 'Cleaned, validated, and feature-engineered drilling data';

-- ── Gold schema ───────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS drilling_demo_gold
  COMMENT 'ML-ready features, real-time predictions, and aggregates';


-- ═══════════════════════════════════════════════════════════════
-- BRONZE LAYER: raw ingestion from MSEEL CSV files
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS drilling_demo_bronze.mseel_drilling_raw (
  well_id       STRING    COMMENT 'Well identifier derived from file name (e.g. MIP_3H)',
  ts_original   TIMESTAMP COMMENT 'Timestamp parsed from source CSV (nullable if malformed)',
  md            DOUBLE    COMMENT 'Measured Depth (ft)',
  tvd           DOUBLE    COMMENT 'True Vertical Depth (ft)',
  wob           DOUBLE    COMMENT 'Weight on Bit (klbs)',
  rpm           DOUBLE    COMMENT 'Rotary Speed (rpm)',
  torque        DOUBLE    COMMENT 'Surface Torque (ft-lbs)',
  spp           DOUBLE    COMMENT 'Standpipe Pressure (psi)',
  flow          DOUBLE    COMMENT 'Pump Flow Rate (gpm)',
  hookload      DOUBLE    COMMENT 'Hookload (klbs)',
  rop           DOUBLE    COMMENT 'Rate of Penetration (ft/hr)',
  rig_state     STRING    COMMENT 'Rig state code or description',
  _file         STRING    COMMENT 'Source file path for lineage',
  _ingest_ts    TIMESTAMP COMMENT 'Ingestion timestamp (UTC)'
)
USING DELTA
COMMENT 'Raw MSEEL drilling data — append-only, never modified after ingestion'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite'  = 'true',
  'delta.autoOptimize.autoCompact'    = 'true',
  'delta.columnMapping.mode'          = 'name',
  'delta.dataSkippingNumIndexedCols'  = '5'
);


-- ═══════════════════════════════════════════════════════════════
-- SILVER LAYER: cleaned and feature-enriched records
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS drilling_demo_silver.mseel_drilling_clean (
  well_id       STRING    COMMENT 'Well identifier',
  ts            TIMESTAMP COMMENT 'Canonical timestamp: coalesce(ts_original, _ingest_ts)',
  md            DOUBLE    COMMENT 'Measured Depth (ft)',
  tvd           DOUBLE    COMMENT 'True Vertical Depth (ft)',
  wob           DOUBLE    COMMENT 'Weight on Bit (klbs)',
  rpm           DOUBLE    COMMENT 'Rotary Speed (rpm)',
  torque        DOUBLE    COMMENT 'Surface Torque (ft-lbs)',
  spp           DOUBLE    COMMENT 'Standpipe Pressure (psi)',
  flow          DOUBLE    COMMENT 'Pump Flow Rate (gpm)',
  hookload      DOUBLE    COMMENT 'Hookload (klbs)',
  rop           DOUBLE    COMMENT 'Rate of Penetration (ft/hr)',
  rig_state     STRING    COMMENT 'Rig state',
  mse           DOUBLE    COMMENT 'Mechanical Specific Energy (psi) — Teale formula',
  d_rop_dt      DOUBLE    COMMENT 'Lag-based dROP/dt (ft/hr per minute)',
  d_torque_dt   DOUBLE    COMMENT 'Lag-based dTorque/dt (ft-lbs per minute)',
  d_spp_dt      DOUBLE    COMMENT 'Lag-based dSPP/dt (psi per minute)',
  window_id     TIMESTAMP COMMENT 'Minute-truncated timestamp for time-windowed aggregations'
)
USING DELTA
COMMENT 'Cleaned MSEEL drilling data with MSE and lag-derivative features'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'delta.columnMapping.mode'         = 'name'
);


-- ═══════════════════════════════════════════════════════════════
-- GOLD LAYER 1: ML training feature table
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS drilling_demo_gold.rop_features_train (
  well_id       STRING    COMMENT 'Well identifier (used for grouping, not a model feature)',
  ts            TIMESTAMP COMMENT 'Canonical timestamp',
  md            DOUBLE    COMMENT 'Measured Depth (ft) — proxy for formation depth',
  tvd           DOUBLE    COMMENT 'True Vertical Depth (ft)',
  wob           DOUBLE    COMMENT 'Weight on Bit (klbs)',
  rpm           DOUBLE    COMMENT 'Rotary Speed (rpm)',
  torque        DOUBLE    COMMENT 'Surface Torque (ft-lbs)',
  spp           DOUBLE    COMMENT 'Standpipe Pressure (psi)',
  flow          DOUBLE    COMMENT 'Pump Flow Rate (gpm)',
  hookload      DOUBLE    COMMENT 'Hookload (klbs)',
  mse           DOUBLE    COMMENT 'Mechanical Specific Energy (psi)',
  d_rop_dt      DOUBLE    COMMENT 'dROP/dt (ft/hr per min)',
  d_torque_dt   DOUBLE    COMMENT 'dTorque/dt (ft-lbs per min)',
  d_spp_dt      DOUBLE    COMMENT 'dSPP/dt (psi per min)',
  label_rop     DOUBLE    COMMENT 'TARGET: actual ROP (ft/hr) — the quantity we predict'
)
USING DELTA
COMMENT 'Gold feature table for ROP regression model training'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true'
);


-- ═══════════════════════════════════════════════════════════════
-- GOLD LAYER 2: streaming predictions output table
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS drilling_demo_gold.rop_predictions_stream (
  well_id       STRING    COMMENT 'Well identifier',
  ts            TIMESTAMP COMMENT 'Event timestamp from the drilling record',
  md            DOUBLE    COMMENT 'Measured Depth (ft)',
  rop_actual    DOUBLE    COMMENT 'Observed ROP (ft/hr)',
  rop_pred      DOUBLE    COMMENT 'ML-predicted optimal ROP (ft/hr)',
  rop_gap       DOUBLE    COMMENT 'rop_pred - rop_actual: positive = under-performing',
  mse           DOUBLE    COMMENT 'Mechanical Specific Energy (psi)',
  hazard_flag   STRING    COMMENT 'NORMAL | INEFFICIENT_DRILLING | HIGH_MSE | VIBRATION | STUCK_PIPE',
  _batch_id     BIGINT    COMMENT 'Structured Streaming micro-batch ID',
  _scored_ts    TIMESTAMP COMMENT 'Wall-clock time the record was scored'
)
USING DELTA
COMMENT 'Real-time ROP predictions and hazard classifications (streaming Delta sink)'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'delta.columnMapping.mode'         = 'name'
);
