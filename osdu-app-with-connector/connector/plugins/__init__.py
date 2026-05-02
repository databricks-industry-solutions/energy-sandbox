"""
Extension hooks for Phase 2+ (seismic, ACZ/blob file materialization).

Planned additions (not implemented in Phase 1):

- **Seismic plug-in**: domain configs with binary staging, `seistore` paths, and
  volume-friendly layout (see `notebooks/DLT_ADME_ManagedIdentity_Token_Smoke.py` for token patterns).
- **Technical files**: resolve file pointers from storage records, copy to Unity Catalog
  Volumes or external locations, register metadata for Genie / dashboards.

**Streaming / near-real-time**

- Replace pull-based ``DomainIngestionRunner`` with a **Structured Streaming** or **Queues**
  source that enforces the same **auth refresh**, **HTTP extract**, and **Delta merge** stages.
- Keep ``ADMEApiClient`` and YAML ``DomainConfig`` as the single source of truth for query shape;
  swap only the scheduler (batch job → streaming query or micro-batch).

**Zero-copy / ADLS**

- For large binaries, land **file IDs + metadata** in bronze/silver and resolve paths to **ADLS**
  via ADME file services; avoid copying bytes through the driver. Use **Unity Catalog volumes**
  or **external locations** with IAM that matches entitlements.

**Databricks Lakeflow / DLT**

- Map each domain (or each medallion layer) to ``@dlt.table`` or pipeline tasks that call
  ``AuthProvider``, ``ADMEApiClient.fetch_domain_page`` / ``iter_domain_pages``, and the same
  merge semantics as ``SilverWriter``. Use **Change Data Feed** from bronze for incremental silver.
- Replace ``DeltaCheckpointStore`` with DLT **flow state** or an **append-only checkpoint**
  table written from a pipeline task.

Keep Phase 1 domains metadata-only; add new ``DomainConfig`` entries under ``conf/domains/``
and optional ``phase: 2`` when you enable heavy/binary pipelines.
"""
