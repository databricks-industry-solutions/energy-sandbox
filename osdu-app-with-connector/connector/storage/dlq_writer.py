"""Dead Letter Queue writer — captures failed records and pages into a Delta table."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from connector.models.config import ConnectorRuntimeConfig

logger = logging.getLogger(__name__)


class DLQWriter:
    """Append failed records/pages to a DLQ Delta table for later inspection and replay."""

    def __init__(self, spark: Any, runtime: ConnectorRuntimeConfig) -> None:
        self._spark = spark
        self._runtime = runtime
        self._ensured = False

    def _fqn(self) -> str:
        d = self._runtime.delta
        return f"{d.catalog}.{d.schema_name}.adme_osdu_dlq"

    def ensure_table(self) -> None:
        if self._ensured:
            return
        fqn = self._fqn()
        self._spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {fqn} (
              dlq_id STRING NOT NULL,
              domain STRING NOT NULL,
              error_type STRING NOT NULL,
              error_message STRING,
              raw_payload STRING,
              source_cursor STRING,
              request_path STRING,
              failed_at TIMESTAMP NOT NULL,
              retry_count INT DEFAULT 0
            )
            USING DELTA
            TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
        """)
        self._ensured = True

    def write_failed_record(
        self,
        domain: str,
        record: dict[str, Any],
        error: Exception,
        *,
        source_cursor: Optional[str] = None,
    ) -> None:
        from pyspark.sql import Row

        self.ensure_table()
        now = datetime.now(timezone.utc)
        row = Row(
            dlq_id=str(uuid.uuid4()),
            domain=domain,
            error_type=type(error).__name__,
            error_message=str(error)[:2000],
            raw_payload=json.dumps(record, default=str)[:50000],
            source_cursor=source_cursor,
            request_path=None,
            failed_at=now,
            retry_count=0,
        )
        df = self._spark.createDataFrame([row])
        df.write.format("delta").mode("append").saveAsTable(self._fqn())
        logger.warning("DLQ: record failed", extra={"structured": {"domain": domain, "error": str(error)[:200]}})

    def write_failed_page(
        self,
        domain: str,
        error: Exception,
        *,
        request_path: Optional[str] = None,
        source_cursor: Optional[str] = None,
        page_payload: Optional[str] = None,
    ) -> None:
        from pyspark.sql import Row

        self.ensure_table()
        now = datetime.now(timezone.utc)
        row = Row(
            dlq_id=str(uuid.uuid4()),
            domain=domain,
            error_type=type(error).__name__,
            error_message=str(error)[:2000],
            raw_payload=(page_payload or "")[:50000],
            source_cursor=source_cursor,
            request_path=request_path,
            failed_at=now,
            retry_count=0,
        )
        df = self._spark.createDataFrame([row])
        df.write.format("delta").mode("append").saveAsTable(self._fqn())
        logger.error("DLQ: page failed", extra={"structured": {"domain": domain, "error": str(error)[:200]}})
