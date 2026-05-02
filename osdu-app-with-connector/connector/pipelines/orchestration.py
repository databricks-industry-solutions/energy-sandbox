"""End-to-end domain ingestion: extract -> bronze -> silver -> checkpoint, with DLQ and metrics."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connector.auth.auth_provider import AuthProvider
from connector.clients.adme_api import ADMEApiClient
from connector.domains.normalize import max_watermark_from_records
from connector.models.config import ConnectorRuntimeConfig, DomainConfig, LoadType, TableLayout
from connector.storage.checkpoint import CheckpointStore, DeltaCheckpointStore
from connector.storage.delta_writer import BronzeWriter, SilverWriter

logger = logging.getLogger(__name__)


class DomainIngestionRunner:
    """
    Orchestrates one domain run with error handling, DLQ, and metrics.

    Lakeflow Connect / DLT: replace this class with pipeline nodes that call the same
    stages (auth refresh, HTTP extract, Delta merge) inside ``@dlt.table`` or Auto Loader flows.
    """

    def __init__(
        self,
        runtime: ConnectorRuntimeConfig,
        auth: AuthProvider,
        checkpoint: CheckpointStore,
        *,
        spark: Optional[Any] = None,
    ) -> None:
        self._runtime = runtime
        self._auth = auth
        self._checkpoint = checkpoint
        self._spark = spark
        self._client: Optional[ADMEApiClient] = None
        self._bronze: Optional[BronzeWriter] = None
        self._silver: Optional[SilverWriter] = None
        self._dlq = None
        self._metrics = None

    def _ensure_delta(self, domain: DomainConfig) -> None:
        if self._spark is None:
            raise ValueError("SparkSession required for Delta bronze/silver writes")
        if self._bronze is None:
            self._bronze = BronzeWriter(self._spark, self._runtime)
        if self._silver is None:
            self._silver = SilverWriter(self._spark, self._runtime)
        assert self._bronze is not None
        assert self._silver is not None
        self._bronze.ensure_table(domain)
        self._silver.ensure_table(domain)

    def _ensure_dlq(self) -> None:
        if self._spark is None:
            return
        if self._dlq is None:
            from connector.storage.dlq_writer import DLQWriter
            self._dlq = DLQWriter(self._spark, self._runtime)

    def _ensure_metrics(self) -> None:
        if self._spark is None:
            return
        if self._metrics is None:
            from connector.storage.metrics_writer import MetricsWriter
            self._metrics = MetricsWriter(self._spark, self._runtime)

    def run(
        self,
        domain: DomainConfig,
        *,
        load_type: Optional[LoadType] = None,
        max_pages: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Run extraction and optional Delta writes.

        ``max_pages`` caps pagination (smoke tests); None means full pagination.
        """
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()

        if isinstance(self._checkpoint, DeltaCheckpointStore) and self._runtime.delta.table_layout == TableLayout.unified:
            self._checkpoint.ensure_table()

        lt = load_type or self._runtime.load_type
        load_full = lt == LoadType.full
        wm_before = None if load_full else self._checkpoint.get_watermark(domain.name)

        total_records: List[Dict[str, Any]] = []
        pages = 0
        rows_bronze = 0
        rows_silver = 0
        rows_failed = 0
        status = "SUCCESS"

        self._ensure_dlq()
        self._ensure_metrics()

        try:
            with ADMEApiClient(self._runtime, self._auth) as client:
                self._client = client
                for page in client.iter_domain_pages(
                    domain,
                    watermark=wm_before,
                    load_full=load_full,
                ):
                    good_records = []
                    for rec in page.records:
                        try:
                            good_records.append(rec)
                        except Exception as rec_err:
                            rows_failed += 1
                            if self._dlq:
                                try:
                                    self._dlq.write_failed_record(
                                        domain.name, rec, rec_err,
                                        source_cursor=page.next_cursor,
                                    )
                                except Exception:
                                    logger.exception("Failed to write to DLQ")

                    total_records.extend(good_records)
                    pages += 1

                    if self._spark is not None and good_records:
                        self._ensure_delta(domain)
                        assert self._bronze is not None
                        b_count = self._bronze.write_batch(
                            domain,
                            good_records,
                            request_path=domain.extraction.path,
                            request_method=domain.extraction.method,
                            http_status=200,
                            source_cursor=page.next_cursor,
                        )
                        rows_bronze += b_count

                        assert self._silver is not None
                        try:
                            s_count = self._silver.merge_batch(domain, good_records)
                            rows_silver += s_count
                        except Exception as silver_err:
                            rows_failed += len(good_records)
                            logger.error("Silver merge failed for page", exc_info=silver_err)
                            if self._dlq:
                                try:
                                    self._dlq.write_failed_page(
                                        domain.name, silver_err,
                                        request_path=domain.extraction.path,
                                        source_cursor=page.next_cursor,
                                    )
                                except Exception:
                                    logger.exception("Failed to write page error to DLQ")

                    if max_pages is not None and pages >= max_pages:
                        break

        except Exception as page_err:
            status = "FAILED"
            logger.error("Domain extraction failed", exc_info=page_err)
            if self._dlq:
                try:
                    self._dlq.write_failed_page(
                        domain.name, page_err,
                        request_path=domain.extraction.path,
                    )
                except Exception:
                    logger.exception("Failed to write extraction error to DLQ")

        wm_after = max_watermark_from_records(total_records, domain.incremental_field)
        if wm_after is None and total_records:
            wm_after = wm_before

        self._checkpoint.commit(
            domain.name,
            watermark=wm_after,
            load_type=lt.value,
            rows_ingested=len(total_records),
        )

        ended_at = datetime.now(timezone.utc)
        duration = time.monotonic() - t0

        if self._metrics:
            try:
                self._metrics.write(
                    domain=domain.name,
                    load_type=lt.value,
                    rows_extracted=len(total_records),
                    rows_bronze=rows_bronze,
                    rows_silver=rows_silver,
                    rows_failed=rows_failed,
                    pages=pages,
                    duration_seconds=duration,
                    watermark_before=wm_before,
                    watermark_after=wm_after,
                    started_at=started_at,
                    ended_at=ended_at,
                    status=status,
                )
            except Exception:
                logger.exception("Failed to write run metrics")

        logger.info(
            "domain ingest complete",
            extra={
                "structured": {
                    "domain": domain.name,
                    "pages": pages,
                    "rows": len(total_records),
                    "rows_bronze": rows_bronze,
                    "rows_silver": rows_silver,
                    "rows_failed": rows_failed,
                    "load_type": lt.value,
                    "watermark": wm_after,
                    "duration_s": round(duration, 2),
                    "status": status,
                }
            },
        )

        return {
            "domain": domain.name,
            "pages": pages,
            "rows": len(total_records),
            "rows_bronze": rows_bronze,
            "rows_silver": rows_silver,
            "rows_failed": rows_failed,
            "watermark": wm_after,
            "load_type": lt.value,
            "duration_seconds": round(duration, 2),
            "status": status,
        }
