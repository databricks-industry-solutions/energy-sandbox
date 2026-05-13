# Databricks notebook source
# MAGIC %pip install -q 'httpx>=0.27' 'azure-identity>=1.15' 'pydantic>=2.5' 'PyYAML>=6' 'tenacity>=8'

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC # Bronze Ingestion — ADME OSDU Lakeflow SDP
# MAGIC
# MAGIC Extracts raw OSDU records from ADME Search API via Managed Identity and
# MAGIC lands them as structured Bronze tables using `pyspark.pipelines`.
# MAGIC
# MAGIC Each domain (wellbore, reservoir, rock_and_fluid) gets its own `@dp.table`.
# MAGIC The connector package (`connector/`) provides auth, HTTP extraction, pagination,
# MAGIC and schema inference — reused as-is from the batch connector.

# COMMAND ----------

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyspark import pipelines as dp
from pyspark.sql import Row
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# --- Bootstrap connector package path ---
_nb_dir = Path(os.path.dirname(os.path.abspath(__file__))) if "__file__" in dir() else Path.cwd()
_candidates = [_nb_dir.parent, _nb_dir.parent / "files", _nb_dir.parent.parent, _nb_dir.parent.parent / "files"]
for _c in _candidates:
    if (_c / "connector" / "__init__.py").is_file():
        if str(_c) not in sys.path:
            sys.path.insert(0, str(_c))
        break

from connector.auth.auth_provider import AuthProvider
from connector.clients.adme_api import ADMEApiClient
from connector.config_loader import load_runtime_config
from connector.domains.registry import load_domains_from_dir
from connector.models.config import AuthConfig, ConnectorRuntimeConfig, DomainConfig, LoadType

# COMMAND ----------

def _conf(key: str, default: str = "") -> str:
    try:
        v = spark.conf.get(key, default)
        return v if v and str(v).strip() else default
    except Exception:
        return default


def _build_runtime() -> ConnectorRuntimeConfig:
    """Build runtime config from pipeline configuration parameters."""
    yaml_candidates = [
        Path(str(p)) / "conf" / "connector_runtime.yaml"
        for p in _candidates
    ] + [
        Path(str(p)) / "conf" / "connector_runtime.example.yaml"
        for p in _candidates
    ]
    runtime = None
    for yp in yaml_candidates:
        if yp.is_file():
            runtime = load_runtime_config(yp)
            break

    if runtime is None:
        runtime = ConnectorRuntimeConfig(
            base_url=_conf("adme.connector.base_url", "https://admesbxscusins1.energy.azure.com"),
            data_partition_id=_conf("adme.connector.data_partition_id", "opendes"),
            auth=AuthConfig(
                tenant_id=_conf("adme.connector.tenant_id", "72f988bf-86f1-41af-91ab-2d7cd011db47"),
                adme_api_client_id=_conf("adme.connector.adme_api_client_id", "e37a6c70-7cbc-4593-80fc-01c1f20203f7"),
            ),
            delta={
                "catalog": _conf("adme.connector.catalog", "adme_adb_sbx_scus_dbx_ws_1"),
                "schema": _conf("adme.connector.schema", "adme_osdu_sdp"),
                "table_layout": "per_domain",
            },
        )

    runtime.base_url = _conf("adme.connector.base_url", runtime.base_url)
    runtime.data_partition_id = _conf("adme.connector.data_partition_id", runtime.data_partition_id)
    runtime.auth.tenant_id = _conf("adme.connector.tenant_id", runtime.auth.tenant_id)
    runtime.auth.adme_api_client_id = _conf("adme.connector.adme_api_client_id", runtime.auth.adme_api_client_id)
    mi = _conf("adme.connector.managed_identity_client_id", "")
    if mi:
        runtime.auth.managed_identity_client_id = mi
    return runtime


def _load_domains() -> dict[str, DomainConfig]:
    """Load domain configs from conf/domains/."""
    for _c in _candidates:
        d = _c / "conf" / "domains"
        if d.is_dir():
            return load_domains_from_dir(d)
    return {}


def _extract_domain(domain_name: str) -> list[dict[str, Any]]:
    """Extract all records for a domain from ADME Search API."""
    runtime = _build_runtime()
    domains = _load_domains()
    domain = domains[domain_name]
    auth = AuthProvider(runtime.auth)

    records: list[dict[str, Any]] = []
    with ADMEApiClient(runtime, auth) as client:
        for page in client.iter_domain_pages(domain, watermark=None, load_full=True):
            records.extend(page.records)
    return records


_BRONZE_SCHEMA = StructType([
    StructField("bronze_id", StringType(), False),
    StructField("domain", StringType(), False),
    StructField("record_id", StringType(), True),
    StructField("raw_json", StringType(), False),
    StructField("ingestion_ts", TimestampType(), False),
    StructField("ingestion_date", StringType(), False),
    StructField("request_path", StringType(), True),
    StructField("http_status", IntegerType(), True),
    StructField("cluster_id", StringType(), True),
])


def _records_to_dataframe(domain_name: str, records: list[dict[str, Any]]):
    """Convert extracted records to a Spark DataFrame with bronze schema."""
    now = datetime.now(timezone.utc)
    ingestion_date = now.strftime("%Y-%m-%d")
    cluster_id = _conf("spark.databricks.clusterUsageTags.clusterId", "")

    rows = []
    for rec in records:
        record_id = rec.get("id", rec.get("data", {}).get("ResourceID", ""))
        rows.append(Row(
            bronze_id=str(uuid.uuid4()),
            domain=domain_name,
            record_id=str(record_id) if record_id else None,
            raw_json=json.dumps(rec, default=str),
            ingestion_ts=now,
            ingestion_date=ingestion_date,
            request_path="/api/search/v2/query",
            http_status=200,
            cluster_id=cluster_id,
        ))

    if not rows:
        return spark.createDataFrame([], _BRONZE_SCHEMA)
    return spark.createDataFrame(rows, _BRONZE_SCHEMA)

# COMMAND ----------

@dp.table(
    name="bronze_wellbore",
    comment="Raw wellbore records from ADME Search API (full extract per pipeline refresh).",
    cluster_by=["ingestion_date"],
)
def bronze_wellbore():
    records = _extract_domain("wellbore")
    return _records_to_dataframe("wellbore", records)


@dp.table(
    name="bronze_reservoir",
    comment="Raw reservoir records from ADME Search API (full extract per pipeline refresh).",
    cluster_by=["ingestion_date"],
)
def bronze_reservoir():
    records = _extract_domain("reservoir")
    return _records_to_dataframe("reservoir", records)


@dp.table(
    name="bronze_rock_and_fluid",
    comment="Raw rock & fluid records from ADME Search API (full extract per pipeline refresh).",
    cluster_by=["ingestion_date"],
)
def bronze_rock_and_fluid():
    records = _extract_domain("rock_and_fluid")
    return _records_to_dataframe("rock_and_fluid", records)
