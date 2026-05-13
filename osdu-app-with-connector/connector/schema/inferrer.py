"""Recursive type inference engine for raw OSDU JSON records.

Walks every key path across a batch of records, tracks Python types at each path,
and resolves conflicts via promotion rules to produce a Spark-compatible schema.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Spark SQL type names (strings so the module works without Spark at import time) ──

_PROMOTION_ORDER = ["BOOLEAN", "INT", "LONG", "DOUBLE", "STRING"]
_PROMOTION_RANK = {t: i for i, t in enumerate(_PROMOTION_ORDER)}


def _python_type_to_spark(value: Any) -> str:
    """Map a single Python value to a Spark SQL type string."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "LONG" if abs(value) > 2_147_483_647 else "INT"
    if isinstance(value, float):
        return "DOUBLE"
    if isinstance(value, dict):
        return "STRUCT"
    if isinstance(value, list):
        return "ARRAY"
    return "STRING"


def _promote(a: str, b: str) -> str:
    """Return the wider of two scalar Spark SQL types."""
    if a == b:
        return a
    if a == "NULL":
        return b
    if b == "NULL":
        return a
    ra = _PROMOTION_RANK.get(a)
    rb = _PROMOTION_RANK.get(b)
    if ra is not None and rb is not None:
        return _PROMOTION_ORDER[max(ra, rb)]
    return "STRING"


@dataclass
class FieldInfo:
    """Inferred metadata for a single dot-path in the JSON tree."""

    dot_path: str
    spark_type: str  # e.g. "STRING", "DOUBLE", "ARRAY<STRING>", "STRUCT"
    nullable: bool = True
    depth: int = 0
    is_array: bool = False
    children: dict[str, FieldInfo] = field(default_factory=dict)

    @property
    def column_name(self) -> str:
        """Safe Delta column name: dots -> double underscores."""
        return self.dot_path.replace(".", "__")

    def to_ddl(self) -> str:
        """Spark SQL DDL fragment for this field (leaf only)."""
        return f"`{self.column_name}` {self.spark_type}"


@dataclass
class InferredSchema:
    """Complete inferred schema for a domain's records."""

    fields: dict[str, FieldInfo] = field(default_factory=dict)
    sample_size: int = 0

    def leaf_fields(self) -> dict[str, FieldInfo]:
        """Return only leaf-level fields (no intermediate STRUCTs that have children)."""
        return {
            k: v for k, v in self.fields.items()
            if v.spark_type != "STRUCT" or not v.children
        }

    def column_names(self) -> list[str]:
        return sorted(fi.column_name for fi in self.leaf_fields().values())

    def to_dict(self) -> dict[str, str]:
        """Serialisable representation: {dot_path: spark_type}."""
        return {fi.dot_path: fi.spark_type for fi in self.leaf_fields().values()}

    @classmethod
    def from_dict(cls, d: dict[str, str], sample_size: int = 0) -> InferredSchema:
        """Reconstruct from the serialised dict form."""
        schema = cls(sample_size=sample_size)
        for dot_path, spark_type in d.items():
            depth = dot_path.count(".")
            schema.fields[dot_path] = FieldInfo(
                dot_path=dot_path,
                spark_type=spark_type,
                depth=depth,
                is_array=spark_type.startswith("ARRAY"),
            )
        return schema


class SchemaInferrer:
    """Infer a typed schema from a batch of raw OSDU JSON dicts."""

    def __init__(
        self,
        *,
        max_depth: int = 3,
        type_overrides: Optional[dict[str, str]] = None,
        exclude_paths: Optional[list[str]] = None,
    ) -> None:
        self._max_depth = max_depth
        self._overrides = type_overrides or {}
        self._exclude = set(exclude_paths or [])

    def infer(self, records: list[dict[str, Any]]) -> InferredSchema:
        """Walk *records* and return a merged InferredSchema."""
        type_map: dict[str, str] = {}
        nullable_map: dict[str, bool] = {}
        all_paths: set[str] = set()

        for rec in records:
            rec_paths: set[str] = set()
            self._walk(rec, "", 0, type_map, nullable_map, rec_paths)
            all_paths.update(rec_paths)

            for existing in type_map:
                if existing not in rec_paths:
                    nullable_map[existing] = True

        for path, override_type in self._overrides.items():
            if path in type_map or path in all_paths:
                type_map[path] = override_type.upper()

        schema = InferredSchema(sample_size=len(records))
        for dot_path, spark_type in type_map.items():
            depth = dot_path.count(".")
            schema.fields[dot_path] = FieldInfo(
                dot_path=dot_path,
                spark_type=spark_type,
                nullable=nullable_map.get(dot_path, True),
                depth=depth,
                is_array=spark_type.startswith("ARRAY"),
            )
        return schema

    def _walk(
        self,
        obj: Any,
        prefix: str,
        depth: int,
        type_map: dict[str, str],
        nullable_map: dict[str, bool],
        rec_paths: set[str],
    ) -> None:
        if not isinstance(obj, dict):
            return
        for key, value in obj.items():
            dot_path = f"{prefix}.{key}" if prefix else key
            if dot_path in self._exclude:
                continue

            py_type = _python_type_to_spark(value)

            if py_type == "STRUCT" and depth < self._max_depth:
                self._walk(value, dot_path, depth + 1, type_map, nullable_map, rec_paths)
                continue

            if py_type == "ARRAY":
                resolved = self._infer_array_type(value, dot_path, depth)
                rec_paths.add(dot_path)
                existing = type_map.get(dot_path)
                if existing is None:
                    type_map[dot_path] = resolved
                elif existing != resolved:
                    type_map[dot_path] = "STRING"
                if value is None:
                    nullable_map.setdefault(dot_path, True)
                continue

            if py_type == "STRUCT" and depth >= self._max_depth:
                py_type = "STRING"

            rec_paths.add(dot_path)
            existing = type_map.get(dot_path)
            if existing is None:
                type_map[dot_path] = py_type
            else:
                type_map[dot_path] = _promote(existing, py_type)

            if value is None:
                nullable_map.setdefault(dot_path, True)

    def _infer_array_type(self, arr: list, dot_path: str, depth: int) -> str:
        """Determine the element type of a JSON array."""
        if not arr:
            return "ARRAY<STRING>"

        elem_types: set[str] = set()
        for elem in arr:
            et = _python_type_to_spark(elem)
            if et == "STRUCT" and depth < self._max_depth:
                return "ARRAY<STRING>"
            elem_types.add(et)

        elem_types.discard("NULL")
        if not elem_types:
            return "ARRAY<STRING>"
        if len(elem_types) == 1:
            t = elem_types.pop()
            if t == "STRUCT":
                return "ARRAY<STRING>"
            return f"ARRAY<{t}>"

        resolved = "STRING"
        for t in elem_types:
            resolved = _promote(resolved, t)
        return f"ARRAY<{resolved}>"
