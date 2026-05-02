# Databricks notebook source
# MAGIC %md
# MAGIC # Run ADME connector — all Phase 1 domains
# MAGIC
# MAGIC Operational entry: loops `conf/domains/*.yaml` with `phase: 1`, runs incremental or full load.
# MAGIC **Lakeflow / DLT** — replace this loop with pipeline tasks or Auto Loader + `MERGE` notebooks.
# MAGIC
# MAGIC **Unity Catalog** — Default: **`adme.connector.require_uc_verified=false`** (warn and **continue** if the CREATE SCHEMA probe fails; DDL may still error without grants). Set **`adme.connector.require_uc_verified=true`** to **fail fast** when no catalog passes the probe (recommended once UC grants exist). Grant **USE CATALOG** + **CREATE SCHEMA** on your catalog, or set **`adme.connector.catalog`**. **`adme.connector.catalog_probe=false`** skips probing and uses **`adme.connector.catalog`** as-is.

# COMMAND ----------

# MAGIC %pip install -q 'httpx>=0.27' 'azure-identity>=1.15' 'pydantic>=2.5' 'PyYAML>=6' 'tenacity>=8'

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import base64
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional


def _project_root_from_walk(start: Path) -> Optional[Path]:
    """
    Resolve bundle ``.../files`` (``files/connector``) or flat ``.../connector``.

    Skip the bundle branch when ``p.name == "notebooks"`` so we never resolve
    ``.../notebooks/files/connector`` (Workspace 404).
    """
    try:
        b = start.resolve()
    except Exception:
        return None
    for p in [b, *b.parents]:
        if (p / "connector" / "__init__.py").is_file():
            return p
        if p.name == "notebooks":
            continue
        if (p / "files" / "connector" / "__init__.py").is_file():
            return (p / "files").resolve()
    return None


def _detect_repo_root() -> Path:
    """
    Same rules as smoke notebook 00: invalid ``adme.connector.repo_root`` must fall through
    (do not use a bare ``.../notebooks`` path — that can produce ``.../notebooks/files`` 404s).
    """
    conf_root = spark.conf.get("adme.connector.repo_root", "").strip()
    if conf_root:
        p = Path(conf_root).expanduser().resolve()
        found = _project_root_from_walk(p)
        if found is not None:
            return found

    notebook_dir: Optional[Path] = None
    try:
        _ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()  # noqa: F821
        _raw = _ctx.notebookPath().get()
        if _raw:
            nb = Path(_raw)
            if not nb.is_absolute():
                nb = Path("/Workspace") / str(nb).lstrip("/")
            notebook_dir = nb.parent
    except Exception:
        pass

    for base in ([notebook_dir] if notebook_dir is not None else []) + [Path.cwd()]:
        found = _project_root_from_walk(base)
        if found is not None:
            return found

    return Path.cwd().resolve()


def _databricks_workspace_api_base() -> str:
    u = spark.conf.get("spark.databricks.workspaceUrl", "").strip().rstrip("/")
    if not u:
        return ""
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return "https://" + u


def _read_workspace_file_via_export_api(abs_path: Path) -> Optional[bytes]:
    s = str(abs_path)
    if not s.startswith("/Workspace"):
        return None
    ws_path = s[len("/Workspace") :]
    base = _databricks_workspace_api_base()
    if not base:
        return None
    try:
        tok = (
            dbutils.notebook.entry_point.getDbutils()
            .notebook()
            .getContext()
            .apiToken()
            .get()
        )
    except Exception:
        return None
    if not tok:
        return None

    def _one(fmt: str) -> Optional[bytes]:
        q = urllib.parse.urlencode({"path": ws_path, "format": fmt})
        url = f"{base}/api/2.0/workspace/export?{q}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError):
            return None
        raw = body.get("content")
        if not raw:
            return None
        try:
            return base64.b64decode(raw)
        except (ValueError, TypeError):
            return None

    out = _one("AUTO")
    return out if out else _one("SOURCE")


def _read_workspace_file_fast(src_file: Path) -> bytes:
    for _ in range(4):
        try:
            data = src_file.read_bytes()
        except OSError:
            data = b""
        if data:
            return data
        time.sleep(0.04)
    api_data = _read_workspace_file_via_export_api(src_file)
    if api_data:
        return api_data
    try:
        r = subprocess.run(
            ["/bin/cat", "--", str(src_file)],
            capture_output=True,
            timeout=20,
            check=False,
        )
        if r.stdout:
            return r.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        return src_file.read_bytes()
    except OSError:
        return b""


def _materialize_connector_and_conf_only(src: Path, dst: Path) -> None:
    if dst.is_dir():
        shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    for top in ("connector", "conf"):
        s_top = src / top
        if not s_top.is_dir():
            if top == "connector":
                raise OSError(f"missing {src}/{top}")
            continue
        print(f"Materialize → {top}/ …")
        n = 0
        for root, _, files in os.walk(s_top, topdown=True, followlinks=False):
            rel_within = Path(root).relative_to(s_top)
            for fname in files:
                if fname.startswith("."):
                    continue
                sp = Path(root) / fname
                dp = dst / top / rel_within / fname
                dp.parent.mkdir(parents=True, exist_ok=True)
                dp.write_bytes(_read_workspace_file_fast(sp))
                n += 1
                if n % 30 == 0:
                    print(f"   … {top}: {n} files")
        print(f"   done {top}/: {n} files")


def _materialize_workspace_tree(src: Path) -> tuple[Path, bool]:
    if not str(src).startswith("/Workspace"):
        return src, False
    dst = Path(tempfile.gettempdir()) / "adme_osdu_connector_materialized"
    try:
        _materialize_connector_and_conf_only(src, dst)
    except OSError as e:
        print(f"WARN: materialize failed ({e}); using Workspace: {src}")
        return src, False
    print(f"Materialized (connector+conf only): {src} -> {dst}")
    return dst, True


_workspace_src = _detect_repo_root()
REPO_ROOT, _copied = _materialize_workspace_tree(_workspace_src)
if _copied:
    ws = str(_workspace_src)
    sys.path[:] = [p for p in sys.path if p != ws and not str(p).startswith(ws + os.sep)]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

for _k in list(sys.modules):
    if _k == "connector" or _k.startswith("connector."):
        del sys.modules[_k]

if not (REPO_ROOT / "connector" / "__init__.py").is_file():
    raise ModuleNotFoundError(
        "Cannot import `connector`. For bundle sync use .../adme_osdu_connector/files. "
        f"Detected REPO_ROOT={REPO_ROOT}. Set adme.connector.repo_root if needed."
    )

_ap_path = REPO_ROOT / "connector" / "auth" / "auth_provider.py"
_ap_text = _ap_path.read_text(encoding="utf-8", errors="replace")
if "class AuthProvider" not in _ap_text:
    raise ImportError(
        f"{_ap_path} missing AuthProvider (len={len(_ap_text)}). Re-sync bundle; "
        "rm -rf /tmp/adme_osdu_connector_materialized on the cluster."
    )

sys.dont_write_bytecode = True
for _pc in list(REPO_ROOT.rglob("__pycache__")):
    if _pc.is_dir():
        shutil.rmtree(_pc, ignore_errors=True)
importlib.invalidate_caches()

from connector.auth.auth_provider import AuthProvider
from connector.config_loader import load_runtime_config
from connector.domains.registry import load_domains_from_dir
from connector.models.config import LoadType
from connector.pipelines.orchestration import DomainIngestionRunner
from connector.storage.checkpoint import DeltaCheckpointStore
from connector.utils.uc_catalog import ensure_catalog_schema_for_delta, resolve_writable_catalog

_runtime_yaml = REPO_ROOT / "conf" / "connector_runtime.yaml"
RUNTIME_YAML = _runtime_yaml if _runtime_yaml.is_file() else REPO_ROOT / "conf" / "connector_runtime.example.yaml"
DOMAINS_DIR = REPO_ROOT / "conf" / "domains"

runtime = load_runtime_config(RUNTIME_YAML)
runtime.base_url = spark.conf.get("adme.connector.base_url", runtime.base_url)
runtime.data_partition_id = spark.conf.get("adme.connector.data_partition_id", runtime.data_partition_id)
runtime.auth.tenant_id = spark.conf.get("adme.connector.tenant_id", runtime.auth.tenant_id)
runtime.auth.adme_api_client_id = spark.conf.get(
    "adme.connector.adme_api_client_id", runtime.auth.adme_api_client_id
)
mi = spark.conf.get("adme.connector.managed_identity_client_id", "").strip()
if mi:
    runtime.auth.managed_identity_client_id = mi
_cat = spark.conf.get("adme.connector.catalog", "").strip() or runtime.delta.catalog
runtime.delta.catalog, _uc_write_ok = resolve_writable_catalog(
    spark,
    _cat,
    default_on_probe_fail="continue",
    log=print,
)
print(
    "Delta catalog:",
    runtime.delta.catalog,
    "| CREATE SCHEMA verified:",
    _uc_write_ok,
    "| wanted:",
    repr(_cat),
)
_require_uc = spark.conf.get("adme.connector.require_uc_verified", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
if not _uc_write_ok and _require_uc:
    raise RuntimeError(
        "No catalog passed the CREATE SCHEMA probe — stopping because adme.connector.require_uc_verified=true. "
        "Grant USE CATALOG + CREATE SCHEMA on your catalog, set adme.connector.catalog, or set "
        "adme.connector.require_uc_verified=false (default) to attempt DDL anyway. "
        "Use notebook 00 for API-only smoke when you have no UC DDL yet."
    )
if not _uc_write_ok:
    print(
        "WARN: UC CREATE SCHEMA probe did not verify — continuing (default require_uc_verified=false). "
        "If schema/table DDL fails below, grant CREATE SCHEMA on the catalog or choose a writable catalog. "
        "Set require_uc_verified=true to fail here instead."
    )
runtime.delta.schema_name = spark.conf.get("adme.connector.schema", runtime.delta.schema_name)

LOAD = spark.conf.get("adme.connector.load_type", "incremental").strip().lower()
runtime.load_type = LoadType.full if LOAD == "full" else LoadType.incremental

ensure_catalog_schema_for_delta(spark, runtime.delta.catalog, runtime.delta.schema_name)

domains = load_domains_from_dir(DOMAINS_DIR)
phase1 = {k: v for k, v in domains.items() if v.phase == 1}
print("Domains:", list(phase1.keys()), "load_type:", runtime.load_type.value)

ckpt = DeltaCheckpointStore(spark, runtime)
ckpt.ensure_table()

runner = DomainIngestionRunner(runtime, AuthProvider(runtime.auth), ckpt, spark=spark)
summaries = []
for name, cfg in phase1.items():
    print("--- Running", name, "---")
    summaries.append(runner.run(cfg, load_type=runtime.load_type))

for s in summaries:
    print(s)
