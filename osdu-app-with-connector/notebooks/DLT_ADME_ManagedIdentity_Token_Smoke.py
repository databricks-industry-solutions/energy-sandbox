# Databricks notebook source
# MAGIC %md
# MAGIC # DLT: ADME token + smoke tests (managed identity)
# MAGIC
# MAGIC Mirrors the **logical steps** from `Auth_with_Entra_Token_ADME_API_SmokeTest_Databricks.py` as separate Delta Live Tables:
# MAGIC
# MAGIC 1. **`bronze_adme_config`** — same constants as notebook “Set Variables” + ADME API scope.
# MAGIC 2. **`bronze_adme_workspace_context`** — cluster / workspace tags (Spark conf), like the discovery cell’s Databricks section.
# MAGIC 3. **`bronze_adme_imds_arm`** — IMDS probe for `https://management.azure.com/` (notebook Cell 4 Step 1 / “MI token test”).
# MAGIC 4. **`silver_adme_access_token`** — `ManagedIdentityCredential` + `get_token` for `api://<ADME_APP_ID>/.default` (**contains the JWT**).
# MAGIC 5. **`silver_adme_token_claims`** — decoded JWT payload (no signature verify): `aud`, `appid`, `oid`, `exp`, `roles`, etc.
# MAGIC 6. **`bronze_adme_metadata_partitions`** / **`bronze_adme_metadata_legal_tags`** — bronze **metadata API** landing (partition list + legal tags JSON) for the UC roadmap (Lakeflow/file copy can follow into `landing_technical` volume).
# MAGIC 7. **`gold_adme_smoke_results`** — GET each ADME path with `Authorization: Bearer <token>` and `data-partition-id`.
# MAGIC
# MAGIC **Requirements**
# MAGIC - Pipeline cluster must reach **IMDS** (`169.254.169.254`): use an **Azure** job/pipeline cluster with **managed identity** (often **single-user** / **no isolation**; serverless may not expose IMDS).
# MAGIC - Install **`azure-identity`** on the cluster (first cell `%pip`, or cluster library).
# MAGIC
# MAGIC **Security**
# MAGIC - `silver_adme_access_token` stores a **live bearer token**. Lock down with **Unity Catalog** (catalog/schema/table ACLs) or **do not grant** broad `SELECT`. Prefer copying only `expires_on` / metadata to downstream systems and refreshing the secret out-of-band.

# COMMAND ----------

# MAGIC %pip install -q 'azure-identity>=1.15.0'

# COMMAND ----------

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

import dlt
import requests
from pyspark.sql import Row
from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# --- Same defaults as the ADME auth notebook (override via Spark conf if needed) ---
_DEFAULT_BASE = "https://admesbxscusins1.energy.azure.com"
_DEFAULT_PARTITION = "opendes"
_DEFAULT_TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"
_DEFAULT_ADME_APP_ID = "e37a6c70-7cbc-4593-80fc-01c1f20203f7"

_IMDS_TOKEN_URL = "http://169.254.169.254/metadata/identity/oauth2/token"


def _conf(key: str, default: str) -> str:
    try:
        v = spark.conf.get(key, default)
        return v if v is not None and str(v).strip() != "" else default
    except Exception:
        return default


def _b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def decode_jwt_payload_noverify(jwt: str) -> dict[str, Any]:
    parts = jwt.split(".")
    if len(parts) != 3:
        raise ValueError("Not a JWT (expected 3 parts).")
    return json.loads(_b64url_decode(parts[1]))


def _single_config_row():
    base_url = _conf("adme.pipeline.base_url", _DEFAULT_BASE).rstrip("/")
    data_partition_id = _conf("adme.pipeline.data_partition_id", _DEFAULT_PARTITION)
    tenant_id = _conf("adme.pipeline.tenant_id", _DEFAULT_TENANT)
    adme_app_id = _conf("adme.pipeline.adme_api_client_id", _DEFAULT_ADME_APP_ID)
    scope = f"api://{adme_app_id}/.default"
    return Row(
        base_url=base_url,
        data_partition_id=data_partition_id,
        tenant_id=tenant_id,
        adme_api_client_id=adme_app_id,
        adme_scope=scope,
        pipeline_version="1",
    )


@dlt.table(
    name="bronze_adme_config",
    comment="Step 1: ADME / Entra settings (Spark conf adme.pipeline.* overrides defaults).",
)
def bronze_adme_config():
    cfg = _single_config_row()
    schema = StructType(
        [
            StructField("base_url", StringType(), False),
            StructField("data_partition_id", StringType(), False),
            StructField("tenant_id", StringType(), False),
            StructField("adme_api_client_id", StringType(), False),
            StructField("adme_scope", StringType(), False),
            StructField("pipeline_version", StringType(), False),
        ]
    )
    return spark.createDataFrame([cfg], schema)


@dlt.table(
    name="bronze_adme_workspace_context",
    comment="Step 2: Databricks cluster / workspace tags from Spark conf.",
)
def bronze_adme_workspace_context():
    cluster_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterId", None)
    workspace_url = spark.conf.get("spark.databricks.workspaceUrl", None)
    spark_version = spark.conf.get("spark.databricks.clusterUsageTags.sparkVersion", None)
    row = Row(
        cluster_id=cluster_id,
        workspace_url=workspace_url,
        spark_version=spark_version,
        captured_at=datetime.now(timezone.utc),
    )
    schema = StructType(
        [
            StructField("cluster_id", StringType(), True),
            StructField("workspace_url", StringType(), True),
            StructField("spark_version", StringType(), True),
            StructField("captured_at", TimestampType(), False),
        ]
    )
    df = spark.createDataFrame([row], schema)
    return df


@dlt.table(
    name="bronze_adme_imds_arm",
    comment="Step 3: IMDS probe for ARM resource token (management.azure.com).",
)
def bronze_adme_imds_arm():
    err: Optional[str] = None
    status_code = -1
    client_id = None
    object_id = None
    resource = None
    try:
        r = requests.get(
            _IMDS_TOKEN_URL,
            params={
                "api-version": "2018-02-01",
                "resource": "https://management.azure.com/",
            },
            headers={"Metadata": "true"},
            timeout=3.0,
        )
        status_code = r.status_code
        if r.status_code == 200:
            body = r.json()
            client_id = body.get("client_id")
            object_id = body.get("object_id")
            resource = body.get("resource")
        else:
            err = r.text[:2000] if r.text else f"HTTP {r.status_code}"
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    row = Row(
        imds_http_status=status_code,
        imds_client_id=client_id,
        imds_object_id=object_id,
        imds_resource=resource,
        error_message=err,
        probed_at_epoch=int(time.time()),
    )
    schema = StructType(
        [
            StructField("imds_http_status", IntegerType(), False),
            StructField("imds_client_id", StringType(), True),
            StructField("imds_object_id", StringType(), True),
            StructField("imds_resource", StringType(), True),
            StructField("error_message", StringType(), True),
            StructField("probed_at_epoch", LongType(), False),
        ]
    )
    return spark.createDataFrame([row], schema)


@dlt.table(
    name="silver_adme_access_token",
    comment="Step 4: ADME API access token via ManagedIdentityCredential (contains JWT — lock down UC).",
)
def silver_adme_access_token():
    from azure.identity import ManagedIdentityCredential

    cfg_rows = dlt.read("bronze_adme_config").limit(1).collect()
    if not cfg_rows:
        raise ValueError("bronze_adme_config is empty")
    scope = cfg_rows[0]["adme_scope"]

    mi_client_id = _conf("adme.pipeline.managed_identity_client_id", "").strip()
    credential = (
        ManagedIdentityCredential(client_id=mi_client_id)
        if mi_client_id
        else ManagedIdentityCredential()
    )
    tok = credential.get_token(scope)
    acquired = int(time.time())
    row = Row(
        access_token=tok.token,
        expires_on=int(tok.expires_on),
        scope=scope,
        acquired_at_epoch=acquired,
    )
    schema = StructType(
        [
            StructField("access_token", StringType(), False),
            StructField("expires_on", LongType(), False),
            StructField("scope", StringType(), False),
            StructField("acquired_at_epoch", LongType(), False),
        ]
    )
    return spark.createDataFrame([row], schema)


@dlt.table(
    name="silver_adme_token_claims",
    comment="Step 5: Decoded JWT claims (no signature verification).",
)
def silver_adme_token_claims():
    trows = dlt.read("silver_adme_access_token").limit(1).collect()
    if not trows:
        raise ValueError("silver_adme_access_token is empty")
    jwt = trows[0]["access_token"]
    claims = decode_jwt_payload_noverify(jwt)
    roles = claims.get("roles")
    roles_json = json.dumps(roles) if roles is not None else None
    row = Row(
        aud=str(claims.get("aud", "")),
        appid=str(claims.get("appid", claims.get("azp", "") or "")),
        oid=str(claims.get("oid", "") or ""),
        tid=str(claims.get("tid", "") or ""),
        exp=int(claims["exp"]) if isinstance(claims.get("exp"), int) else None,
        roles_json=roles_json,
        claims_json=json.dumps(claims, default=str)[:8000],
        decoded_at_epoch=int(time.time()),
    )
    schema = StructType(
        [
            StructField("aud", StringType(), False),
            StructField("appid", StringType(), False),
            StructField("oid", StringType(), False),
            StructField("tid", StringType(), False),
            StructField("exp", IntegerType(), True),
            StructField("roles_json", StringType(), True),
            StructField("claims_json", StringType(), True),
            StructField("decoded_at_epoch", LongType(), False),
        ]
    )
    return spark.createDataFrame([row], schema)


def _adme_get_json_row(
    *,
    base_url: str,
    data_partition_id: str,
    tok: str,
    path: str,
    max_raw_chars: int = 1_000_000,
) -> Row:
    url = base_url.rstrip("/") + path
    headers = {
        "Authorization": f"Bearer {tok}",
        "data-partition-id": data_partition_id,
        "Accept": "application/json",
    }
    status = -1
    raw = ""
    err: Optional[str] = None
    parsed_hint: Optional[str] = None
    try:
        r = requests.get(url, headers=headers, timeout=60)
        status = r.status_code
        raw = (r.text or "")[:max_raw_chars]
        if r.status_code == 200 and r.text:
            try:
                data = r.json()
                if isinstance(data, list):
                    parsed_hint = json.dumps([str(x) for x in data], default=str)[:16000]
                elif isinstance(data, dict):
                    parsed_hint = json.dumps(data, default=str)[:16000]
            except Exception:
                parsed_hint = None
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    return Row(
        api_path=path,
        data_partition_id=data_partition_id,
        http_status=status,
        response_raw=raw,
        parsed_json_snippet=parsed_hint,
        error_message=err,
        ingested_at=datetime.now(timezone.utc),
    )


_BRONZE_API_SCHEMA = StructType(
    [
        StructField("api_path", StringType(), False),
        StructField("data_partition_id", StringType(), False),
        StructField("http_status", IntegerType(), False),
        StructField("response_raw", StringType(), True),
        StructField("parsed_json_snippet", StringType(), True),
        StructField("error_message", StringType(), True),
        StructField("ingested_at", TimestampType(), False),
    ]
)


@dlt.table(
    name="bronze_adme_metadata_partitions",
    comment="Bronze metadata: GET /api/partition/v1/partitions (aligns data_partition_id / entitlements context).",
)
def bronze_adme_metadata_partitions():
    cfg = dlt.read("bronze_adme_config").limit(1).collect()[0]
    base_url = cfg["base_url"]
    data_partition_id = cfg["data_partition_id"]
    tok = dlt.read("silver_adme_access_token").limit(1).collect()[0]["access_token"]
    row = _adme_get_json_row(
        base_url=base_url,
        data_partition_id=data_partition_id,
        tok=tok,
        path="/api/partition/v1/partitions",
    )
    return spark.createDataFrame([row], _BRONZE_API_SCHEMA)


@dlt.table(
    name="bronze_adme_metadata_legal_tags",
    comment="Bronze metadata: GET /api/legal/v1/legaltags?valid=true (legal / compliance tags for downstream gold).",
)
def bronze_adme_metadata_legal_tags():
    cfg = dlt.read("bronze_adme_config").limit(1).collect()[0]
    base_url = cfg["base_url"]
    data_partition_id = cfg["data_partition_id"]
    tok = dlt.read("silver_adme_access_token").limit(1).collect()[0]["access_token"]
    row = _adme_get_json_row(
        base_url=base_url,
        data_partition_id=data_partition_id,
        tok=tok,
        path="/api/legal/v1/legaltags?valid=true",
    )
    return spark.createDataFrame([row], _BRONZE_API_SCHEMA)


@dlt.table(
    name="gold_adme_smoke_results",
    comment="Step 7: ADME GET smoke tests using token from silver_adme_access_token.",
)
def gold_adme_smoke_results():
    cfg = dlt.read("bronze_adme_config").limit(1).collect()[0]
    base_url = cfg["base_url"].rstrip("/")
    data_partition_id = cfg["data_partition_id"]
    tok = dlt.read("silver_adme_access_token").limit(1).collect()[0]["access_token"]

    paths = [
        ("/seistore-svc/api/v3/svcstatus", "Seistore service status"),
        ("/api/reservoir-ddms/v2/health/info", "Reservoir DDMS health/info"),
        ("/api/crs/catalog/v3/info", "CRS Catalog info"),
        ("/api/entitlements/v2/groups", "Entitlements groups"),
        ("/api/legal/v1/legaltags?valid=true", "Legal tags (valid=true)"),
        ("/api/partition/v1/partitions", "Partition service (list partitions)"),
        ("/api/file/v2/well-known/configuration", "File service (well-known configuration)"),
        ("/api/search/v2/liveness", "Search service (liveness)"),
        ("/api/indexer/v2/readiness", "Indexer service (readiness)"),
    ]

    headers = {
        "Authorization": f"Bearer {tok}",
        "data-partition-id": data_partition_id,
        "Accept": "application/json",
    }

    rows = []
    for path, label in paths:
        url = base_url + path
        status = -1
        err = None
        try:
            r = requests.get(url, headers=headers, timeout=30)
            status = r.status_code
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        rows.append(
            Row(
                label=label,
                path=path,
                url=url,
                http_status=status,
                error_message=err,
                tested_at_epoch=int(time.time()),
            )
        )

    schema = StructType(
        [
            StructField("label", StringType(), False),
            StructField("path", StringType(), False),
            StructField("url", StringType(), False),
            StructField("http_status", IntegerType(), False),
            StructField("error_message", StringType(), True),
            StructField("tested_at_epoch", LongType(), False),
        ]
    )
    return spark.createDataFrame(rows, schema)
