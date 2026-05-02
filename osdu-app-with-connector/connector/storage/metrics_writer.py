"""Run metrics writer — records per-domain ingestion stats into a Delta table."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from connector.models.config import ConnectorRuntimeConfig

logger = logging.getLogger(__name__)


class MetricsWriter:
    """Append one row per domain-run into adme_osdu_run_metrics for monitoring."""

    def __init__(self, spark: Any, runtime: ConnectorRuntimeConfig) -> None:
        self._spark = spark
        self._runtime = runtime
        self._ensured = False

    def _fqn(self) -> str:
        d = self._runtime.delta
        return f"{d.catalog}.{d.schema_name}.adme_osdu_run_metrics"

    def ensure_table(self) -> None:
        if self._ensured:
            return
        fqn = self._fqn()
        self._spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {fqn} (
              run_id STRING NOT NULL,
              domain STRING NOT NULL,
              load_type STRING NOT NULL,
              rows_extracted INT DEFAULT 0,
              rows_bronze INT DEFAULT 0,
              rows_silver INT DEFAULT 0,
              rows_failed INT DEFAULT 0,
              pages INT DEFAULT 0,
              duration_seconds DOUBLE,
              watermark_before STRING,
              watermark_after STRING,
              started_at TIMESTAMP NOT NULL,
              ended_at TIMESTAMP NOT NULL,
              status STRING DEFAULT 'SUCCESS'
            )
            USING DELTA
            TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
        """)
        self._ensured = True

    def write(
        self,
        *,
        domain: str,
        load_type: str,
        rows_extracted: int = 0,
        rows_bronze: int = 0,
        rows_silver: int = 0,
        rows_failed: int = 0,
        pages: int = 0,
        duration_seconds: float = 0.0,
        watermark_before: Optional[str] = None,
        watermark_after: Optional[str] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        status: str = "SUCCESS",
    ) -> None:
        from pyspark.sql import Row

        self.ensure_table()
        now = datetime.now(timezone.utc)
        row = Row(
            run_id=str(uuid.uuid4()),
            domain=domain,
            load_type=load_type,
            rows_extracted=rows_extracted,
            rows_bronze=rows_bronze,
            rows_silver=rows_silver,
            rows_failed=rows_failed,
            pages=pages,
            duration_seconds=round(duration_seconds, 2),
            watermark_before=watermark_before,
            watermark_after=watermark_after,
            started_at=started_at or now,
            ended_at=ended_at or now,
            status=status,
        )
        df = self._spark.createDataFrame([row])
        df.write.format("delta").mode("append").saveAsTable(self._fqn())
        logger.info(
            "metrics recorded",
            extra={"structured": {
                "domain": domain, "rows_extracted": rows_extracted,
                "rows_failed": rows_failed, "duration_s": round(duration_seconds, 2),
            }},
        )
