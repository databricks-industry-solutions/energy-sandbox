"""Recursive JSON flattener with auto / hybrid / explicit modes.

Converts a nested OSDU record dict into a flat dict ready for a Spark Row,
using the InferredSchema to determine column names and types.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from connector.schema.inferrer import InferredSchema

logger = logging.getLogger(__name__)


def _safe_column_name(dot_path: str) -> str:
    """Convert a dot-path to a safe Delta column name."""
    return dot_path.replace(".", "__")


def _get_by_path(record: Any, dotted: str) -> Any:
    """Walk a dot-path into a nested dict, returning None on missing keys."""
    cur: Any = record
    for part in dotted.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _coerce_value(value: Any, spark_type: str, array_stringify: bool) -> Any:
    """Coerce a Python value to match the target Spark SQL type."""
    if value is None:
        return None

    if spark_type == "STRING":
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return str(value)

    if spark_type == "INT":
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    if spark_type == "LONG":
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    if spark_type == "DOUBLE":
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    if spark_type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    if spark_type.startswith("ARRAY"):
        if not isinstance(value, list):
            return None
        if array_stringify:
            return json.dumps(value, default=str)
        return value

    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value


class RecordFlattener:
    """Flatten a raw OSDU record into a dict suitable for a Spark Row.

    Modes:
        auto     — recursively flatten all keys; no field_map needed.
        hybrid   — field_map entries get clean names; rest auto-flatten.
        explicit — only field_map entries; everything else -> _extra.
    """

    def __init__(
        self,
        schema: InferredSchema,
        *,
        flatten_mode: str = "hybrid",
        field_map: Optional[dict[str, str]] = None,
        max_depth: int = 3,
        array_stringify: bool = False,
        exclude_paths: Optional[set[str]] = None,
    ) -> None:
        self._schema = schema
        self._mode = flatten_mode
        self._field_map = field_map or {}
        self._max_depth = max_depth
        self._array_stringify = array_stringify
        self._exclude = exclude_paths or set()

        self._reverse_field_map = {v: k for k, v in self._field_map.items()}

    def flatten(self, record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return (flat_row, extra_dict).

        flat_row: column_name -> coerced value for all schema fields.
        extra_dict: paths not covered by the schema (for _extra VARIANT).
        """
        flat: dict[str, Any] = {}
        covered_paths: set[str] = set()

        if self._mode == "explicit":
            flat, covered_paths = self._flatten_explicit(record)
        elif self._mode == "hybrid":
            flat, covered_paths = self._flatten_hybrid(record)
        else:
            flat, covered_paths = self._flatten_auto(record)

        extra = self._collect_extra(record, covered_paths)
        return flat, extra

    def _flatten_explicit(self, record: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
        """Only field_map entries become columns."""
        flat: dict[str, Any] = {}
        covered: set[str] = set()
        for col_name, dot_path in self._field_map.items():
            val = _get_by_path(record, dot_path)
            fi = self._schema.fields.get(dot_path)
            spark_type = fi.spark_type if fi else "STRING"
            flat[col_name] = _coerce_value(val, spark_type, self._array_stringify)
            covered.add(dot_path)
        return flat, covered

    def _flatten_hybrid(self, record: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
        """field_map entries get clean names; remaining schema fields auto-flatten."""
        flat: dict[str, Any] = {}
        covered: set[str] = set()

        for col_name, dot_path in self._field_map.items():
            val = _get_by_path(record, dot_path)
            fi = self._schema.fields.get(dot_path)
            spark_type = fi.spark_type if fi else "STRING"
            flat[col_name] = _coerce_value(val, spark_type, self._array_stringify)
            covered.add(dot_path)

        for dot_path, fi in self._schema.leaf_fields().items():
            if dot_path in covered or dot_path in self._exclude:
                continue
            val = _get_by_path(record, dot_path)
            col_name = fi.column_name
            flat[col_name] = _coerce_value(val, fi.spark_type, self._array_stringify)
            covered.add(dot_path)

        return flat, covered

    def _flatten_auto(self, record: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
        """Recursively flatten all schema fields into columns."""
        flat: dict[str, Any] = {}
        covered: set[str] = set()

        for dot_path, fi in self._schema.leaf_fields().items():
            if dot_path in self._exclude:
                continue
            val = _get_by_path(record, dot_path)
            col_name = fi.column_name
            flat[col_name] = _coerce_value(val, fi.spark_type, self._array_stringify)
            covered.add(dot_path)

        return flat, covered

    def _collect_extra(
        self, record: dict[str, Any], covered: set[str]
    ) -> dict[str, Any]:
        """Gather fields not covered by the schema into a dict for _extra."""
        extra: dict[str, Any] = {}
        self._walk_extra(record, "", 0, covered, extra)
        return extra

    def _walk_extra(
        self,
        obj: Any,
        prefix: str,
        depth: int,
        covered: set[str],
        extra: dict[str, Any],
    ) -> None:
        if not isinstance(obj, dict):
            return
        for key, value in obj.items():
            dot_path = f"{prefix}.{key}" if prefix else key
            if dot_path in covered:
                continue
            if isinstance(value, dict) and depth < self._max_depth:
                self._walk_extra(value, dot_path, depth + 1, covered, extra)
            else:
                extra[dot_path] = value
