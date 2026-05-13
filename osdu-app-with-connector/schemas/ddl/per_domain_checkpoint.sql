-- Per-domain checkpoint: e.g. checkpoint_wellbore — watermark for that domain only.

CREATE TABLE IF NOT EXISTS <catalog>.<schema>.<checkpoint_table_for_domain> (
  watermark STRING,
  last_run_utc TIMESTAMP NOT NULL,
  load_type STRING NOT NULL,
  rows_ingested BIGINT NOT NULL
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
