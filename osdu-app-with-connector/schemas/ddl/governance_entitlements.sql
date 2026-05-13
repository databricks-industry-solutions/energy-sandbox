CREATE TABLE IF NOT EXISTS <catalog>.<schema>.gov_entitlements (
  group_id STRING NOT NULL,
  group_name STRING NOT NULL,
  description STRING NOT NULL,
  data_partition_id STRING NOT NULL,
  raw_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL,
  source STRING NOT NULL
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
