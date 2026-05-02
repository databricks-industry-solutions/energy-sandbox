"""Fetch governance metadata from ADME (or mock), write UC Delta mirror tables."""

from __future__ import annotations

import json
import logging
from typing import Any

from connector.auth.auth_provider import AuthProvider
from connector.clients.adme_api import ADMEApiClient
from connector.governance.delta_governance import (
    ensure_governance_schema,
    write_entitlements_groups,
    write_legal_tags,
    write_record_acl_mirror,
)
from connector.governance.mock_data import (
    mock_entitlement_group_rows,
    mock_legal_tag_rows,
    mock_record_acl_rows,
)
from connector.governance.parsers import parse_entitlements_groups_json, parse_legal_tags_json
from connector.models.config import ConnectorRuntimeConfig

logger = logging.getLogger(__name__)


def sync_governance_mirror(
    spark: Any,
    runtime: ConnectorRuntimeConfig,
    auth: AuthProvider,
    *,
    append_mock_when_live: bool = False,
    force_mock: bool = False,
) -> dict[str, int]:
    """
    Pull legal tags + entitlements groups from ADME; ACL table uses mock until a stable ACL API is wired.

    - ``force_mock``: skip HTTP, write mock only.
    - ``append_mock_when_live``: when ADME returns data, also append mock rows (for demos).
    """
    ensure_governance_schema(spark, runtime)
    pid = runtime.data_partition_id
    counts: dict[str, int] = {}

    legal_rows: list[dict] = []
    group_rows: list[dict] = []

    if not force_mock:
        with ADMEApiClient(runtime, auth) as client:
            lr = client.smoke_get("/api/legal/v1/legaltags?valid=true", timeout=60)
            if lr.status_code == 200:
                try:
                    legal_rows = parse_legal_tags_json(
                        lr.json(), data_partition_id=pid, source="adme_api"
                    )
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.warning("legal tags JSON parse failed: %s", e)
            else:
                logger.warning("legal tags HTTP %s", lr.status_code)

            gr = client.smoke_get("/api/entitlements/v2/groups", timeout=60)
            if gr.status_code == 200:
                try:
                    group_rows = parse_entitlements_groups_json(
                        gr.json(), data_partition_id=pid, source="adme_api"
                    )
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.warning("groups JSON parse failed: %s", e)
            else:
                logger.warning("entitlements groups HTTP %s", gr.status_code)

    mock_l = mock_legal_tag_rows(pid)
    mock_g = mock_entitlement_group_rows(pid)
    mock_a = mock_record_acl_rows(pid)

    if force_mock:
        legal_final = list(mock_l)
    elif legal_rows:
        legal_final = legal_rows + (mock_l if append_mock_when_live else [])
    else:
        legal_final = list(mock_l)

    if force_mock:
        group_final = list(mock_g)
    elif group_rows:
        group_final = group_rows + (mock_g if append_mock_when_live else [])
    else:
        group_final = list(mock_g)

    # ACL mirror: mock for now (replace with Storage/Record ACL API when available)
    acl_final = list(mock_a)

    counts["legal_tags"] = write_legal_tags(spark, runtime, legal_final)
    counts["entitlements_groups"] = write_entitlements_groups(spark, runtime, group_final)
    counts["record_acl_mirror"] = write_record_acl_mirror(spark, runtime, acl_final)
    return counts
