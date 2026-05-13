-- Unified layout: single bronze table for all domains (see delta.table_layout: unified).
-- Partitioned by domain and ingestion_date for retention and pruning.

CREATE TABLE IF NOT EXISTS <catalog>.<schema>.<bronze_table> (
  bronze_id STRING NOT NULL,
  domain STRING NOT NULL,
  ingestion_date STRING NOT NULL,
  raw_json STRING NOT NULL,
  ingestion_ts TIMESTAMP NOT NULL,
  request_path STRING,
  request_method STRING,
  http_status INT,
  source_cursor STRING,
  cluster_id STRING
)
USING DELTA
PARTITIONED BY (domain, ingestion_date)
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
