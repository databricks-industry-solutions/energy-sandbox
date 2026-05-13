-- Per-domain silver (delta.table_layout: per_domain): table name silver_<domain>.
-- Domain is implicit in the table name; merge on record_id only.

CREATE TABLE IF NOT EXISTS <catalog>.<schema>.<silver_table_for_domain> (
  record_id STRING NOT NULL,
  kind STRING,
  modify_time STRING,
  silver_payload STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
