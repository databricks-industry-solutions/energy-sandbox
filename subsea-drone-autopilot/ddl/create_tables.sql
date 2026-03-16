-- =============================================================
-- Subsea Drone Autopilot – Delta + Unity Catalog DDL
-- Catalog: oil_pump_monitor_catalog   |   Schema: subsea
-- =============================================================

-- Using existing catalog (no CREATE CATALOG permission on shared metastore)
-- CREATE SCHEMA IF NOT EXISTS oil_pump_monitor_catalog.subsea;

-- -----------------------------------------------------------
-- 1. drone_status  (current state of 5 drones)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS oil_pump_monitor_catalog.subsea.drone_status (
  drone_id              STRING        NOT NULL  COMMENT 'Logical drone identifier (DRONE-01..05)',
  battery_pct           DOUBLE        NOT NULL  COMMENT 'Current battery percentage 0–100',
  depth_m               DOUBLE                  COMMENT 'Current depth in meters (0 if surfaced)',
  health_score          DOUBLE        NOT NULL  COMMENT 'Composite health 0.0–1.0',
  last_heartbeat_ts     TIMESTAMP     NOT NULL  COMMENT 'Last telemetry heartbeat',
  current_mission_id    STRING                  COMMENT 'Active mission ID or NULL',
  maintenance_required  BOOLEAN       NOT NULL  DEFAULT false,
  state                 STRING        NOT NULL  COMMENT 'idle | in_mission | cooldown | maintenance'
)
USING DELTA
COMMENT 'Live status of each subsea inspection drone'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

-- -----------------------------------------------------------
-- 2. drone_limits  (per-drone capability envelope)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS oil_pump_monitor_catalog.subsea.drone_limits (
  drone_id                       STRING   NOT NULL,
  max_depth_m                    DOUBLE   NOT NULL,
  max_duration_min               DOUBLE   NOT NULL,
  min_battery_reserve_pct_low_risk   DOUBLE NOT NULL DEFAULT 30.0,
  min_battery_reserve_pct_med_risk   DOUBLE NOT NULL DEFAULT 40.0,
  min_battery_reserve_pct_high_risk  DOUBLE NOT NULL DEFAULT 50.0
)
USING DELTA
COMMENT 'Safety envelopes per drone model';

-- -----------------------------------------------------------
-- 3. telemetry_raw  (streaming ingest from drones)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS oil_pump_monitor_catalog.subsea.telemetry_raw (
  drone_id            STRING      NOT NULL,
  mission_id          STRING      NOT NULL,
  ts                  TIMESTAMP   NOT NULL,
  depth_m             DOUBLE,
  imu_roll_deg        DOUBLE,
  imu_pitch_deg       DOUBLE,
  imu_yaw_deg         DOUBLE,
  thruster_currents   STRING      COMMENT 'JSON array<double>',
  internal_temps_c    STRING      COMMENT 'JSON array<double>',
  network_rssi_dbm    DOUBLE,
  nav_error_m         DOUBLE
)
USING DELTA
PARTITIONED BY (drone_id)
COMMENT 'Raw per-second telemetry from drone missions';

-- -----------------------------------------------------------
-- 4. telemetry_features  (windowed aggregations + anomaly)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS oil_pump_monitor_catalog.subsea.telemetry_features (
  drone_id            STRING      NOT NULL,
  mission_id          STRING      NOT NULL,
  window_start_ts     TIMESTAMP   NOT NULL,
  window_end_ts       TIMESTAMP   NOT NULL,
  mean_depth_m        DOUBLE,
  peak_thruster_current_a DOUBLE,
  max_internal_temp_c DOUBLE,
  mean_nav_error_m    DOUBLE,
  comms_loss_fraction DOUBLE      COMMENT 'Fraction of window with RSSI < threshold',
  roll_std_deg        DOUBLE,
  pitch_std_deg       DOUBLE,
  anomaly_score       DOUBLE      COMMENT '0.0–1.0 from isolation-forest model',
  health_label        STRING      COMMENT 'normal | warning | critical'
)
USING DELTA
COMMENT 'Feature-engineered telemetry windows for anomaly detection';

-- -----------------------------------------------------------
-- 5. inspections  (mission-level records)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS oil_pump_monitor_catalog.subsea.inspections (
  mission_id      STRING      NOT NULL,
  asset_id        STRING      NOT NULL,
  asset_type      STRING      NOT NULL  COMMENT 'riser | mooring | manifold | flowline | fpso_hull',
  requested_by    STRING,
  start_ts        TIMESTAMP,
  end_ts          TIMESTAMP,
  status          STRING      NOT NULL  COMMENT 'requested | planned | launched | in_progress | completed | aborted | failed',
  summary_json    STRING      COMMENT 'Agent-generated summary JSON'
)
USING DELTA
COMMENT 'Inspection mission records';

-- -----------------------------------------------------------
-- 6. inspection_frames  (per-image records)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS oil_pump_monitor_catalog.subsea.inspection_frames (
  mission_id          STRING      NOT NULL,
  frame_id            STRING      NOT NULL,
  ts                  TIMESTAMP   NOT NULL,
  image_path          STRING      NOT NULL  COMMENT 'UC Volume path to image',
  depth_m             DOUBLE,
  camera_pose         STRING      COMMENT 'JSON {roll,pitch,yaw,x,y,z}',
  model_output_json   STRING      COMMENT 'JSON from vision model',
  severity_score      DOUBLE      COMMENT '0.0–1.0 defect severity'
)
USING DELTA
PARTITIONED BY (mission_id)
COMMENT 'Camera frames with ML inference outputs';

-- -----------------------------------------------------------
-- 7. autopilot_decisions  (agent audit trail)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS oil_pump_monitor_catalog.subsea.autopilot_decisions (
  decision_id       STRING      NOT NULL,
  ts                TIMESTAMP   NOT NULL,
  mission_id        STRING,
  decision_type     STRING      NOT NULL  COMMENT 'plan | launch | abort | refuse',
  input_json        STRING,
  tool_outputs_json STRING,
  final_plan_json   STRING
)
USING DELTA
COMMENT 'Full audit log of autopilot agent decisions';

-- -----------------------------------------------------------
-- Seed drone_status for 5 drones
-- -----------------------------------------------------------
INSERT INTO oil_pump_monitor_catalog.subsea.drone_status VALUES
  ('DRONE-01', 92.0, 0.0, 0.95, current_timestamp(), NULL, false, 'idle'),
  ('DRONE-02', 78.0, 0.0, 0.88, current_timestamp(), NULL, false, 'idle'),
  ('DRONE-03', 45.0, 0.0, 0.72, current_timestamp(), NULL, true,  'maintenance'),
  ('DRONE-04', 85.0, 0.0, 0.91, current_timestamp(), NULL, false, 'idle'),
  ('DRONE-05', 60.0, 0.0, 0.83, current_timestamp(), NULL, false, 'cooldown');

-- -----------------------------------------------------------
-- Seed drone_limits
-- -----------------------------------------------------------
INSERT INTO oil_pump_monitor_catalog.subsea.drone_limits VALUES
  ('DRONE-01', 500.0, 180.0, 30.0, 40.0, 50.0),
  ('DRONE-02', 500.0, 180.0, 30.0, 40.0, 50.0),
  ('DRONE-03', 300.0, 120.0, 30.0, 40.0, 50.0),
  ('DRONE-04', 500.0, 180.0, 30.0, 40.0, 50.0),
  ('DRONE-05', 1000.0, 240.0, 30.0, 40.0, 50.0);
