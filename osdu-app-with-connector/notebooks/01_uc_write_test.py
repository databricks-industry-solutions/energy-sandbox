# Databricks notebook source
# MAGIC %md
# MAGIC # Unity Catalog write test
# MAGIC
# MAGIC **Purpose** — Test whether your cluster identity can **create schemas and write Delta tables** in Unity Catalog.
# MAGIC No ADME credentials needed — purely a Databricks UC privilege check.
# MAGIC
# MAGIC **What it does:**
# MAGIC 1. Lists visible catalogs
# MAGIC 2. Probes each with CREATE SCHEMA (skips `samples` / `system`)
# MAGIC 3. On the first writable catalog: DDL → INSERT → SELECT → cleanup
# MAGIC 4. If managed storage fails (403), tries writing via Spark DataFrame API and `/tmp` fallback
# MAGIC 5. Prints a **Teams-friendly summary**
# MAGIC
# MAGIC **Optional:** set `adme.connector.catalog` to test a specific catalog.

# COMMAND ----------

import uuid
from datetime import datetime, timezone

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1) Discover catalogs

# COMMAND ----------

_explicit = spark.conf.get("adme.connector.catalog", "").strip().strip("`")
_cats = [str(r[0]).strip("`") for r in spark.sql("SHOW CATALOGS").collect()]
_SKIP = {"samples", "system"}

print(f"Visible catalogs ({len(_cats)}): {', '.join(_cats)}")
if _explicit:
    print(f"Explicit catalog from Spark conf: {_explicit!r}")
else:
    print("No adme.connector.catalog set — will probe all candidates.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2) Probe CREATE SCHEMA on each catalog

# COMMAND ----------

def _current_cat():
    try:
        return str(spark.sql("SELECT current_catalog()").collect()[0][0]).strip("`")
    except Exception:
        return ""

def _restore(prev):
    if prev:
        try:
            spark.sql(f"USE CATALOG `{prev}`")
        except Exception:
            pass

def _short(exc, max_len=120):
    s = str(exc).replace("\n", " ")
    if "PERMISSION_DENIED" in s:
        idx = s.find("PERMISSION_DENIED")
        s = s[idx:idx + max_len + 40]
    elif "FailedOperationAttemptException" in s or "Metadata operation" in s:
        s = "hive_metastore metadata op denied/failed"
    elif "403" in s or "not authorized" in s.lower():
        s = "storage 403 — cluster identity lacks access to catalog's managed storage"
    s = " ".join(s.split())
    return s[:max_len] + "…" if len(s) > max_len else s

def probe_catalog(cat):
    """Return (ok, error_msg). Attempts USE CATALOG + CREATE/DROP SCHEMA."""
    prev = _current_cat()
    schema = f"_uc_test_probe_{uuid.uuid4().hex[:10]}"
    try:
        spark.sql(f"USE CATALOG `{cat}`")
    except Exception as e:
        _restore(prev)
        return False, f"USE CATALOG failed: {_short(e)}"
    try:
        try:
            spark.sql(f"CREATE SCHEMA `{schema}`")
        except Exception:
            spark.sql(f"CREATE SCHEMA `{cat}`.`{schema}`")
    except Exception as e:
        _restore(prev)
        return False, f"CREATE SCHEMA failed: {_short(e)}"
    try:
        spark.sql(f"DROP SCHEMA IF EXISTS `{cat}`.`{schema}`")
    except Exception:
        try:
            spark.sql(f"DROP SCHEMA IF EXISTS `{schema}`")
        except Exception:
            pass
    _restore(prev)
    return True, ""

_order = []
if _explicit and _explicit in _cats:
    _order.append(_explicit)
for c in _cats:
    if c.lower() not in _SKIP and c not in _order:
        _order.append(c)

results = {}
_first_writable = None

for c in _order:
    if c.lower() in _SKIP:
        results[c] = (None, "skipped (built-in)")
        continue
    ok, msg = probe_catalog(c)
    results[c] = (ok, msg)
    if ok:
        print(f"  PASS  {c}")
        if _first_writable is None:
            _first_writable = c
    else:
        print(f"  FAIL  {c}  —  {msg}")

for c in _cats:
    if c not in results:
        results[c] = (None, "skipped (built-in)")
        print(f"  SKIP  {c}")

if _first_writable:
    print(f"\nFirst writable catalog: {_first_writable}")
else:
    print("\nNo writable catalog found.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3) Full write round-trip test
# MAGIC Tries **three** approaches on the first writable catalog:
# MAGIC 1. **SQL DDL + INSERT** (standard managed Delta)
# MAGIC 2. **DataFrame API** write (if SQL INSERT hits storage 403)
# MAGIC 3. **External path** `/tmp` Delta write (bypasses managed storage entirely)

# COMMAND ----------

_write_cat = _first_writable
_uid = uuid.uuid4().hex[:8]
_test_schema = f"_uc_write_test_{_uid}"

# Results per approach
_ddl_ok = False
_ddl_err = ""
_sql_insert_ok = False
_sql_insert_err = ""
_df_insert_ok = False
_df_insert_err = ""
_ext_write_ok = False
_ext_write_err = ""
_read_ok = False
_read_err = ""
_storage_blocked = False

if not _write_cat:
    print("Skipping write test — no writable catalog from probes above.")
else:
    prev = _current_cat()
    fqn = f"`{_write_cat}`.`{_test_schema}`.`smoke_row`"

    # --- DDL ---
    try:
        spark.sql(f"USE CATALOG `{_write_cat}`")
        spark.sql(f"CREATE SCHEMA `{_test_schema}`")
        _ddl_ok = True
        print(f"  DDL OK      — schema created in {_write_cat!r}")
    except Exception as e:
        _ddl_err = _short(e, 200)
        print(f"  DDL FAIL    — {_ddl_err}")

    # --- Approach 1: SQL INSERT ---
    if _ddl_ok:
        try:
            spark.sql(f"""
                CREATE TABLE {fqn} (id STRING, ts TIMESTAMP, msg STRING) USING DELTA
            """)
            spark.sql(f"""
                INSERT INTO {fqn} VALUES ('{_uid}', current_timestamp(), 'UC write test')
            """)
            row = spark.sql(f"SELECT * FROM {fqn}").collect()
            if row:
                _sql_insert_ok = True
                _read_ok = True
                print(f"  SQL INSERT  — PASS (read back {len(row)} row(s))")
            else:
                _sql_insert_err = "0 rows returned after INSERT"
                print(f"  SQL INSERT  — WARN: {_sql_insert_err}")
        except Exception as e:
            s = str(e)
            if "403" in s or "not authorized" in s.lower() or "AuthorizationFailure" in s:
                _storage_blocked = True
                _sql_insert_err = "storage 403"
                print("  SQL INSERT  — FAIL: storage 403 (managed storage not accessible)")
            else:
                _sql_insert_err = _short(e, 200)
                print(f"  SQL INSERT  — FAIL: {_sql_insert_err}")
        # Cleanup table for retry
        if not _sql_insert_ok:
            try:
                spark.sql(f"DROP TABLE IF EXISTS {fqn}")
            except Exception:
                pass

    # --- Approach 2: DataFrame API write (if SQL failed with storage 403) ---
    if _ddl_ok and not _sql_insert_ok and _storage_blocked:
        try:
            from pyspark.sql import Row
            df = spark.createDataFrame([Row(id=_uid, ts=datetime.now(timezone.utc), msg="DF write test")])
            df.write.format("delta").mode("overwrite").saveAsTable(
                f"{_write_cat}.{_test_schema}.smoke_df"
            )
            rc = spark.sql(f"SELECT * FROM `{_write_cat}`.`{_test_schema}`.`smoke_df`").collect()
            if rc:
                _df_insert_ok = True
                _read_ok = True
                print(f"  DF WRITE    — PASS (read back {len(rc)} row(s))")
            else:
                _df_insert_err = "0 rows returned"
                print(f"  DF WRITE    — WARN: {_df_insert_err}")
        except Exception as e:
            s = str(e)
            if "403" in s or "not authorized" in s.lower() or "AuthorizationFailure" in s:
                _df_insert_err = "storage 403 (same blocker)"
            else:
                _df_insert_err = _short(e, 200)
            print(f"  DF WRITE    — FAIL: {_df_insert_err}")

    # --- Approach 3: Try multiple external paths to find one that works ---
    if _ddl_ok and not _sql_insert_ok and not _df_insert_ok:
        from pyspark.sql import Row
        _ext_paths = [
            ("dbfs:/tmp", f"dbfs:/tmp/_uc_ext_test_{_uid}"),
            ("dbfs:/FileStore", f"dbfs:/FileStore/_uc_ext_test_{_uid}"),
            ("/tmp (local)", f"/tmp/_uc_ext_test_{_uid}"),
            ("abfss (ADME storage)", f"abfss://uc-test@admeadbelzstsbxscus1.dfs.core.windows.net/_uc_ext_test_{_uid}"),
        ]
        for label, ext_path in _ext_paths:
            try:
                df = spark.createDataFrame([Row(id=_uid, ts=datetime.now(timezone.utc), msg=f"ext {label}")])
                df.write.format("delta").mode("overwrite").save(ext_path)
                rc = spark.read.format("delta").load(ext_path).collect()
                if rc:
                    _ext_write_ok = True
                    _ext_write_err = ""
                    print(f"  EXT WRITE   — PASS via {label} ({ext_path}, {len(rc)} row(s))")
                    print("                Spark CAN write Delta — managed catalog storage is the blocker")
                    break
                else:
                    print(f"  EXT WRITE   — {label}: wrote but 0 rows back")
            except Exception as e:
                print(f"  EXT WRITE   — {label}: FAIL — {_short(e, 150)}")
            # Cleanup
            try:
                dbutils.fs.rm(ext_path, True)
            except Exception:
                try:
                    import shutil
                    shutil.rmtree(ext_path, ignore_errors=True)
                except Exception:
                    pass
        if not _ext_write_ok:
            _ext_write_err = "all external paths failed"
            print("  EXT WRITE   — all paths failed (cluster may have restricted storage access)")

    # --- Cleanup UC objects ---
    for tbl in ("smoke_row", "smoke_df"):
        try:
            spark.sql(f"DROP TABLE IF EXISTS `{_write_cat}`.`{_test_schema}`.`{tbl}`")
        except Exception:
            pass
    try:
        spark.sql(f"DROP SCHEMA IF EXISTS `{_write_cat}`.`{_test_schema}`")
    except Exception:
        pass
    _restore(prev)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4) Diagnostics — storage credentials + external locations
# MAGIC Shows what storage your identity can see (helps admin know what to grant).

# COMMAND ----------

print("--- Storage credentials visible to you ---")
try:
    creds = spark.sql("SHOW STORAGE CREDENTIALS").collect()
    if creds:
        for r in creds:
            print(f"  {r[0]}")
    else:
        print("  (none)")
except Exception as e:
    print(f"  cannot list: {_short(e, 150)}")

print("\n--- External locations visible to you ---")
try:
    locs = spark.sql("SHOW EXTERNAL LOCATIONS").collect()
    if locs:
        for r in locs:
            print(f"  {r[0]:40s}  {r[1] if len(r) > 1 else ''}")
    else:
        print("  (none)")
except Exception as e:
    print(f"  cannot list: {_short(e, 150)}")

print("\n--- Catalog details ---")
if _first_writable:
    try:
        desc = spark.sql(f"DESCRIBE CATALOG EXTENDED `{_first_writable}`").collect()
        for r in desc:
            print(f"  {r[0]:30s}  {r[1]}")
    except Exception as e:
        print(f"  cannot describe: {_short(e, 150)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5) Summary (screenshot for Teams)

# COMMAND ----------

_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
_SEP = "=" * 72
_SUB = "-" * 72

_any_write = _sql_insert_ok or _df_insert_ok
_can_write_somewhere = _any_write or _ext_write_ok

print()
print(_SEP)
print("  Unity Catalog write test — result (screenshot for Teams)")
print(_SEP)
print(f"  When:       {_ts}")
print(f"  Workspace:  {spark.conf.get('spark.databricks.workspaceUrl', '(unknown)')}")
print(f"  Identity:   {spark.sql('SELECT current_user()').collect()[0][0]}")
print(f"  Catalogs:   {len(_cats)} visible")
print(_SUB)

for c in _order:
    ok, msg = results.get(c, (None, ""))
    if ok is True:
        print(f"  PASS  {c}")
    elif ok is False:
        print(f"  FAIL  {c}  —  {msg}")
    else:
        print(f"  SKIP  {c}")
for c in _cats:
    if c not in _order:
        print(f"  SKIP  {c}")

print(_SUB)
print(f"  CREATE SCHEMA:     {'PASS' if _first_writable else 'FAIL'}")
if _write_cat:
    print(f"  DDL (schema):      {'PASS' if _ddl_ok else 'FAIL'}{('  — ' + _ddl_err) if _ddl_err else ''}")
    print(f"  SQL INSERT:        {'PASS' if _sql_insert_ok else 'FAIL'}{('  — ' + _sql_insert_err) if _sql_insert_err else ''}")
    if _storage_blocked and not _sql_insert_ok:
        print(f"  DataFrame write:   {'PASS' if _df_insert_ok else 'FAIL'}{('  — ' + _df_insert_err) if _df_insert_err else ''}")
        print(f"  External /tmp:     {'PASS' if _ext_write_ok else 'FAIL'}{('  — ' + _ext_write_err) if _ext_write_err else ''}")
    print(f"  SELECT (read):     {'PASS' if _read_ok else ('SKIP' if not _any_write else 'FAIL')}")
else:
    print("  DDL / INSERT / SELECT: SKIPPED (no writable catalog)")
print(_SUB)

if _first_writable:
    print(f"  Writable catalog:  {_first_writable}")
else:
    print("  Writable catalog:  NONE")

_actions = []
if not _first_writable:
    _actions.append("ask metastore admin for USE CATALOG + CREATE SCHEMA (or a personal catalog)")
elif _storage_blocked and not _any_write:
    _actions.append("UC grants OK — storage 403 blocks writes")
    _actions.append("ask admin: GRANT READ_FILES, WRITE_FILES ON STORAGE CREDENTIAL <cred> TO poc_users")
    _actions.append("or: admin grants Storage Blob Data Contributor on the metastore ADLS account")
elif _any_write:
    _actions.append(f"set adme.connector.catalog={_first_writable} on your cluster for ADME pipelines")

if _actions:
    print("  Action(s):")
    for a in _actions:
        print(f"    - {a}")

if _any_write:
    _overall = "PASS"
elif _ddl_ok and _ext_write_ok and not _any_write:
    _overall = "PARTIAL — UC DDL OK + Spark can write /tmp, but managed storage 403"
elif _ddl_ok and not _any_write:
    _overall = "PARTIAL — UC DDL OK, managed storage blocked (403)"
elif _first_writable:
    _overall = "FAIL"
else:
    _overall = "FAIL — no writable catalog"
print(f"  OVERALL:  {_overall}")
print(_SEP)
