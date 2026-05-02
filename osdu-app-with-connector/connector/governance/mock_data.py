"""Deterministic mock rows when ADME governance APIs are unavailable (403/500/empty)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def mock_legal_tag_rows(data_partition_id: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    return [
        {
            "legal_tag_name": "opendes-public-seismic",
            "legal_tag_id": "lt-mock-001",
            "is_valid": True,
            "data_partition_id": data_partition_id,
            "obligations_json": '{"classification":"Public"}',
            "raw_json": '{"name":"opendes-public-seismic","source":"mock"}',
            "ingested_at": now,
            "source": "mock",
        },
        {
            "legal_tag_name": "opendes-restricted-pii",
            "legal_tag_id": "lt-mock-002",
            "is_valid": True,
            "data_partition_id": data_partition_id,
            "obligations_json": '{"classification":"Restricted","region":"US"}',
            "raw_json": '{"name":"opendes-restricted-pii","source":"mock"}',
            "ingested_at": now,
            "source": "mock",
        },
    ]


def mock_entitlement_group_rows(data_partition_id: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    return [
        {
            "group_id": "grp-mock-data-readers",
            "group_name": "OSDU Data Readers",
            "description": "Mock readers group for UC grant mapping demos",
            "data_partition_id": data_partition_id,
            "raw_json": '{"email":"data-readers@example.com","source":"mock"}',
            "ingested_at": now,
            "source": "mock",
        },
        {
            "group_id": "grp-mock-data-stewards",
            "group_name": "OSDU Data Stewards",
            "description": "Mock stewards — map to UC group for policy alignment",
            "data_partition_id": data_partition_id,
            "raw_json": '{"email":"stewards@example.com","source":"mock"}',
            "ingested_at": now,
            "source": "mock",
        },
    ]


def mock_record_acl_rows(data_partition_id: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    return [
        {
            "object_id": "srn:partition:opendes:master-data--Wellbore:mock-1",
            "resource_type": "wellbore",
            "principal_id": "grp-mock-data-readers",
            "privilege": "viewer",
            "data_partition_id": data_partition_id,
            "raw_json": '{"aclSource":"mock","notes":"Drive UC row filters / views from this table"}',
            "ingested_at": now,
            "source": "mock",
        },
        {
            "object_id": "srn:partition:opendes:master-data--Wellbore:mock-2",
            "resource_type": "wellbore",
            "principal_id": "grp-mock-data-stewards",
            "privilege": "owner",
            "data_partition_id": data_partition_id,
            "raw_json": '{"aclSource":"mock"}',
            "ingested_at": now,
            "source": "mock",
        },
    ]
