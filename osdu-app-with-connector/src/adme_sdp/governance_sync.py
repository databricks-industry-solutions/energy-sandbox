# Databricks notebook source
# MAGIC %pip install -q 'httpx>=0.27' 'azure-identity>=1.15' 'pydantic>=2.5' 'PyYAML>=6' 'tenacity>=8'

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC # Governance Sync — ADME OSDU Lakeflow SDP
# MAGIC
# MAGIC Materializes ADME governance metadata (legal tags, entitlements groups,
# MAGIC record ACL mirror) as pipeline-managed tables. Fetches live data from ADME
# MAGIC APIs when available, falls back to mock data for demos.

# COMMAND ----------

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyspark import pipelines as dp
from pyspark.sql import Row
from pyspark.sql.types import (
    BooleanType,
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
from connector.governance.mock_data import (
    mock_entitlement_group_rows,
    mock_legal_tag_rows,
    mock_record_acl_rows,
)
from connector.governance.parsers import parse_entitlements_groups_json, parse_legal_tags_json
from connector.models.config import AuthConfig, ConnectorRuntimeConfig

# COMMAND ----------

def _conf(key: str, default: str = "") -> str:
    try:
        v = spark.conf.get(key, default)
        return v if v and str(v).strip() else default
    except Exception:
        return default


def _build_runtime() -> ConnectorRuntimeConfig:
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

# COMMAND ----------

def _fetch_legal_tags() -> list[dict[str, Any]]:
    """Fetch legal tags from ADME API, fall back to mock."""
    runtime = _build_runtime()
    auth = AuthProvider(runtime.auth)
    pid = runtime.data_partition_id

    rows: list[dict] = []
    try:
        with ADMEApiClient(runtime, auth) as client:
            resp = client.smoke_get("/api/legal/v1/legaltags?valid=true", timeout=60)
            if resp.status_code == 200:
                rows = parse_legal_tags_json(resp.json(), data_partition_id=pid, source="adme_api")
    except Exception:
        pass

    if not rows:
        rows = mock_legal_tag_rows(pid)
    return rows


def _fetch_entitlements_groups() -> list[dict[str, Any]]:
    """Fetch entitlements groups from ADME API, fall back to mock."""
    runtime = _build_runtime()
    auth = AuthProvider(runtime.auth)
    pid = runtime.data_partition_id

    rows: list[dict] = []
    try:
        with ADMEApiClient(runtime, auth) as client:
            resp = client.smoke_get("/api/entitlements/v2/groups", timeout=60)
            if resp.status_code == 200:
                rows = parse_entitlements_groups_json(resp.json(), data_partition_id=pid, source="adme_api")
    except Exception:
        pass

    if not rows:
        rows = mock_entitlement_group_rows(pid)
    return rows


def _fetch_record_acl() -> list[dict[str, Any]]:
    """Record ACL mirror — mock until a stable ACL API is available."""
    runtime = _build_runtime()
    pid = runtime.data_partition_id
    return mock_record_acl_rows(pid)

# COMMAND ----------

_LEGAL_TAGS_SCHEMA = StructType([
    StructField("legal_tag_name", StringType(), False),
    StructField("legal_tag_id", StringType(), False),
    StructField("is_valid", BooleanType(), True),
    StructField("data_partition_id", StringType(), False),
    StructField("obligations_json", StringType(), True),
    StructField("raw_json", StringType(), True),
    StructField("ingested_at", TimestampType(), False),
    StructField("source", StringType(), False),
])

_ENTITLEMENTS_SCHEMA = StructType([
    StructField("group_id", StringType(), False),
    StructField("group_name", StringType(), False),
    StructField("description", StringType(), True),
    StructField("data_partition_id", StringType(), False),
    StructField("raw_json", StringType(), True),
    StructField("ingested_at", TimestampType(), False),
    StructField("source", StringType(), False),
])

_ACL_SCHEMA = StructType([
    StructField("object_id", StringType(), False),
    StructField("resource_type", StringType(), True),
    StructField("principal_id", StringType(), True),
    StructField("privilege", StringType(), True),
    StructField("data_partition_id", StringType(), False),
    StructField("raw_json", StringType(), True),
    StructField("ingested_at", TimestampType(), False),
    StructField("source", StringType(), False),
])


@dp.table(
    name="gov_legal_tags",
    comment="ADME legal tags mirror — fetched live from ADME API or mock for demos.",
)
def gov_legal_tags():
    rows = _fetch_legal_tags()
    if not rows:
        return spark.createDataFrame([], _LEGAL_TAGS_SCHEMA)
    return spark.createDataFrame([Row(**r) for r in rows], _LEGAL_TAGS_SCHEMA)


@dp.table(
    name="gov_entitlements",
    comment="ADME entitlements groups mirror — fetched live from ADME API or mock for demos.",
)
def gov_entitlements():
    rows = _fetch_entitlements_groups()
    if not rows:
        return spark.createDataFrame([], _ENTITLEMENTS_SCHEMA)
    return spark.createDataFrame([Row(**r) for r in rows], _ENTITLEMENTS_SCHEMA)


@dp.table(
    name="gov_record_acl_mirror",
    comment="Record-level ACL mirror — mock data until ADME exposes a stable ACL API.",
)
def gov_record_acl_mirror():
    rows = _fetch_record_acl()
    if not rows:
        return spark.createDataFrame([], _ACL_SCHEMA)
    return spark.createDataFrame([Row(**r) for r in rows], _ACL_SCHEMA)
