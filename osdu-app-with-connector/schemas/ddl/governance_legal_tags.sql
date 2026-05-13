CREATE TABLE IF NOT EXISTS <catalog>.<schema>.gov_legal_tags (
  legal_tag_name STRING NOT NULL,
  legal_tag_id STRING NOT NULL,
  is_valid BOOLEAN NOT NULL,
  data_partition_id STRING NOT NULL,
  obligations_json STRING,
  raw_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL,
  source STRING NOT NULL
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
