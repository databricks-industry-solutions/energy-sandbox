"""Pydantic configuration models for the connector."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import AliasChoices, BaseModel, Field


class LoadType(str, Enum):
    full = "full"
    incremental = "incremental"


class AuthMode(str, Enum):
    managed_identity = "managed_identity"
    service_principal = "service_principal"
    static_token = "static_token"


class TableLayout(str, Enum):
    """Delta physical layout: one set of tables for all domains, or one bronze/silver/checkpoint per domain."""

    unified = "unified"
    per_domain = "per_domain"


class AuthConfig(BaseModel):
    """Azure Entra authentication for ADME API scope ``api://<adme_api_client_id>/.default``."""

    mode: AuthMode = AuthMode.managed_identity
    tenant_id: str = Field(..., description="Azure AD tenant ID")
    adme_api_client_id: str = Field(
        ...,
        description="Application (client) ID of the ADME API app registration (JWT audience).",
    )
    managed_identity_client_id: Optional[str] = Field(
        default=None,
        description="User-assigned MI client id; omit for system-assigned.",
    )
    service_principal_client_id: Optional[str] = None
    service_principal_client_secret: Optional[str] = None
    static_access_token: Optional[str] = None
    static_token_expires_on: Optional[int] = Field(
        default=None,
        description="Unix epoch expiry for static token (optional).",
    )

    @property
    def token_scope(self) -> str:
        return f"api://{self.adme_api_client_id}/.default"


class HttpClientConfig(BaseModel):
    timeout_seconds: float = 60.0
    max_connections: int = 32


class PaginationConfig(BaseModel):
    """Where to read list items and next cursor from JSON."""

    style: Literal["cursor_body", "offset_limit"] = "cursor_body"
    records_path: str = "results"
    cursor_path: str = "cursor"
    cursor_request_field: str = "cursor"
    page_size: int = 100


class ExtractionConfig(BaseModel):
    """How to call ADME/OSDU for a domain."""

    method: Literal["GET", "POST"] = "POST"
    path: str = "/api/search/v2/query"
    base_query: dict[str, Any] = Field(
        default_factory=dict,
        description="Static JSON merged into request body (e.g. kind, limit).",
    )
    incremental_filter_template: Optional[str] = Field(
        default=None,
        description=(
            "Optional query string fragment for incremental loads; "
            "``{watermark}`` replaced with last watermark (e.g. epoch ms)."
        ),
    )


class NormalizationConfig(BaseModel):
    """Map flattened silver columns from raw OSDU-style records (dot paths)."""

    record_id_path: str = "id"
    record_kind_path: str = "kind"
    modify_time_path: str = "modifyTime"
    field_map: dict[str, str] = Field(
        default_factory=dict,
        description="silver_column -> dotted path in raw record",
    )


class DomainConfig(BaseModel):
    """One ingestible domain (wellbore, reservoir, etc.)."""

    name: str
    description: str = ""
    primary_key: str = "id"
    incremental_field: str = "modifyTime"
    extraction: ExtractionConfig
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    normalization: NormalizationConfig = Field(default_factory=NormalizationConfig)
    phase: Literal[1, 2] = 1
    """Phase 2 reserved for seismic-heavy or binary workflows."""


class DeltaTargetsConfig(BaseModel):
    """Unity Catalog naming for bronze/silver/checkpoint tables."""

    catalog: str
    schema_name: str = Field(..., alias="schema")
    table_layout: TableLayout = TableLayout.unified
    """``unified``: single bronze/silver/checkpoint with a ``domain`` column; ``per_domain``: ``bronze_<domain>``, etc."""
    bronze_prefix: str = "bronze_"
    silver_prefix: str = "silver_"
    checkpoint_prefix: str = "checkpoint_"
    bronze_table: str = "adme_osdu_bronze_records"
    silver_table: str = "adme_osdu_silver_records"
    checkpoint_table: str = "adme_osdu_ingest_checkpoint"
    legal_tags_table: str = "gov_legal_tags"
    entitlements_table: str = Field(
        default="gov_entitlements",
        validation_alias=AliasChoices("entitlements_table", "entitlements_groups_table"),
        description="Entitlements / groups mirror (legacy YAML key: entitlements_groups_table).",
    )
    record_acl_mirror_table: str = "gov_record_acl_mirror"

    model_config = {"populate_by_name": True}

    @staticmethod
    def sanitize_domain_table_suffix(domain_name: str) -> str:
        """UC table name fragment from domain config ``name`` (lowercase, safe characters)."""
        s = re.sub(r"[^a-zA-Z0-9_]+", "_", (domain_name or "").strip())
        s = s.strip("_").lower()
        return s or "domain"

    def bronze_fqn(self, domain_name: Optional[str] = None) -> str:
        if self.table_layout == TableLayout.per_domain:
            if not domain_name:
                raise ValueError("domain_name is required for bronze_fqn when table_layout is per_domain")
            t = f"{self.bronze_prefix}{self.sanitize_domain_table_suffix(domain_name)}"
        else:
            t = self.bronze_table
        return f"{self.catalog}.{self.schema_name}.{t}"

    def silver_fqn(self, domain_name: Optional[str] = None) -> str:
        if self.table_layout == TableLayout.per_domain:
            if not domain_name:
                raise ValueError("domain_name is required for silver_fqn when table_layout is per_domain")
            t = f"{self.silver_prefix}{self.sanitize_domain_table_suffix(domain_name)}"
        else:
            t = self.silver_table
        return f"{self.catalog}.{self.schema_name}.{t}"

    def checkpoint_fqn(self, domain_name: Optional[str] = None) -> str:
        if self.table_layout == TableLayout.per_domain:
            if not domain_name:
                raise ValueError("domain_name is required for checkpoint_fqn when table_layout is per_domain")
            t = f"{self.checkpoint_prefix}{self.sanitize_domain_table_suffix(domain_name)}"
        else:
            t = self.checkpoint_table
        return f"{self.catalog}.{self.schema_name}.{t}"

    def legal_tags_fqn(self) -> str:
        return f"{self.catalog}.{self.schema_name}.{self.legal_tags_table}"

    def entitlements_fqn(self) -> str:
        return f"{self.catalog}.{self.schema_name}.{self.entitlements_table}"

    def entitlements_groups_fqn(self) -> str:
        """Backward-compatible alias for :meth:`entitlements_fqn`."""
        return self.entitlements_fqn()

    def record_acl_mirror_fqn(self) -> str:
        return f"{self.catalog}.{self.schema_name}.{self.record_acl_mirror_table}"


class CheckpointConfig(BaseModel):
    """Checkpoint store backend."""

    backend: Literal["delta", "memory"] = "delta"


class ConnectorRuntimeConfig(BaseModel):
    """Top-level runtime settings (Databricks + ADME)."""

    base_url: str = Field(..., description="ADME base URL, e.g. https://....energy.azure.com")
    data_partition_id: str
    auth: AuthConfig
    http: HttpClientConfig = Field(default_factory=HttpClientConfig)
    delta: DeltaTargetsConfig
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    load_type: LoadType = LoadType.incremental

    def api_base(self) -> str:
        return self.base_url.rstrip("/")
