-- Unified silver: deduplicated records; merge key (domain, record_id).

CREATE TABLE IF NOT EXISTS <catalog>.<schema>.<silver_table> (
  domain STRING NOT NULL,
  record_id STRING NOT NULL,
  kind STRING,
  modify_time STRING,
  silver_payload STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
