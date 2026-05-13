"""AdmeOsduLakeflowConnect — LakeflowConnect adapter for the ADME OSDU connector."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from connector.auth.auth_provider import AuthProvider
from connector.clients.adme_api import ADMEApiClient
from connector.domains.registry import load_domains_from_dir
from connector.governance.parsers import parse_entitlements_groups_json, parse_legal_tags_json
from connector.lakeflow.interface import LakeflowConnect, SchemaField
from connector.models.config import (
    AuthConfig,
    AuthMode,
    DeltaTargetsConfig,
    DomainConfig,
    ExtractionConfig,
    HttpClientConfig,
    PaginationConfig,
    ConnectorRuntimeConfig,
)

logger = logging.getLogger(__name__)

_CONF_DOMAINS_DIR = Path(__file__).resolve().parents[2] / "conf" / "domains"

_DOMAIN_TABLES = frozenset({"wellbore", "reservoir", "rock_and_fluid"})
_GOV_TABLES = frozenset({"legal_tags", "entitlements"})

# ── Schemas ──────────────────────────────────────────────────────────────────

_DOMAIN_SCHEMA: list[SchemaField] = [
    {"name": "id",           "type": "string",        "nullable": False},
    {"name": "kind",         "type": "string",        "nullable": True},
    {"name": "version",      "type": "long",          "nullable": True},
    {"name": "createTime",   "type": "string",        "nullable": True},
    {"name": "createUser",   "type": "string",        "nullable": True},
    {"name": "modifyTime",   "type": "string",        "nullable": False},
    {"name": "modifyUser",   "type": "string",        "nullable": True},
    {"name": "acl_viewers",  "type": "array<string>", "nullable": True},
    {"name": "acl_owners",   "type": "array<string>", "nullable": True},
    {"name": "legal_tags",   "type": "array<string>", "nullable": True},
    {"name": "legal_status", "type": "string",        "nullable": True},
    {"name": "data",         "type": "map<string,string>", "nullable": True},
]

_LEGAL_TAGS_SCHEMA: list[SchemaField] = [
    {"name": "legal_tag_name",   "type": "string",    "nullable": False},
    {"name": "legal_tag_id",     "type": "string",    "nullable": True},
    {"name": "is_valid",         "type": "boolean",   "nullable": True},
    {"name": "data_partition_id","type": "string",    "nullable": True},
    {"name": "obligations_json", "type": "string",    "nullable": True},
    {"name": "raw_json",         "type": "string",    "nullable": True},
    {"name": "ingested_at",      "type": "timestamp", "nullable": True},
    {"name": "source",           "type": "string",    "nullable": True},
]

_ENTITLEMENTS_SCHEMA: list[SchemaField] = [
    {"name": "group_id",         "type": "string",    "nullable": False},
    {"name": "group_name",       "type": "string",    "nullable": True},
    {"name": "description",      "type": "string",    "nullable": True},
    {"name": "data_partition_id","type": "string",    "nullable": True},
    {"name": "raw_json",         "type": "string",    "nullable": True},
    {"name": "ingested_at",      "type": "timestamp", "nullable": True},
    {"name": "source",           "type": "string",    "nullable": True},
]


def _build_runtime(options: dict[str, str]) -> ConnectorRuntimeConfig:
    return ConnectorRuntimeConfig(
        base_url=options["base_url"],
        data_partition_id=options.get("data_partition_id", "opendes"),
        auth=AuthConfig(
            mode=AuthMode.static_token,
            tenant_id=options.get("tenant_id", "00000000-0000-0000-0000-000000000000"),
            adme_api_client_id=options.get("adme_api_client_id", "00000000-0000-0000-0000-000000000001"),
            static_access_token=options.get("access_token", "simulator-token"),
        ),
        delta=DeltaTargetsConfig(catalog="lakeflow_test", schema="adme_osdu"),
        http=HttpClientConfig(timeout_seconds=30.0, max_connections=8),
    )


def _default_domain_config(table_name: str) -> DomainConfig:
    kind_map = {
        "wellbore":       "osdu:wks:master-data--Wellbore:*",
        "reservoir":      "osdu:wks:work-product-component--ReservoirZone:*",
        "rock_and_fluid": "osdu:wks:work-product-component--RockAndFluidSample:*",
    }
    return DomainConfig(
        name=table_name,
        extraction=ExtractionConfig(
            base_query={
                "kind": kind_map.get(table_name, f"osdu:wks:*{table_name}*:*"),
                "sort": {"field": ["modifyTime"], "order": ["ASC"]},
            },
            incremental_filter_template="modifyTime:[{watermark} TO *]",
        ),
        pagination=PaginationConfig(),
    )


class AdmeOsduLakeflowConnect(LakeflowConnect):
    """LakeflowConnect adapter for the ADME OSDU connector.

    Options (all string-valued):
        base_url            ADME instance URL (e.g. https://foo.energy.azure.com)
        data_partition_id   OSDU data partition (default: opendes)
        access_token        Pre-issued bearer token for static_token auth mode
        tenant_id           Azure AD tenant ID (optional for real auth)
        adme_api_client_id  ADME app registration client ID (optional for real auth)
    """

    TABLES = ("wellbore", "reservoir", "rock_and_fluid", "legal_tags", "entitlements")

    def __init__(self, options: dict[str, str]) -> None:
        super().__init__(options)
        self._runtime = _build_runtime(options)
        self._auth = AuthProvider(self._runtime.auth)
        self._domains = load_domains_from_dir(_CONF_DOMAINS_DIR)

    def _new_client(self) -> ADMEApiClient:
        return ADMEApiClient(self._runtime, self._auth)

    # ── LakeflowConnect ────────────────────────────────────────────────────────

    def list_tables(self) -> list[str]:
        return list(self.TABLES)

    def get_table_schema(self, table_name: str, table_options: dict[str, str]) -> list[SchemaField]:
        if table_name in _DOMAIN_TABLES:
            return list(_DOMAIN_SCHEMA)
        if table_name == "legal_tags":
            return list(_LEGAL_TAGS_SCHEMA)
        if table_name == "entitlements":
            return list(_ENTITLEMENTS_SCHEMA)
        raise ValueError(f"Unknown table: {table_name!r}")

    def read_table_metadata(self, table_name: str, table_options: dict[str, str]) -> dict:
        if table_name in _DOMAIN_TABLES:
            return {"primary_keys": ["id"], "cursor_field": "modifyTime", "ingestion_type": "cdc"}
        if table_name == "legal_tags":
            return {"primary_keys": ["legal_tag_name"], "cursor_field": None, "ingestion_type": "snapshot"}
        if table_name == "entitlements":
            return {"primary_keys": ["group_id"], "cursor_field": None, "ingestion_type": "snapshot"}
        raise ValueError(f"Unknown table: {table_name!r}")

    def read_table(
        self,
        table_name: str,
        start_offset: dict | None,
        table_options: dict[str, str],
    ) -> tuple[Iterator[dict], dict | None]:
        if table_name in _DOMAIN_TABLES:
            return self._read_domain(table_name, start_offset, table_options)
        if table_name == "legal_tags":
            return self._read_legal_tags()
        if table_name == "entitlements":
            return self._read_entitlements()
        raise ValueError(f"Unknown table: {table_name!r}")

    # ── Domain (OSDU record) reads ────────────────────────────────────────────

    def _read_domain(
        self,
        table_name: str,
        start_offset: dict | None,
        table_options: dict[str, str],
    ) -> tuple[Iterator[dict], dict | None]:
        domain = self._domains.get(table_name) or _default_domain_config(table_name)
        cursor = (start_offset or {}).get("cursor")
        watermark = (start_offset or {}).get("watermark")

        with self._new_client() as client:
            page = client.fetch_domain_page(
                domain,
                cursor=cursor,
                watermark=watermark,
                load_full=(watermark is None),
            )

        records: list[dict] = page.get("results", [])
        next_cursor: str | None = page.get("cursor") or None

        if not records:
            return iter([]), start_offset  # signals pagination done

        flat = [self._flatten_record(r) for r in records]
        max_wm = max((r.get("modifyTime") or "") for r in flat) or watermark
        new_offset: dict = {"cursor": next_cursor, "watermark": max_wm}
        return iter(flat), new_offset

    @staticmethod
    def _flatten_record(r: dict) -> dict:
        acl = r.get("acl") or {}
        legal = r.get("legal") or {}
        data = r.get("data") or {}
        return {
            "id": r.get("id"),
            "kind": r.get("kind"),
            "version": r.get("version"),
            "createTime": r.get("createTime"),
            "createUser": r.get("createUser"),
            "modifyTime": r.get("modifyTime"),
            "modifyUser": r.get("modifyUser"),
            "acl_viewers": acl.get("viewers"),
            "acl_owners": acl.get("owners"),
            "legal_tags": (legal.get("legaltags") or []),
            "legal_status": legal.get("status"),
            "data": {k: str(v) for k, v in data.items() if not isinstance(v, (dict, list))},
        }

    # ── Governance reads ──────────────────────────────────────────────────────

    def _read_legal_tags(self) -> tuple[Iterator[dict], None]:
        with self._new_client() as client:
            resp = client.get_json("/api/legal/v1/legaltags", params={"valid": "true"})
        rows = parse_legal_tags_json(
            resp,
            data_partition_id=self._runtime.data_partition_id,
            source="adme_api",
        )
        return iter(rows), None

    def _read_entitlements(self) -> tuple[Iterator[dict], None]:
        with self._new_client() as client:
            resp = client.get_json("/api/entitlements/v2/groups")
        rows = parse_entitlements_groups_json(
            resp,
            data_partition_id=self._runtime.data_partition_id,
            source="adme_api",
        )
        return iter(rows), None
