"""Unity Catalog helpers: pick a catalog where the current principal may create schemas."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

# Built-in Databricks catalogs — users never get CREATE SCHEMA here; probing only adds noise.
_SKIP_PROBE_NAMES = frozenset({"samples", "system"})


def _catalog_probe_enabled(spark: Any) -> bool:
    v = spark.conf.get("adme.connector.catalog_probe", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _catalog_probe_verbose(spark: Any) -> bool:
    v = spark.conf.get("adme.connector.catalog_probe_verbose", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _probe_fail_mode(spark: Any, default_on_probe_fail: str | None) -> str:
    """Return normalized mode: continue | error | ... (empty Spark conf uses *default_on_probe_fail* or error)."""
    v = spark.conf.get("adme.connector.catalog_on_probe_fail", "").strip().lower()
    if v:
        return v
    if default_on_probe_fail and default_on_probe_fail.strip():
        return default_on_probe_fail.strip().lower()
    return "error"


def _probe_fail_is_continue(spark: Any, *, default_on_probe_fail: str | None) -> bool:
    m = _probe_fail_mode(spark, default_on_probe_fail)
    return m in ("continue", "warn", "best_effort", "soft")


def _current_catalog_name(spark: Any) -> str:
    try:
        return str(spark.sql("SELECT current_catalog()").collect()[0][0]).strip("`")
    except Exception:
        return ""


def _uc_log_level(spark: Any) -> str:
    """``minimal`` (default): one summary; ``detailed``: per-step [UC] lines."""
    v = spark.conf.get("adme.connector.uc_log_level", "minimal").strip().lower()
    if v in ("detailed", "verbose", "debug", "full"):
        return "detailed"
    return "minimal"


def _probe_error_summary(exc: BaseException, *, max_len: int = 100) -> str:
    s = str(exc).strip().replace("\n", " ")
    if "PERMISSION_DENIED" in s:
        idx = s.find("PERMISSION_DENIED")
        s = s[idx : idx + max_len + 40]
    elif "FailedOperationAttemptException" in s or "Metadata operation failed" in s:
        s = "hive_metastore metadata operation denied or failed (no CREATE SCHEMA in HMS context)"
    elif "NO_SUCH_CATALOG" in s or "not found" in s.lower():
        idx = s.find("Catalog") if "Catalog" in s else 0
        s = s[idx : idx + max_len + 30]
    else:
        s = " ".join(s.split())
    s = " ".join(s.split())
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _restore_catalog(spark: Any, prev: str) -> None:
    if not (prev or "").strip():
        return
    p = prev.strip().strip("`")
    if not p:
        return
    try:
        spark.sql(f"USE CATALOG `{p}`")
    except Exception:
        pass


def ensure_catalog_schema_for_delta(spark: Any, catalog: str, schema_name: str) -> None:
    """
    Ensure ``schema_name`` exists in *catalog* for Delta writes.

    Runs ``USE CATALOG`` then ``CREATE SCHEMA IF NOT EXISTS`` (session-scoped name first, then
    fully qualified), then restores the previous session catalog. Matches the probe behavior so
    bronze/governance do not rely on three-part DDL alone (some UC setups require an active catalog).
    """
    cat = (catalog or "").strip().strip("`")
    sch = (schema_name or "").strip().strip("`")
    if not cat or not sch:
        raise ValueError("catalog and schema_name are required")
    prev = _current_catalog_name(spark)
    try:
        spark.sql(f"USE CATALOG `{cat}`")
        try:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{sch}`")
        except Exception:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{cat}`.`{sch}`")
    finally:
        _restore_catalog(spark, prev)


def _probe_create_schema(
    spark: Any,
    catalog: str,
    *,
    log: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    """Return ``(True, "")`` if CREATE SCHEMA (then DROP) succeeds in *catalog*.

    On failure returns ``(False, reason)`` where *reason* is a short SQL error summary for logs.

    Runs ``USE CATALOG`` first. Many UC setups deny three-part ``CREATE`` until the session
    catalog is set, even when the principal has CREATE SCHEMA on the catalog.

    Set Spark conf ``adme.connector.catalog_probe_verbose=true`` for full exception lines on *log*.
    """
    cat = (catalog or "").strip().strip("`")
    if not cat:
        return False, ""
    verbose = _catalog_probe_verbose(spark)

    def _detail(msg: str) -> None:
        if verbose and log:
            log(msg)

    probe_schema = f"_adme_uc_probe_{uuid.uuid4().hex[:12]}"
    prev = _current_catalog_name(spark)
    try:
        spark.sql(f"USE CATALOG `{cat}`")
    except Exception as e:
        _detail(f"[UC] probe {cat!r} USE CATALOG failed: {e}")
        _restore_catalog(spark, prev)
        return False, _probe_error_summary(e)
    created_qualified = False
    try:
        try:
            spark.sql(f"CREATE SCHEMA `{probe_schema}`")
        except Exception as e1:
            _detail(f"[UC] probe {cat!r} CREATE SCHEMA (unqualified) failed: {e1}")
            try:
                spark.sql(f"CREATE SCHEMA `{cat}`.`{probe_schema}`")
                created_qualified = True
            except Exception as e2:
                _detail(f"[UC] probe {cat!r} CREATE SCHEMA (qualified) failed: {e2}")
                raise
    except Exception as e:
        _restore_catalog(spark, prev)
        return False, _probe_error_summary(e)
    try:
        if created_qualified:
            spark.sql(f"DROP SCHEMA IF EXISTS `{cat}`.`{probe_schema}`")
        else:
            spark.sql(f"DROP SCHEMA IF EXISTS `{probe_schema}`")
    except Exception:
        try:
            spark.sql(f"DROP SCHEMA IF EXISTS `{cat}`.`{probe_schema}`")
        except Exception:
            pass
    _restore_catalog(spark, prev)
    return True, ""


def _should_probe(c: str) -> bool:
    return c.lower() not in _SKIP_PROBE_NAMES


def _best_effort_catalog(
    explicit: str,
    w: str,
    cats: list[str],
    order: list[str],
) -> str:
    """
    Pick a catalog name without proving CREATE SCHEMA (for API-only / degraded runs).

    Prefer **Unity Catalog** names over ``hive_metastore`` when both appeared in the candidate
    list — HMS often fails the same probe and is a poor default for ``cfg`` / FQN display.
    """
    if explicit:
        return explicit
    if w and w in cats:
        return w
    for c in order:
        if _should_probe(c) and c.lower() != "hive_metastore":
            return c
    for c in order:
        if _should_probe(c):
            return c
    if w:
        return w
    for c in cats:
        if _should_probe(c) and c.lower() != "hive_metastore":
            return c
    for c in cats:
        if _should_probe(c):
            return c
    return cats[0] if cats else ""


def resolve_writable_catalog(
    spark: Any,
    wanted: str,
    *,
    default_on_probe_fail: str | None = None,
    log: Callable[[str], None] | None = None,
) -> tuple[str, bool]:
    """
    Return ``(catalog_name, verified)``.

    ``verified`` is True only if a **CREATE SCHEMA** probe succeeded in the returned catalog.

    Spark conf:

    - ``adme.connector.uc_log_level`` = ``minimal`` (default) | ``detailed`` — minimal prints one
      compact summary; detailed prints step-by-step lines (debugging).
    - ``adme.connector.catalog_probe`` = ``false`` — skip probing; use ``adme.connector.catalog``
      or *wanted*; returns ``verified=False``.
    - ``adme.connector.catalog_on_probe_fail`` / *default_on_probe_fail* — ``continue`` vs ``error``.
    - ``adme.connector.catalog_probe_verbose`` = ``true`` — extra SQL detail during probes
      (works with ``minimal`` for probe internals only).
    """
    w = (wanted or "").strip().strip("`")
    explicit = spark.conf.get("adme.connector.catalog", "").strip().strip("`")
    mode = _probe_fail_mode(spark, default_on_probe_fail)
    level = _uc_log_level(spark)
    probe_detail_log = log if (level == "detailed" or _catalog_probe_verbose(spark)) else None

    def _lg(msg: str) -> None:
        if log:
            log(msg)

    if not _catalog_probe_enabled(spark):
        pick = explicit or w
        if not pick:
            raise RuntimeError(
                "adme.connector.catalog_probe is false but no catalog name is set. Set Spark conf "
                "adme.connector.catalog (or YAML delta.catalog), then re-run."
            )
        if level == "minimal":
            _lg(f"[UC] probe=off | using {pick!r} | verified=False")
        else:
            _lg(
                "[UC] catalog_probe=false -> using "
                f"{pick!r} without CREATE SCHEMA check (verified=False). "
                "Delta writes may still fail without grants."
            )
        return pick, False

    try:
        cats = [str(r[0]).strip("`") for r in spark.sql("SHOW CATALOGS").collect()]
    except Exception:
        _lg("[UC] SHOW CATALOGS failed; using YAML/Spark catalog name only (unverified).")
        return (w or wanted or explicit), False

    non_legacy = [c for c in cats if c.lower() != "hive_metastore"]
    legacy = [c for c in cats if c.lower() == "hive_metastore"]

    order: list[str] = []

    def push(x: str) -> None:
        if x and x in cats and x not in order:
            order.append(x)

    if w:
        push(w)
    for c in non_legacy:
        push(c)
    try:
        cur = str(spark.sql("SELECT current_catalog()").collect()[0][0]).strip("`")
    except Exception:
        cur = ""
    push(cur)

    if level == "minimal":
        _lg(
            f"[UC] wanted={w!r} | explicit={explicit or '-'} | on_fail={mode} | "
            f"show_catalogs={len(cats)} | uc_log_level=minimal (set adme.connector.uc_log_level=detailed for step logs)"
        )
    else:
        _lg(
            "[UC] visible catalogs ("
            + str(len(cats))
            + "): "
            + ", ".join(cats[:20])
            + (" ..." if len(cats) > 20 else "")
        )
        _lg(
            "[UC] wanted="
            + repr(w)
            + " | explicit="
            + (repr(explicit) if explicit else "(not set)")
            + f" | on_fail={mode}"
        )
        _lg("[UC] candidate order (samples/system not probed): " + (" -> ".join(order) if order else "(empty)"))

    tried: list[str] = []
    failures: list[tuple[str, str]] = []

    for c in order:
        if not _should_probe(c):
            if level == "detailed":
                _lg(f"[UC] skip (built-in): {c!r}")
            continue
        tried.append(c)
        if level == "detailed":
            _lg(f"[UC] CREATE SCHEMA probe in {c!r} ...")
        ok, deny = _probe_create_schema(spark, c, log=probe_detail_log)
        if ok:
            if level == "minimal":
                _lg(f"[UC] verified | catalog={c!r}")
            else:
                _lg(f"[UC] OK -> using catalog {c!r} for Delta (CREATE SCHEMA verified).")
            return c, True
        failures.append((c, deny or "denied"))
        if level == "detailed":
            tail = f" — {deny}" if deny else ""
            _lg(f"[UC] denied -> try next{tail}")

    for c in legacy:
        if c in tried or not _should_probe(c):
            continue
        tried.append(c)
        if level == "detailed":
            _lg(f"[UC] CREATE SCHEMA probe in {c!r} (legacy) ...")
        ok, deny = _probe_create_schema(spark, c, log=probe_detail_log)
        if ok:
            if level == "minimal":
                _lg(f"[UC] verified | catalog={c!r}")
            else:
                _lg(f"[UC] OK -> using catalog {c!r} for Delta (CREATE SCHEMA verified).")
            return c, True
        failures.append((c, deny or "denied"))
        if level == "detailed":
            tail = f" — {deny}" if deny else ""
            _lg(f"[UC] denied -> try next{tail}")

    if _probe_fail_is_continue(spark, default_on_probe_fail=default_on_probe_fail):
        pick = _best_effort_catalog(explicit, w, cats, order)
        if not pick:
            raise RuntimeError(
                "adme.connector.catalog_on_probe_fail=continue but no catalog name could be chosen. "
                "Set adme.connector.catalog or YAML delta.catalog."
            )
        if level == "minimal":
            fail_s = " | ".join(f"{a}: {b}" for a, b in failures)[:420]
            if len(fail_s) > 400:
                fail_s = fail_s[:397] + "…"
            _lg(
                f"[UC] unverified | best_effort={pick!r} | failed: {fail_s} | "
                "fix: grants + adme.connector.catalog | optional: skip_bronze_when_uc_unverified=true"
            )
        else:
            _lg(
                "[UC] all probes failed; continuing with best-effort catalog "
                f"{pick!r} (verified=False). "
                "Bronze may still attempt schema DDL; without grants it will fail. "
                "To fail in 1c: adme.connector.catalog_on_probe_fail=error."
            )
        return pick, False

    if level == "minimal":
        fail_s = " | ".join(f"{a}: {b}" for a, b in failures)[:400]
        _lg(f"[UC] FAIL | tried={tried!r} | {fail_s}")
    else:
        _lg("[UC] FAIL: no catalog allowed CREATE SCHEMA. Probed: " + repr(tried))
    raise RuntimeError(
        "No Unity Catalog allowed CREATE SCHEMA for your identity. "
        f"Probed: {tried}. "
        "Ask a metastore admin for USE CATALOG + CREATE SCHEMA (or a personal catalog), then set "
        "adme.connector.catalog on the cluster. "
        "Or set catalog_on_probe_fail=continue (smoke default). "
        "Or catalog_probe=false with adme.connector.catalog if an admin confirms access."
    )
