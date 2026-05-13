"""Bronze (structured + VARIANT) and silver (merged) Delta writers for Unity Catalog."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from connector.domains.normalize import normalize_record
from connector.models.config import (
    ArrayHandling,
    ConnectorRuntimeConfig,
    DomainConfig,
    FlattenMode,
    TableLayout,
)

logger = logging.getLogger(__name__)

# ── Spark SQL type string → PySpark DataType mapping ──

_SPARK_TYPE_MAP: dict[str, str] = {
    "STRING": "StringType",
    "INT": "IntegerType",
    "LONG": "LongType",
    "DOUBLE": "DoubleType",
    "BOOLEAN": "BooleanType",
}


def _pyspark_type(spark_sql: str):
    """Return a PySpark DataType instance from a Spark SQL type string."""
    from pyspark.sql import types as T

    name = _SPARK_TYPE_MAP.get(spark_sql)
    if name:
        return getattr(T, name)()
    return T.StringType()


class BronzeWriter:
    """Append raw API records to structured Bronze Delta tables.

    Each row contains:
    - ``raw_json`` STRING — full record as JSON string (backward compat / audit).
    - ``raw_variant`` — same record as VARIANT (8x faster path queries with ``:``).
    - Auto-exploded typed columns derived from schema inference.
    - ``_extra`` STRING — overflow JSON for unmapped fields.
    - Ingestion metadata columns.
    """

    def __init__(self, spark: Any, runtime: ConnectorRuntimeConfig) -> None:
        self._spark = spark
        self._runtime = runtime
        self._ensured: set[str] = set()
        self._variant_supported: Optional[bool] = None

    def _fqn(self, domain: DomainConfig) -> str:
        if self._runtime.delta.table_layout == TableLayout.per_domain:
            return self._runtime.delta.bronze_fqn(domain.name)
        return self._runtime.delta.bronze_fqn()

    def _check_variant_support(self) -> bool:
        """Detect whether the runtime supports VARIANT columns."""
        if self._variant_supported is not None:
            return self._variant_supported
        try:
            self._spark.sql("SELECT parse_json('{}')")
            self._variant_supported = True
        except Exception:
            self._variant_supported = False
            logger.info("VARIANT type not supported on this runtime; falling back to STRING")
        return self._variant_supported

    def ensure_table(self, domain: DomainConfig) -> None:
        """Create the Bronze table if needed, and add VARIANT / _extra columns if missing."""
        fqn = self._fqn(domain)
        if fqn in self._ensured:
            return

        norm = domain.normalization
        variant_ok = norm.include_variant and self._check_variant_support()

        try:
            self._spark.sql(f"""
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
            """)
        except Exception as e:
            if "DELTA_PROTOCOL_CHANGED" in str(e) or "already exists" in str(e).lower():
                logger.debug("bronze table concurrent create resolved: %s", e)
            else:
                raise

        existing_cols = set()
        try:
            existing_cols = {f.name.lower() for f in self._spark.table(fqn).schema.fields}
        except Exception:
            try:
                short_name = fqn.split(".", 1)[-1] if "." in fqn else fqn
                existing_cols = {f.name.lower() for f in self._spark.table(short_name).schema.fields}
            except Exception:
                pass

        needs_variant = variant_ok and "raw_variant" not in existing_cols
        needs_extra = norm.include_structured_columns and "_extra" not in existing_cols

        if not needs_variant and not needs_extra:
            self._ensured.add(fqn)
            return

        targets_to_try = [fqn]
        if "." in fqn:
            targets_to_try.append(fqn.split(".", 1)[-1])

        for alter_target in targets_to_try:
            try:
                if needs_variant:
                    try:
                        self._spark.sql(
                            f"ALTER TABLE {alter_target} SET TBLPROPERTIES "
                            f"('delta.feature.variantType-preview' = 'supported')"
                        )
                    except Exception:
                        pass

                add_cols = []
                if needs_variant:
                    add_cols.append("`raw_variant` VARIANT")
                if needs_extra:
                    add_cols.append("`_extra` STRING")

                self._spark.sql(f"ALTER TABLE {alter_target} ADD COLUMNS ({', '.join(add_cols)})")
                logger.info("bronze ensure_table: added columns %s to %s", add_cols, alter_target)
                break
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug("columns already present in %s", alter_target)
                    break
                logger.debug("ALTER TABLE %s failed: %s", alter_target, e)

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
        inferred_schema=None,
        flattener=None,
    ) -> int:
        """Write a batch of raw records to Bronze.

        If *inferred_schema* and *flattener* are provided, each row also gets
        auto-exploded typed columns and an ``_extra`` overflow field.
        """
        from pyspark.sql import Row
        from pyspark.sql.types import (
            IntegerType,
            StringType,
            StructField,
            StructType,
            TimestampType,
        )

        norm = domain.normalization
        use_variant = norm.include_variant and self._check_variant_support()
        use_structured = norm.include_structured_columns and inferred_schema and flattener

        now = datetime.now(timezone.utc)
        ingestion_date = now.strftime("%Y-%m-%d")
        cluster_id = self._spark.conf.get("spark.databricks.clusterUsageTags.clusterId", "")

        records_list = list(records)
        if not records_list:
            return 0

        rows = []
        for rec in records_list:
            raw_json_str = json.dumps(rec, default=str)
            row_dict: dict[str, Any] = {
                "bronze_id": str(uuid.uuid4()),
                "domain": domain.name,
                "raw_json": raw_json_str,
                "ingestion_ts": now,
                "request_path": request_path,
                "request_method": request_method,
                "http_status": http_status,
                "source_cursor": source_cursor,
                "cluster_id": cluster_id,
                "ingestion_date": ingestion_date,
            }

            if use_structured:
                flat, extra = flattener.flatten(rec)
                for col_name, value in flat.items():
                    row_dict[col_name] = value
                row_dict["_extra"] = json.dumps(extra, default=str) if extra else None

            rows.append(row_dict)

        # Build Spark schema dynamically
        base_fields = [
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

        if use_structured and inferred_schema:
            for fi in sorted(inferred_schema.leaf_fields().values(), key=lambda f: f.column_name):
                col_name = fi.column_name
                if col_name in {f.name for f in base_fields}:
                    continue
                spark_type = fi.spark_type
                if spark_type.startswith("ARRAY"):
                    base_fields.append(StructField(col_name, StringType(), True))
                else:
                    base_fields.append(StructField(col_name, _pyspark_type(spark_type), True))
            base_fields.append(StructField("_extra", StringType(), True))

        schema = StructType(base_fields)
        col_names = {f.name for f in base_fields}

        # Ensure all row dicts have all keys (pad missing with None)
        clean_rows = []
        for rd in rows:
            clean = {k: rd.get(k) for k in col_names}
            clean_rows.append(Row(**clean))

        fqn = self._fqn(domain)
        df = self._spark.createDataFrame(clean_rows, schema)

        if use_variant:
            df.createOrReplaceTempView("_bronze_staging")
            try:
                self._spark.sql(f"""
                    INSERT INTO {fqn}
                    SELECT *, parse_json(raw_json) AS raw_variant
                    FROM (
                        SELECT * FROM _bronze_staging
                    )
                """)
            except Exception as ve:
                logger.warning("VARIANT INSERT failed (%s), falling back to plain append", ve)
                df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(fqn)
            finally:
                try:
                    self._spark.catalog.dropTempView("_bronze_staging")
                except Exception:
                    pass
        else:
            df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(fqn)

        logger.info(
            "bronze append",
            extra={
                "structured": {
                    "domain": domain.name,
                    "rows": len(rows),
                    "table": fqn,
                    "structured_cols": len(col_names) - 10 if use_structured else 0,
                    "variant": use_variant,
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
