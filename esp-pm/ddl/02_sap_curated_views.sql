-- ============================================================
-- DDL: sap_curated catalog — curated views over SAP BDC
--      Delta-shared tables
-- ============================================================
-- ARCHITECTURE NOTE:
--   SAP Business Data Cloud (BDC) exposes SAP PM & MM tables as
--   Delta Sharing data products. The sharing recipient (your
--   workspace) sees them as read-only Delta tables, typically
--   under a catalog like "sap_bdc_share".
--
--   Pattern used here:
--     1. Accept the Delta Share → raw tables land in sap_bdc_share.*
--     2. Create a separate "sap_curated" catalog with clean views
--        that apply consistent naming, types, and governance tags.
--
--   If BDC exposes tables in a different catalog/schema, adjust
--   the FROM clauses in the views below accordingly.
-- ============================================================

CREATE CATALOG IF NOT EXISTS sap_curated
  COMMENT 'Curated consumer layer over SAP BDC Delta-shared data products (PM + MM)';

CREATE SCHEMA IF NOT EXISTS sap_curated.pm
  COMMENT 'SAP Plant Maintenance curated views';

CREATE SCHEMA IF NOT EXISTS sap_curated.mm
  COMMENT 'SAP Materials Management curated views';


-- ============================================================
-- Assumption: raw BDC Delta Share tables land here.
-- Adjust to match your actual share/catalog name.
-- ============================================================
-- sap_bdc_share.plant_maintenance.equipment   → EQUI/EQUZ
-- sap_bdc_share.plant_maintenance.notifications → QMEL
-- sap_bdc_share.plant_maintenance.orders       → AUFK / AFKO
-- sap_bdc_share.materials_mgmt.materials       → MARA / MAKT
-- sap_bdc_share.materials_mgmt.stock           → MARD / MARDH


-- ============================================================
-- sap_curated.pm.equipment
-- ============================================================
-- Master equipment data (EQUI table equivalent).
-- Each row = one SAP equipment master record.
-- ============================================================
CREATE OR REPLACE VIEW sap_curated.pm.equipment
  COMMENT 'SAP PM Equipment master — curated from BDC Delta Share (EQUI/EQUZ)'
AS
SELECT
  CAST(equipment_id           AS STRING)    AS equipment_id,           -- EQUNR
  CAST(functional_location_id AS STRING)    AS functional_location_id, -- TPLNR
  CAST(plant                  AS STRING)    AS plant,                  -- WERKS
  CAST(equipment_type         AS STRING)    AS equipment_type,         -- EQTYP
  CAST(manufacturer           AS STRING)    AS manufacturer,           -- HERST
  CAST(model                  AS STRING)    AS model,                  -- TYPBZ
  CAST(install_date           AS DATE)      AS install_date,           -- INBDT
  CAST(decommission_date      AS DATE)      AS decommission_date,      -- STILLDT (nullable)
  CAST(status                 AS STRING)    AS status                  -- ISTAT / user-status text
FROM sap_bdc_share.plant_maintenance.equipment;


-- ============================================================
-- sap_curated.pm.notifications
-- ============================================================
-- PM notifications (QMEL / VIQMEL equivalent).
-- Unplanned (breakdown) notifications are the primary source
-- of failure ground-truth labels.
-- ============================================================
CREATE OR REPLACE VIEW sap_curated.pm.notifications
  COMMENT 'SAP PM Notifications — curated from BDC Delta Share (QMEL). Key label source for ML.'
AS
SELECT
  CAST(notification_id         AS STRING)    AS notification_id,          -- QMNUM
  CAST(equipment_id            AS STRING)    AS equipment_id,             -- EQUNR
  CAST(functional_location_id  AS STRING)    AS functional_location_id,   -- TPLNR
  CAST(notif_type              AS STRING)    AS notif_type,               -- QMART (M2=breakdown, M1=maintenance request)
  CAST(priority                AS STRING)    AS priority,                 -- PRIOK
  CAST(breakdown_indicator     AS BOOLEAN)   AS breakdown_indicator,      -- MSAUS = 'X'
  CAST(failure_start_ts        AS TIMESTAMP) AS failure_start_ts,         -- QMDAT + MZEIT
  CAST(failure_end_ts          AS TIMESTAMP) AS failure_end_ts,           -- AUFDT + MZEIT2 (nullable until repair)
  CAST(symptom_code            AS STRING)    AS symptom_code,             -- FEGRP + FECOD
  CAST(cause_code              AS STRING)    AS cause_code,               -- URSACHE
  CAST(created_ts              AS TIMESTAMP) AS created_ts,               -- ERDAT + ERZEIT
  CAST(status                  AS STRING)    AS status                    -- QMST user-status (OSNO/NOPR/NOCO etc.)
FROM sap_bdc_share.plant_maintenance.notifications;


-- ============================================================
-- sap_curated.pm.orders
-- ============================================================
-- PM maintenance orders (AUFK / AFKO equivalent).
-- Used for maintenance history features and cost roll-ups.
-- ============================================================
CREATE OR REPLACE VIEW sap_curated.pm.orders
  COMMENT 'SAP PM Orders — curated from BDC Delta Share (AUFK/AFKO). Source for maintenance features and costs.'
AS
SELECT
  CAST(order_id                AS STRING)      AS order_id,               -- AUFNR
  CAST(notification_id         AS STRING)      AS notification_id,        -- QMNUM (linked notification)
  CAST(equipment_id            AS STRING)      AS equipment_id,           -- EQUNR
  CAST(functional_location_id  AS STRING)      AS functional_location_id, -- TPLNR
  CAST(order_type              AS STRING)      AS order_type,             -- AUART (PM01=preventive, ZCM=corrective, etc.)
  CAST(priority                AS STRING)      AS priority,               -- PRIOK
  CAST(created_ts              AS TIMESTAMP)   AS created_ts,             -- ERDAT
  CAST(scheduled_start_ts      AS TIMESTAMP)   AS scheduled_start_ts,     -- GSTRS
  CAST(scheduled_end_ts        AS TIMESTAMP)   AS scheduled_end_ts,       -- GETRS
  CAST(actual_start_ts         AS TIMESTAMP)   AS actual_start_ts,        -- GSTRI (nullable until started)
  CAST(actual_end_ts           AS TIMESTAMP)   AS actual_end_ts,          -- GETRI (nullable until closed)
  CAST(status                  AS STRING)      AS status,                 -- AUFNR user-status / system-status
  CAST(planned_cost            AS DECIMAL(18,2)) AS planned_cost,         -- GEPLKOSTEN
  CAST(actual_cost             AS DECIMAL(18,2)) AS actual_cost           -- ISTKOST
FROM sap_bdc_share.plant_maintenance.orders;


-- ============================================================
-- sap_curated.mm.materials
-- ============================================================
-- Material master (MARA + MAKT equivalent).
-- Used to identify critical spare parts by material group.
-- ============================================================
CREATE OR REPLACE VIEW sap_curated.mm.materials
  COMMENT 'SAP MM Material master — curated from BDC Delta Share (MARA/MAKT)'
AS
SELECT
  CAST(material_id    AS STRING)        AS material_id,     -- MATNR
  CAST(material_desc  AS STRING)        AS material_desc,   -- MAKTX (language key = EN)
  CAST(material_group AS STRING)        AS material_group,  -- MATKL (e.g. ESP-CRITICAL, ESP-CONSUMABLE)
  CAST(uom            AS STRING)        AS uom,             -- MEINS base unit of measure
  CAST(standard_price AS DECIMAL(18,2)) AS standard_price   -- STPRS moving average or standard price
FROM sap_bdc_share.materials_mgmt.materials;


-- ============================================================
-- sap_curated.mm.stock
-- ============================================================
-- Plant / storage-location stock levels (MARD equivalent).
-- Joined in feature engineering to determine critical parts
-- availability before scheduling a repair.
-- ============================================================
CREATE OR REPLACE VIEW sap_curated.mm.stock
  COMMENT 'SAP MM Stock on hand — curated from BDC Delta Share (MARD). Used for parts-availability features.'
AS
SELECT
  CAST(material_id       AS STRING)        AS material_id,        -- MATNR
  CAST(plant             AS STRING)        AS plant,              -- WERKS
  CAST(storage_location  AS STRING)        AS storage_location,   -- LGORT
  CAST(batch             AS STRING)        AS batch,              -- CHARG (nullable for non-batch materials)
  CAST(quantity_on_hand  AS DECIMAL(18,2)) AS quantity_on_hand,   -- LABST (unrestricted use stock)
  CAST(valuation_type    AS STRING)        AS valuation_type      -- BWTAR
FROM sap_bdc_share.materials_mgmt.stock;


-- ============================================================
-- Helper view: critical materials list
-- ============================================================
-- Identifies materials in the "ESP-CRITICAL" material group.
-- Used in feature engineering to compute critical_parts_available.
-- Adjust material_group filter to match your SAP master data.
-- ============================================================
CREATE OR REPLACE VIEW sap_curated.mm.critical_materials
  COMMENT 'Filtered view of ESP critical spare parts (material_group = ESP-CRITICAL)'
AS
SELECT
  m.material_id,
  m.material_desc,
  m.uom,
  m.standard_price,
  s.plant,
  s.storage_location,
  COALESCE(s.quantity_on_hand, 0) AS quantity_on_hand,
  (COALESCE(s.quantity_on_hand, 0) > 0) AS in_stock
FROM sap_curated.mm.materials  m
LEFT JOIN sap_curated.mm.stock s USING (material_id)
WHERE m.material_group = 'ESP-CRITICAL';   -- adjust to match your data


-- ============================================================
-- Helper view: recent PM order history per equipment
-- ============================================================
-- Pre-aggregates the most common maintenance KPIs used in
-- feature engineering.  Refreshed as part of the feature job.
-- ============================================================
CREATE OR REPLACE VIEW sap_curated.pm.equipment_maintenance_summary
  COMMENT 'Pre-aggregated maintenance KPIs per equipment for feature engineering joins'
AS
SELECT
  equipment_id,
  MAX(CASE WHEN order_type IN ('PM01','PM02','ZPM') THEN actual_end_ts END) AS last_preventive_ts,
  MAX(CASE WHEN order_type IN ('ZCM','PM03','CM01') THEN actual_end_ts END) AS last_corrective_ts,
  SUM(CASE WHEN actual_end_ts >= DATEADD(YEAR, -1, CURRENT_TIMESTAMP())
           THEN CAST(actual_cost AS DOUBLE) END)                             AS sum_actual_cost_365d,
  COUNT(CASE WHEN actual_end_ts >= DATEADD(YEAR, -1, CURRENT_TIMESTAMP())
             THEN 1 END)                                                     AS order_count_365d
FROM sap_curated.pm.orders
GROUP BY equipment_id;
