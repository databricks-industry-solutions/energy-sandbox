-- Optional ACL-style mirror (often mock until a stable Record/Storage ACL API is integrated).

CREATE TABLE IF NOT EXISTS <catalog>.<schema>.gov_record_acl_mirror (
  object_id STRING NOT NULL,
  resource_type STRING NOT NULL,
  principal_id STRING NOT NULL,
  privilege STRING NOT NULL,
  data_partition_id STRING NOT NULL,
  raw_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL,
  source STRING NOT NULL
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
