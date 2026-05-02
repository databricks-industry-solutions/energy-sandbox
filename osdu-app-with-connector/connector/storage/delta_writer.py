"""Bronze (raw JSON) and silver (merged) Delta writers for Unity Catalog."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from connector.domains.normalize import normalize_record
from connector.models.config import ConnectorRuntimeConfig, DomainConfig, TableLayout

logger = logging.getLogger(__name__)


class BronzeWriter:
    """
    Append raw API records to bronze Delta: full JSON + ingestion metadata.

    Partitioning: ``domain``, ``ingestion_date`` (recommended for volume growth and retention).
    """

    def __init__(self, spark: Any, runtime: ConnectorRuntimeConfig) -> None:
        self._spark = spark
        self._runtime = runtime
        self._ensured: set[str] = set()

    def _fqn(self, domain: DomainConfig) -> str:
        if self._runtime.delta.table_layout == TableLayout.per_domain:
            return self._runtime.delta.bronze_fqn(domain.name)
        return self._runtime.delta.bronze_fqn()

    def ensure_table(self, domain: DomainConfig) -> None:
        fqn = self._fqn(domain)
        if fqn in self._ensured:
            return
        self._spark.sql(
            f"""
            CREATE TABLE IF NOT EXISTS {fqn} (
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
            TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
            """
        )
        self._ensured.add(fqn)

    def write_batch(
        self,
        domain: DomainConfig,
        records: Iterable[dict[str, Any]],
        *,
        request_path: str,
        request_method: str,
        http_status: int,
        source_cursor: Optional[str],
    ) -> int:
        from pyspark.sql import Row
        from pyspark.sql.types import (
            IntegerType,
            StringType,
            StructField,
            StructType,
            TimestampType,
        )

        now = datetime.now(timezone.utc)
        ingestion_date = now.strftime("%Y-%m-%d")
        rows = []
        for rec in records:
            rid = str(uuid.uuid4())
            rows.append(
                Row(
                    bronze_id=rid,
                    domain=domain.name,
                    raw_json=json.dumps(rec, default=str),
                    ingestion_ts=now,
                    request_path=request_path,
                    request_method=request_method,
                    http_status=http_status,
                    source_cursor=source_cursor,
                    cluster_id=self._spark.conf.get("spark.databricks.clusterUsageTags.clusterId", ""),
                    ingestion_date=ingestion_date,
                )
            )
        if not rows:
            return 0
        schema = StructType(
            [
                StructField("bronze_id", StringType(), False),
                StructField("domain", StringType(), False),
                StructField("raw_json", StringType(), False),
                StructField("ingestion_ts", TimestampType(), False),
                StructField("request_path", StringType(), True),
                StructField("request_method", StringType(), True),
                StructField("http_status", IntegerType(), True),
                StructField("source_cursor", StringType(), True),
                StructField("cluster_id", StringType(), True),
                StructField("ingestion_date", StringType(), False),
            ]
        )
        fqn = self._fqn(domain)
        df = self._spark.createDataFrame(rows, schema)
        df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(fqn)
        logger.info(
            "bronze append",
            extra={
                "structured": {
                    "domain": domain.name,
                    "rows": len(rows),
                    "table": fqn,
                }
            },
        )
        return len(rows)


class SilverWriter:
    """Merge normalized rows into silver (dedupe by record_id + latest modify_time)."""

    def __init__(self, spark: Any, runtime: ConnectorRuntimeConfig) -> None:
        self._spark = spark
        self._runtime = runtime
        self._ensured: set[str] = set()

    def _fqn(self, domain: DomainConfig) -> str:
        if self._runtime.delta.table_layout == TableLayout.per_domain:
            return self._runtime.delta.silver_fqn(domain.name)
        return self._runtime.delta.silver_fqn()

    def _unified(self) -> bool:
        return self._runtime.delta.table_layout == TableLayout.unified

    def ensure_table(self, domain: DomainConfig) -> None:
        fqn = self._fqn(domain)
        if fqn in self._ensured:
            return
        if self._unified():
            ddl = f"""
            CREATE TABLE IF NOT EXISTS {fqn} (
              domain STRING NOT NULL,
              record_id STRING NOT NULL,
              kind STRING,
              modify_time STRING,
              silver_payload STRING NOT NULL,
              ingested_at TIMESTAMP NOT NULL
            )
            USING DELTA
            TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
            """
        else:
            ddl = f"""
            CREATE TABLE IF NOT EXISTS {fqn} (
              record_id STRING NOT NULL,
              kind STRING,
              modify_time STRING,
              silver_payload STRING NOT NULL,
              ingested_at TIMESTAMP NOT NULL
            )
            USING DELTA
            TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
            """
        self._spark.sql(ddl)
        self._ensured.add(fqn)

    def _evolve_schema(self, fqn: str, incoming_fields: set[str]) -> None:
        """Add columns to the silver table for any new fields from the normalized payload."""
        try:
            existing_cols = {f.name.lower() for f in self._spark.table(fqn).schema.fields}
        except Exception:
            return
        new_cols = incoming_fields - existing_cols
        if not new_cols:
            return
        adds = ", ".join(f"`{c}` STRING" for c in sorted(new_cols))
        self._spark.sql(f"ALTER TABLE {fqn} ADD COLUMNS ({adds})")
        logger.info("schema evolution: added %d columns to %s: %s", len(new_cols), fqn, sorted(new_cols))

    def merge_batch(self, domain: DomainConfig, records: list[dict[str, Any]]) -> int:
        from pyspark.sql import Row
        from pyspark.sql.types import StringType, StructField, StructType, TimestampType

        now = datetime.now(timezone.utc)
        rows = []
        unified = self._unified()
        for raw in records:
            flat = normalize_record(raw, domain)
            rid = flat.get("record_id")
            if rid is None:
                continue
            if unified:
                rows.append(
                    Row(
                        domain=domain.name,
                        record_id=str(rid),
                        kind=flat.get("kind"),
                        modify_time=str(flat.get("modify_time") or ""),
                        silver_payload=json.dumps(flat, default=str),
                        ingested_at=now,
                    )
                )
            else:
                rows.append(
                    Row(
                        record_id=str(rid),
                        kind=flat.get("kind"),
                        modify_time=str(flat.get("modify_time") or ""),
                        silver_payload=json.dumps(flat, default=str),
                        ingested_at=now,
                    )
                )
        if not rows:
            return 0
        if unified:
            schema = StructType(
                [
                    StructField("domain", StringType(), False),
                    StructField("record_id", StringType(), False),
                    StructField("kind", StringType(), True),
                    StructField("modify_time", StringType(), True),
                    StructField("silver_payload", StringType(), False),
                    StructField("ingested_at", TimestampType(), False),
                ]
            )
        else:
            schema = StructType(
                [
                    StructField("record_id", StringType(), False),
                    StructField("kind", StringType(), True),
                    StructField("modify_time", StringType(), True),
                    StructField("silver_payload", StringType(), False),
                    StructField("ingested_at", TimestampType(), False),
                ]
            )
        fqn = self._fqn(domain)

        all_fields = set()
        for raw in records:
            flat = normalize_record(raw, domain)
            all_fields.update(k.lower() for k in flat.keys())
        self._evolve_schema(fqn, all_fields)

        df = self._spark.createDataFrame(rows, schema)
        tmp = f"_adme_silver_stg_{domain.name.replace('-', '_')}"
        df.createOrReplaceTempView(tmp)
        if unified:
            merge_sql = f"""
            MERGE INTO {fqn} t
            USING {tmp} s
            ON t.domain = s.domain AND t.record_id = s.record_id
            WHEN MATCHED AND (
              s.modify_time > t.modify_time
              OR (t.modify_time IS NULL AND s.modify_time IS NOT NULL)
            ) THEN
              UPDATE SET
                kind = s.kind,
                modify_time = s.modify_time,
                silver_payload = s.silver_payload,
                ingested_at = s.ingested_at
            WHEN NOT MATCHED THEN INSERT (
              domain, record_id, kind, modify_time, silver_payload, ingested_at
            ) VALUES (
              s.domain, s.record_id, s.kind, s.modify_time, s.silver_payload, s.ingested_at
            )
            """
        else:
            merge_sql = f"""
            MERGE INTO {fqn} t
            USING {tmp} s
            ON t.record_id = s.record_id
            WHEN MATCHED AND (
              s.modify_time > t.modify_time
              OR (t.modify_time IS NULL AND s.modify_time IS NOT NULL)
            ) THEN
              UPDATE SET
                kind = s.kind,
                modify_time = s.modify_time,
                silver_payload = s.silver_payload,
                ingested_at = s.ingested_at
            WHEN NOT MATCHED THEN INSERT (
              record_id, kind, modify_time, silver_payload, ingested_at
            ) VALUES (
              s.record_id, s.kind, s.modify_time, s.silver_payload, s.ingested_at
            )
            """
        self._spark.sql(merge_sql)
        logger.info(
            "silver merge",
            extra={"structured": {"domain": domain.name, "rows": len(rows), "table": fqn}},
        )
        return len(rows)
