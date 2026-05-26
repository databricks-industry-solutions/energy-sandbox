-- ============================================================
-- DDL: las_viewer catalog — Unity Catalog assets for the
--      LAS Viewer petrophysics solution accelerator
-- ============================================================
-- Run on Databricks SQL or a cluster notebook.
-- The live curve store remains in Lakebase Postgres (operational
-- depth_logs table). Unity Catalog holds the governed metadata,
-- QC summaries, anomalies, and the processing-run audit trail —
-- the "gold layer" analytics assets that downstream consumers
-- (notebooks, BI, governance) should query.
-- ============================================================

-- ── Catalog & Schemas ────────────────────────────────────────
CREATE CATALOG IF NOT EXISTS las_viewer
  COMMENT 'LAS Viewer — petrophysics solution accelerator (gold-layer UC assets)';

CREATE SCHEMA IF NOT EXISTS las_viewer.gold
  COMMENT 'Governed well metadata, curve quality, anomalies, and processing audit trail';

-- ── MFG Industry Solutions tagging ───────────────────────────
-- Required by go/mfg/demo/rules so the demo is auto-discoverable
-- on the manufacturing landing page (go/industrials/outcomes).
ALTER SCHEMA las_viewer.gold SET TAGS (
  'mfg_subindustry'      = 'Oil & Gas Upstream',
  'mfg_outcome_usecase'  = 'Quality Event Root Cause Analysis'
);

-- ============================================================
-- las_viewer.gold.wells
-- ============================================================
-- Well master — durable metadata, geography, status. Mirrors the
-- Lakebase `las.wells` table but governed in UC for cross-tool
-- discovery and access control.
-- ============================================================
CREATE TABLE IF NOT EXISTS las_viewer.gold.wells (
  well_id          STRING         NOT NULL COMMENT 'Unique well identifier (e.g. WELL-001-A)',
  well_name        STRING         NOT NULL COMMENT 'Human-readable well name',
  field_name       STRING                  COMMENT 'Field (Blanco, Wamsutter, Midland, etc.)',
  basin            STRING                  COMMENT 'Producing basin',
  county           STRING                  COMMENT 'US county',
  state            STRING                  COMMENT 'US state',
  api_number       STRING                  COMMENT 'API well identifier (14-digit)',
  lat              DOUBLE                  COMMENT 'Surface location latitude',
  lon              DOUBLE                  COMMENT 'Surface location longitude',
  kb_elevation_ft  DOUBLE                  COMMENT 'Kelly bushing elevation, ft',
  total_depth_ft   DOUBLE                  COMMENT 'Total measured depth, ft',
  spud_date        DATE                    COMMENT 'Spud date',
  well_type        STRING                  COMMENT 'vertical | horizontal | deviated',
  status           STRING                  COMMENT 'raw | qc_complete | corrected | gold',
  quality_score    INT                     COMMENT 'Composite log quality score 0-100',
  curve_count      INT                     COMMENT 'Number of acquired curves',
  notes            STRING                  COMMENT 'Free-form analyst notes',
  ingest_ts        TIMESTAMP      NOT NULL COMMENT 'Time this well was first ingested into UC'
)
USING DELTA
COMMENT 'Governed well master — wells monitored by the LAS Viewer demo';

-- ============================================================
-- las_viewer.gold.curve_quality
-- ============================================================
-- Per-curve quality metrics produced by the QC engine. Drives
-- the QC dashboard and the petrophysical advisor.
-- ============================================================
CREATE TABLE IF NOT EXISTS las_viewer.gold.curve_quality (
  well_id          STRING         NOT NULL COMMENT 'FK to gold.wells.well_id',
  curve_name       STRING         NOT NULL COMMENT 'Curve / channel name (e.g. gr_raw, rhob_raw)',
  coverage_pct     DOUBLE                  COMMENT 'Non-null sample coverage, %',
  in_range_pct     DOUBLE                  COMMENT 'Samples within physical range, %',
  spike_count      INT                     COMMENT 'Spikes detected by 11-sample z-score filter',
  gap_count        INT                     COMMENT 'Gaps detected (null runs ≥ 3 samples)',
  quality_score    INT                     COMMENT 'Composite quality score 0-100',
  last_qc_ts       TIMESTAMP      NOT NULL COMMENT 'Last time QC was computed for this curve'
)
USING DELTA
COMMENT 'Per-curve quality metrics — feeds the Quality Event Root Cause workflow';

-- ============================================================
-- las_viewer.gold.anomalies
-- ============================================================
-- Detected curve / data quality anomalies — washouts, spikes,
-- karst features, missing acquisition. Each row is a quality
-- event that the analyst can root-cause through the app.
-- ============================================================
CREATE TABLE IF NOT EXISTS las_viewer.gold.anomalies (
  anomaly_id       BIGINT         NOT NULL COMMENT 'Surrogate primary key',
  well_id          STRING         NOT NULL COMMENT 'FK to gold.wells.well_id',
  curve_name       STRING         NOT NULL COMMENT 'Curve / channel affected',
  depth_start      DOUBLE                  COMMENT 'Anomaly start MD, ft',
  depth_end        DOUBLE                  COMMENT 'Anomaly end MD, ft',
  anomaly_type     STRING                  COMMENT 'washout | spike | curve_missing | karst | ...',
  severity         STRING                  COMMENT 'warning | critical',
  value            DOUBLE                  COMMENT 'Observed anomalous value where applicable',
  description      STRING                  COMMENT 'Analyst-readable root-cause hypothesis',
  detected_ts      TIMESTAMP      NOT NULL COMMENT 'Time the anomaly was flagged'
)
USING DELTA
COMMENT 'Quality events — anomalies detected on raw curves';

-- ============================================================
-- las_viewer.gold.processing_runs
-- ============================================================
-- Audit log of every processing recipe execution. Required for
-- traceability of derived petrophysical curves (vcl, phi_eff, sw).
-- ============================================================
CREATE TABLE IF NOT EXISTS las_viewer.gold.processing_runs (
  run_id           STRING         NOT NULL COMMENT 'Unique run identifier',
  well_id          STRING         NOT NULL COMMENT 'Well processed',
  recipe_id        STRING                  COMMENT 'Recipe applied (e.g. STD-PETRO-V1)',
  status           STRING                  COMMENT 'pending | running | complete | failed',
  started_ts       TIMESTAMP               COMMENT 'Run start time',
  completed_ts     TIMESTAMP               COMMENT 'Run completion time',
  metrics          STRING                  COMMENT 'JSON metrics blob (samples, spikes_corrected, etc.)',
  created_by       STRING                  COMMENT 'User or service principal who triggered the run'
)
USING DELTA
COMMENT 'Processing-run audit log — full traceability of derived curves';
