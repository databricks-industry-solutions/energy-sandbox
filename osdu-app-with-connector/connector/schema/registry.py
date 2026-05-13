"""Delta-backed schema registry with version tracking and automatic table evolution.

Stores every schema version per domain so you can query history, detect drift,
and automatically ALTER TABLE to accommodate new or widened fields.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from connector.schema.inferrer import InferredSchema

logger = logging.getLogger(__name__)


@dataclass
class SchemaDiff:
    """Difference between two InferredSchema versions."""

    new_fields: dict[str, str] = field(default_factory=dict)
    removed_fields: list[str] = field(default_factory=list)
    type_changes: list[dict[str, str]] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.new_fields or self.removed_fields or self.type_changes)

    def summary(self) -> str:
        parts = []
        if self.new_fields:
            parts.append(f"+{len(self.new_fields)} fields")
        if self.removed_fields:
            parts.append(f"-{len(self.removed_fields)} fields")
        if self.type_changes:
            parts.append(f"~{len(self.type_changes)} type changes")
        return ", ".join(parts) or "no changes"


class SchemaRegistry:
    """Track inferred schemas per domain in a Delta table and evolve Bronze tables."""

    def __init__(self, spark: Any, registry_fqn: str) -> None:
        self._spark = spark
        self._fqn = registry_fqn
        self._short_fqn = registry_fqn.split(".", 1)[-1] if "." in registry_fqn else registry_fqn
        self._ensured = False
        self._resolved_fqn: Optional[str] = None

    def _active_fqn(self) -> str:
        """Return the resolved FQN that works on the current cluster."""
        return self._resolved_fqn or self._fqn

    def ensure_table(self) -> None:
        if self._ensured:
            return
        ddl_template = """
            CREATE TABLE IF NOT EXISTS {} (
                registry_id STRING NOT NULL,
                domain STRING NOT NULL,
                version INT NOT NULL,
                inferred_schema STRING NOT NULL,
                field_count INT NOT NULL,
                new_fields STRING,
                removed_fields STRING,
                type_changes STRING,
                sample_size INT,
                discovered_at TIMESTAMP NOT NULL
            )
            USING DELTA
            TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
        """
        for candidate in [self._fqn, self._short_fqn]:
            try:
                self._spark.sql(ddl_template.format(candidate))
                self._resolved_fqn = candidate
                logger.debug("schema_registry table ensured at %s", candidate)
                break
            except Exception as e:
                if "DELTA_PROTOCOL_CHANGED" in str(e) or "already exists" in str(e).lower():
                    self._resolved_fqn = candidate
                    break
                logger.debug("schema_registry CREATE at %s failed: %s", candidate, e)
        self._ensured = True

    def get_latest(self, domain: str) -> tuple[int, Optional[InferredSchema]]:
        """Return (version, InferredSchema) for the latest version, or (0, None)."""
        self.ensure_table()
        fqn = self._active_fqn()
        try:
            rows = self._spark.sql(f"""
                SELECT version, inferred_schema, sample_size
                FROM {fqn}
                WHERE domain = '{domain}'
                ORDER BY version DESC
                LIMIT 1
            """).collect()
        except Exception:
            return 0, None

        if not rows:
            return 0, None

        row = rows[0]
        schema_dict = json.loads(row["inferred_schema"])
        return row["version"], InferredSchema.from_dict(schema_dict, row["sample_size"] or 0)

    def compare(self, domain: str, new_schema: InferredSchema) -> SchemaDiff:
        """Compare *new_schema* against the latest registered version."""
        _, existing = self.get_latest(domain)
        if existing is None:
            return SchemaDiff(
                new_fields=new_schema.to_dict(),
                removed_fields=[],
                type_changes=[],
            )

        old_map = existing.to_dict()
        new_map = new_schema.to_dict()

        diff = SchemaDiff()

        for path, spark_type in new_map.items():
            if path not in old_map:
                diff.new_fields[path] = spark_type
            elif old_map[path] != spark_type:
                diff.type_changes.append({
                    "path": path,
                    "old_type": old_map[path],
                    "new_type": spark_type,
                })

        for path in old_map:
            if path not in new_map:
                diff.removed_fields.append(path)

        return diff

    def register(
        self,
        domain: str,
        schema: InferredSchema,
        diff: SchemaDiff,
    ) -> int:
        """Append a new version row and return the new version number."""
        from pyspark.sql import Row

        self.ensure_table()
        current_version, _ = self.get_latest(domain)
        new_version = current_version + 1

        row = Row(
            registry_id=str(uuid.uuid4()),
            domain=domain,
            version=new_version,
            inferred_schema=json.dumps(schema.to_dict()),
            field_count=len(schema.leaf_fields()),
            new_fields=json.dumps(list(diff.new_fields.keys())) if diff.new_fields else None,
            removed_fields=json.dumps(diff.removed_fields) if diff.removed_fields else None,
            type_changes=json.dumps(diff.type_changes) if diff.type_changes else None,
            sample_size=schema.sample_size,
            discovered_at=datetime.now(timezone.utc),
        )
        df = self._spark.createDataFrame([row])
        fqn = self._active_fqn()
        try:
            df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(fqn)
        except Exception as e:
            if "DELTA_PROTOCOL_CHANGED" in str(e):
                logger.warning("schema registry concurrent write conflict, retrying once")
                import time
                time.sleep(2)
                df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(fqn)
            else:
                raise
        logger.info(
            "schema registry: v%d for %s (%s)",
            new_version, domain, diff.summary(),
        )
        return new_version

    def _resolve_table(self, table_fqn: str) -> str:
        """Try the full FQN first; fall back to schema.table if 3-part fails."""
        try:
            self._spark.table(table_fqn)
            return table_fqn
        except Exception:
            short = table_fqn.split(".", 1)[-1] if "." in table_fqn else table_fqn
            try:
                self._spark.table(short)
                return short
            except Exception:
                return table_fqn

    def evolve_table(self, table_fqn: str, diff: SchemaDiff) -> None:
        """Execute ALTER TABLE statements to bring a Bronze table in line with the diff."""
        resolved = self._resolve_table(table_fqn)
        if diff.new_fields:
            self._add_columns(resolved, diff.new_fields)
        if diff.type_changes:
            self._widen_columns(resolved, diff.type_changes)

    def _add_columns(self, table_fqn: str, new_fields: dict[str, str]) -> None:
        col_defs = []
        for dot_path, spark_type in sorted(new_fields.items()):
            col_name = dot_path.replace(".", "__")
            safe_type = spark_type if not spark_type.startswith("ARRAY") else "STRING"
            col_defs.append(f"`{col_name}` {safe_type}")

        if col_defs:
            ddl = f"ALTER TABLE {table_fqn} ADD COLUMNS ({', '.join(col_defs)})"
            try:
                self._spark.sql(ddl)
                logger.info("schema evolution: added %d columns to %s", len(col_defs), table_fqn)
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug("columns already exist in %s, skipping", table_fqn)
                else:
                    logger.warning("schema evolution add_columns failed on %s: %s", table_fqn, e)

    def _widen_columns(self, table_fqn: str, type_changes: list[dict[str, str]]) -> None:
        """Attempt safe type widening (e.g. INT -> LONG -> DOUBLE -> STRING)."""
        _SAFE_WIDENING = {
            ("INT", "LONG"), ("INT", "DOUBLE"), ("INT", "STRING"),
            ("LONG", "DOUBLE"), ("LONG", "STRING"),
            ("DOUBLE", "STRING"),
            ("BOOLEAN", "STRING"),
        }
        for change in type_changes:
            col_name = change["path"].replace(".", "__")
            old_t = change["old_type"]
            new_t = change["new_type"]
            if (old_t, new_t) in _SAFE_WIDENING:
                try:
                    self._spark.sql(
                        f"ALTER TABLE {table_fqn} ALTER COLUMN `{col_name}` SET DATA TYPE {new_t}"
                    )
                    logger.info("schema evolution: widened %s from %s to %s in %s", col_name, old_t, new_t, table_fqn)
                except Exception as e:
                    logger.warning("could not widen %s: %s", col_name, e)
            else:
                logger.warning(
                    "unsafe type change %s -> %s for %s in %s; skipping",
                    old_t, new_t, col_name, table_fqn,
                )
