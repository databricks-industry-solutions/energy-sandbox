-- Unified checkpoint: one row per ingest run per domain (append-only history).

CREATE TABLE IF NOT EXISTS <catalog>.<schema>.<checkpoint_table> (
  domain STRING NOT NULL,
  watermark STRING,
  last_run_utc TIMESTAMP NOT NULL,
  load_type STRING NOT NULL,
  rows_ingested BIGINT NOT NULL
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
