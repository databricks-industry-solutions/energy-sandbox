"""Tests for Unity Catalog writable resolution (mock Spark)."""

from __future__ import annotations

import unittest
from typing import Any

from connector.utils.uc_catalog import ensure_catalog_schema_for_delta, resolve_writable_catalog


class _MockConf:
    def __init__(self, kv: dict[str, str] | None = None) -> None:
        self._kv = dict(kv or {})

    def get(self, k: str, default: str = "") -> str:
        return self._kv[k] if k in self._kv else default


class _Row:
    def __init__(self, v: str) -> None:
        self._v = v

    def __getitem__(self, i: int) -> str:
        if i == 0:
            return self._v
        raise IndexError


class _MockSpark:
    def __init__(
        self,
        *,
        catalogs: list[str],
        writable: set[str],
        current_catalog: str = "workspace_cat",
        conf: dict[str, str] | None = None,
    ) -> None:
        self.catalogs = catalogs
        self.writable = writable
        self.current_catalog = current_catalog
        self.conf = _MockConf(conf)
        self.sql_calls: list[str] = []

    def sql(self, q: str) -> Any:
        self.sql_calls.append(q)
        q_up = q.upper().strip()
        if q_up.startswith("SHOW CATALOGS"):
            return _Collect([_Row(c) for c in self.catalogs])
        if "CURRENT_CATALOG" in q_up:
            return _Collect([_Row(self.current_catalog)])
        if q_up.startswith("USE CATALOG"):
            parts = q.split("`")
            if len(parts) >= 2:
                self.current_catalog = parts[1]
            return _Collect([])
        if q_up.startswith("CREATE SCHEMA"):
            parts = q.split("`")
            # `catalog`.`schema` (fully qualified)
            if len(parts) >= 5 and parts[2] == ".":
                cat = parts[1]
                if cat in self.writable:
                    return _Collect([])
                raise Exception("PERMISSION_DENIED")
            # `schema` only (after USE CATALOG)
            if len(parts) >= 2:
                if self.current_catalog in self.writable:
                    return _Collect([])
                raise Exception("PERMISSION_DENIED")
        if q_up.startswith("DROP SCHEMA"):
            return _Collect([])
        raise AssertionError(f"unexpected SQL: {q!r}")


class _Collect:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def collect(self) -> list[_Row]:
        return list(self._rows)


class ResolveWritableCatalogTests(unittest.TestCase):
    def test_skips_workspace_cat_when_not_writable(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore", "workspace_cat", "my_dev"],
            writable={"my_dev"},
            current_catalog="workspace_cat",
        )
        out, ok = resolve_writable_catalog(spark, "main")
        self.assertEqual(out, "my_dev")
        self.assertTrue(ok)

    def test_uses_wanted_when_writable(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore", "main", "workspace_cat"],
            writable={"main"},
            current_catalog="workspace_cat",
        )
        out, ok = resolve_writable_catalog(spark, "main")
        self.assertEqual(out, "main")
        self.assertTrue(ok)

    def test_raises_when_none_writable(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore", "workspace_cat"],
            writable=set(),
            current_catalog="workspace_cat",
        )
        with self.assertRaises(RuntimeError) as ctx:
            resolve_writable_catalog(spark, "x")
        self.assertIn("CREATE SCHEMA", str(ctx.exception))

    def test_continue_on_probe_fail(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore", "workspace_cat"],
            writable=set(),
            current_catalog="workspace_cat",
            conf={"adme.connector.catalog_on_probe_fail": "continue"},
        )
        out, ok = resolve_writable_catalog(spark, "main")
        self.assertFalse(ok)
        self.assertEqual(out, "workspace_cat")

    def test_continue_via_default_parameter_when_conf_unset(self) -> None:
        """Smoke notebook passes default_on_probe_fail=continue when Spark conf is blank."""
        spark = _MockSpark(
            catalogs=["hive_metastore", "workspace_cat"],
            writable=set(),
            current_catalog="workspace_cat",
            conf={},
        )
        out, ok = resolve_writable_catalog(spark, "main", default_on_probe_fail="continue")
        self.assertFalse(ok)
        self.assertEqual(out, "workspace_cat")

    def test_continue_best_effort_prefers_uc_over_hive_metastore(self) -> None:
        """After probes fail, do not pick hive_metastore if a UC catalog was also listed."""
        spark = _MockSpark(
            catalogs=["hive_metastore", "my_workspace_uc"],
            writable=set(),
            current_catalog="hive_metastore",
            conf={"adme.connector.catalog_on_probe_fail": "continue"},
        )
        out, ok = resolve_writable_catalog(spark, "main", default_on_probe_fail="continue")
        self.assertFalse(ok)
        self.assertEqual(out, "my_workspace_uc")

    def test_continue_prefers_explicit_catalog(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore", "workspace_cat"],
            writable=set(),
            current_catalog="workspace_cat",
            conf={
                "adme.connector.catalog_on_probe_fail": "continue",
                "adme.connector.catalog": "admin_catalog",
            },
        )
        out, ok = resolve_writable_catalog(spark, "main")
        self.assertFalse(ok)
        self.assertEqual(out, "admin_catalog")

    def test_probe_disabled_uses_explicit_catalog(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore"],
            writable=set(),
            conf={
                "adme.connector.catalog_probe": "false",
                "adme.connector.catalog": "team_catalog",
            },
        )
        out, ok = resolve_writable_catalog(spark, "main")
        self.assertEqual(out, "team_catalog")
        self.assertFalse(ok)
        self.assertEqual(spark.sql_calls, [])

    def test_probe_disabled_falls_back_to_wanted(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore"],
            writable=set(),
            conf={"adme.connector.catalog_probe": "false"},
        )
        out, ok = resolve_writable_catalog(spark, "legacy_name")
        self.assertEqual(out, "legacy_name")
        self.assertFalse(ok)

    def test_samples_catalog_is_not_probed(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore", "workspace_cat", "samples", "my_dev"],
            writable={"my_dev"},
            current_catalog="workspace_cat",
        )
        resolve_writable_catalog(spark, "main")
        for q in spark.sql_calls:
            if "CREATE SCHEMA" in q and "samples" in q:
                self.fail(f"should not probe samples: {q!r}")

    def test_probe_disabled_without_catalog_raises(self) -> None:
        spark = _MockSpark(
            catalogs=["x"],
            writable=set(),
            conf={"adme.connector.catalog_probe": "false"},
        )
        with self.assertRaises(RuntimeError) as ctx:
            resolve_writable_catalog(spark, "")
        self.assertIn("catalog_probe", str(ctx.exception))

    def test_denied_probe_appends_sql_error_summary(self) -> None:
        """Failed probes should surface a short exception message on the log callback."""
        spark = _MockSpark(
            catalogs=["hive_metastore", "workspace_uc"],
            writable=set(),
            current_catalog="workspace_uc",
            conf={"adme.connector.catalog_on_probe_fail": "continue"},
        )
        lines: list[str] = []

        def capture(msg: str) -> None:
            lines.append(msg)

        resolve_writable_catalog(spark, "main", default_on_probe_fail="continue", log=capture)
        joined = "\n".join(lines)
        self.assertIn("PERMISSION_DENIED", joined)
        self.assertTrue(
            any("unverified" in x and "failed:" in x for x in lines)
            or any("denied" in x and "try next" in x for x in lines),
            lines,
        )

    def test_ensure_catalog_schema_uses_catalog_then_if_not_exists(self) -> None:
        spark = _MockSpark(
            catalogs=["hive_metastore", "ws_cat"],
            writable={"ws_cat"},
            current_catalog="hive_metastore",
        )
        ensure_catalog_schema_for_delta(spark, "ws_cat", "adme_osdu")
        joined = " | ".join(spark.sql_calls)
        self.assertIn("USE CATALOG", joined)
        self.assertIn("ws_cat", joined)
        self.assertIn("CREATE SCHEMA IF NOT EXISTS", joined)
        self.assertIn("adme_osdu", joined)

    def test_ensure_catalog_schema_requires_names(self) -> None:
        spark = _MockSpark(
            catalogs=["ws_cat"],
            writable={"ws_cat"},
            current_catalog="ws_cat",
        )
        with self.assertRaises(ValueError):
            ensure_catalog_schema_for_delta(spark, "", "s")


if __name__ == "__main__":
    unittest.main()
