"""Normalize ADME/OSDU JSON bodies into flat rows for Delta."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _now_ts() -> datetime:
    return datetime.now(timezone.utc)


def _as_list(body: Any, *keys: str) -> list[Any]:
    if body is None:
        return []
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in keys:
            v = body.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict) and "results" in v and isinstance(v["results"], list):
                return v["results"]
    return []


def parse_legal_tags_json(
    body: Any,
    *,
    data_partition_id: str,
    source: str,
) -> list[dict[str, Any]]:
    items = _as_list(body, "legaltags", "legalTags", "data", "results")
    out: list[dict[str, Any]] = []
    now = _now_ts()
    for it in items:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or it.get("legalTagName") or it.get("id") or "")
        if not name.strip():
            continue
        lid = str(it.get("id") or it.get("legalTagId") or name)
        valid = bool(it.get("isValid", it.get("valid", True)))
        obl = it.get("obligations") or it.get("obligation") or it.get("properties")
        obl_s = json.dumps(obl, default=str) if obl is not None else None
        out.append(
            {
                "legal_tag_name": name,
                "legal_tag_id": lid,
                "is_valid": valid,
                "data_partition_id": data_partition_id,
                "obligations_json": obl_s,
                "raw_json": json.dumps(it, default=str),
                "ingested_at": now,
                "source": source,
            }
        )
    return out


def parse_entitlements_groups_json(
    body: Any,
    *,
    data_partition_id: str,
    source: str,
) -> list[dict[str, Any]]:
    items = _as_list(body, "groups", "members", "results", "data")
    out: list[dict[str, Any]] = []
    now = _now_ts()
    for it in items:
        if not isinstance(it, dict):
            continue
        gid = str(it.get("id") or it.get("groupId") or it.get("email") or "")
        if not gid.strip():
            continue
        gname = str(it.get("name") or it.get("displayName") or gid)
        desc = it.get("description")
        desc_s = str(desc) if desc is not None else ""
        out.append(
            {
                "group_id": gid,
                "group_name": gname,
                "description": desc_s,
                "data_partition_id": data_partition_id,
                "raw_json": json.dumps(it, default=str),
                "ingested_at": now,
                "source": source,
            }
        )
    return out


def parse_acl_like_records(
    records: list[dict[str, Any]],
    *,
    data_partition_id: str,
    source: str,
) -> list[dict[str, Any]]:
    """Normalize list of dicts (e.g. from future Storage ACL API) into mirror rows."""
    now = _now_ts()
    out: list[dict[str, Any]] = []
    for it in records:
        out.append(
            {
                "object_id": str(it.get("object_id", it.get("id", ""))),
                "resource_type": str(it.get("resource_type", it.get("type", ""))),
                "principal_id": str(it.get("principal_id", it.get("principal", ""))),
                "privilege": str(it.get("privilege", it.get("access", ""))),
                "data_partition_id": data_partition_id,
                "raw_json": json.dumps(it, default=str),
                "ingested_at": now,
                "source": source,
            }
        )
    return out
