"""Per-domain ingestion watermarks (incremental state)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from connector.models.config import ConnectorRuntimeConfig, TableLayout


@dataclass
class CheckpointRow:
    domain: str
    watermark: Optional[str]
    last_run_utc: str
    load_type: str
    rows_ingested: int


class CheckpointStore(ABC):
    @abstractmethod
    def get_watermark(self, domain: str) -> Optional[str]:
        ...

    @abstractmethod
    def commit(
        self,
        domain: str,
        *,
        watermark: Optional[str],
        load_type: str,
        rows_ingested: int,
    ) -> None:
        ...


class MemoryCheckpointStore(CheckpointStore):
    """In-process store for unit tests and local runs."""

    def __init__(self) -> None:
        self._data: dict[str, CheckpointRow] = {}

    def get_watermark(self, domain: str) -> Optional[str]:
        row = self._data.get(domain)
        return row.watermark if row else None

    def commit(
        self,
        domain: str,
        *,
        watermark: Optional[str],
        load_type: str,
        rows_ingested: int,
    ) -> None:
        self._data[domain] = CheckpointRow(
            domain=domain,
            watermark=watermark,
            last_run_utc=datetime.now(timezone.utc).isoformat(),
            load_type=load_type,
            rows_ingested=rows_ingested,
        )

    def last(self, domain: str) -> Optional[CheckpointRow]:
        return self._data.get(domain)


class DeltaCheckpointStore(CheckpointStore):
    """
    Unity Catalog Delta checkpoint state.

    **Unified layout:** one table with a ``domain`` column (watermark per domain).
    **Per-domain layout:** one table per domain (e.g. ``checkpoint_wellbore``) without a ``domain`` column.

    Lakeflow / DLT can replace this with a pipeline-managed state table or ``FLOW_PROGRESS``.
    """

    def __init__(self, spark: Any, runtime: ConnectorRuntimeConfig) -> None:
        from pyspark.sql import SparkSession

        self._spark: SparkSession = spark
        self._runtime = runtime
        self._catalog = runtime.delta.catalog
        self._schema = runtime.delta.schema_name
        self._ensured: set[str] = set()

    def _per_domain(self) -> bool:
        return self._runtime.delta.table_layout == TableLayout.per_domain

    def _fqn(self, domain: str) -> str:
        if self._per_domain():
            return self._runtime.delta.checkpoint_fqn(domain)
        return self._runtime.delta.checkpoint_fqn()

    def ensure_table(self, domain: Optional[str] = None) -> None:
        """
        Ensure checkpoint table exists. For unified layout, ``domain`` is ignored (single table).
        For per-domain layout, pass the domain name (table ``checkpoint_<domain>``).
        """
        if self._per_domain():
            if not domain:
                return
            fqn = self._fqn(domain)
        else:
            fqn = self._runtime.delta.checkpoint_fqn()
        if fqn in self._ensured:
            return
        if self._per_domain():
            self._spark.sql(
                f"""
                CREATE TABLE IF NOT EXISTS {fqn} (
                  watermark STRING,
                  last_run_utc TIMESTAMP NOT NULL,
                  load_type STRING NOT NULL,
                  rows_ingested BIGINT NOT NULL
                )
                USING DELTA
                TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
                """
            )
        else:
            self._spark.sql(
                f"""
                CREATE TABLE IF NOT EXISTS {fqn} (
                  domain STRING NOT NULL,
                  watermark STRING,
                  last_run_utc TIMESTAMP NOT NULL,
                  load_type STRING NOT NULL,
                  rows_ingested BIGINT NOT NULL
                )
                USING DELTA
                TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
                """
            )
        self._ensured.add(fqn)

    def get_watermark(self, domain: str) -> Optional[str]:
        fqn = self._fqn(domain)
        if self._per_domain():
            self.ensure_table(domain)
            df = self._spark.sql(
                f"SELECT watermark FROM {fqn} ORDER BY last_run_utc DESC LIMIT 1"
            )
        else:
            self.ensure_table()
            safe = domain.replace("'", "''")
            df = self._spark.sql(
                f"SELECT watermark FROM {fqn} WHERE domain = '{safe}' ORDER BY last_run_utc DESC LIMIT 1"
            )
        rows = df.collect()
        if not rows:
            return None
        return rows[0]["watermark"]

    def commit(
        self,
        domain: str,
        *,
        watermark: Optional[str],
        load_type: str,
        rows_ingested: int,
    ) -> None:
        from pyspark.sql import Row
        from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

        fqn = self._fqn(domain)
        self.ensure_table(domain if self._per_domain() else None)

        now = datetime.now(timezone.utc)
        if self._per_domain():
            schema = StructType(
                [
                    StructField("watermark", StringType(), True),
                    StructField("last_run_utc", TimestampType(), False),
                    StructField("load_type", StringType(), False),
                    StructField("rows_ingested", LongType(), False),
                ]
            )
            row = Row(
                watermark=watermark,
                last_run_utc=now,
                load_type=load_type,
                rows_ingested=int(rows_ingested),
            )
        else:
            schema = StructType(
                [
                    StructField("domain", StringType(), False),
                    StructField("watermark", StringType(), True),
                    StructField("last_run_utc", TimestampType(), False),
                    StructField("load_type", StringType(), False),
                    StructField("rows_ingested", LongType(), False),
                ]
            )
            row = Row(
                domain=domain,
                watermark=watermark,
                last_run_utc=now,
                load_type=load_type,
                rows_ingested=int(rows_ingested),
            )
        df = self._spark.createDataFrame([row], schema)
        df.write.format("delta").mode("append").saveAsTable(fqn)
