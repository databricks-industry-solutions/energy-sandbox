"""Flatten OSDU-style records into silver rows using configured dot paths."""

from __future__ import annotations

from typing import Any, Optional

from connector.models.config import DomainConfig, NormalizationConfig


def get_by_path(record: Any, dotted: str) -> Any:
    cur: Any = record
    for part in dotted.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def normalize_record(raw: dict[str, Any], domain: DomainConfig) -> dict[str, Any]:
    """Produce a flat dict for silver merge (includes domain name and raw id/kind/timestamps)."""
    norm = domain.normalization
    row: dict[str, Any] = {
        "domain": domain.name,
        "record_id": get_by_path(raw, norm.record_id_path),
        "kind": get_by_path(raw, norm.record_kind_path),
        "modify_time": get_by_path(raw, norm.modify_time_path),
    }
    for silver_col, path in norm.field_map.items():
        val = get_by_path(raw, path)
        row[silver_col] = val  # None when path doesn't exist — safe for schema evolution
    row["_raw_ref"] = None
    return row


def max_watermark_from_records(
    records: list[dict[str, Any]],
    incremental_field_path: str,
) -> Optional[str]:
    """Best-effort max watermark string from a batch (for incremental)."""
    best: Optional[str] = None
    for r in records:
        v = get_by_path(r, incremental_field_path)
        if v is None:
            continue
        s = str(v)
        if best is None or s > best:
            best = s
    return best
