# Databricks notebook source
# MAGIC %md
# MAGIC # `03_governance_sync` — Governance mirror to Unity Catalog
# MAGIC
# MAGIC Syncs **legal tags** and **entitlements groups** from ADME (`/api/legal/...`, `/api/entitlements/...`) into Delta tables. Fills gaps with **mock rows** so the pipeline always demonstrates UC tables.
# MAGIC
# MAGIC **ACL-style table** (`gov_record_acl_mirror`) is **mock-only** until a stable Storage/Record ACL API is wired.
# MAGIC
# MAGIC **Spark conf (optional):**
# MAGIC - `adme.connector.governance.force_mock` = `true` — skip HTTP, mock-only (offline demo).
# MAGIC - `adme.connector.governance.append_mock_when_live` = `true` — append mock rows when ADME returns data.
# MAGIC
# MAGIC Uses the same bundle path materialization as `02_run_all_domains`.

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
from connector.governance.sync import sync_governance_mirror
from connector.utils.logging import setup_logging
from connector.utils.uc_catalog import resolve_writable_catalog

setup_logging()

_runtime_yaml = REPO_ROOT / "conf" / "connector_runtime.yaml"
RUNTIME_YAML = _runtime_yaml if _runtime_yaml.is_file() else REPO_ROOT / "conf" / "connector_runtime.example.yaml"

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
runtime.delta.catalog, _uc_gov_verified = resolve_writable_catalog(
    spark,
    _cat,
    default_on_probe_fail="continue",
    log=print,
)
_require_uc = spark.conf.get("adme.connector.require_uc_verified", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
if not _uc_gov_verified and _require_uc:
    raise RuntimeError(
        "CREATE SCHEMA probe did not succeed — stopping because adme.connector.require_uc_verified=true. "
        "Grant USE CATALOG + CREATE SCHEMA, set adme.connector.catalog, or use default "
        "require_uc_verified=false to attempt writes anyway."
    )
if not _uc_gov_verified:
    print(
        "WARN: UC CREATE SCHEMA probe did not verify — continuing (default require_uc_verified=false)."
    )
runtime.delta.schema_name = spark.conf.get("adme.connector.schema", runtime.delta.schema_name)

force_mock = spark.conf.get("adme.connector.governance.force_mock", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
append_mock = spark.conf.get(
    "adme.connector.governance.append_mock_when_live", "false"
).strip().lower() in ("1", "true", "yes")

print(
    "Governance sync — catalog:",
    runtime.delta.catalog,
    "schema:",
    runtime.delta.schema_name,
    "CREATE SCHEMA verified:",
    _uc_gov_verified,
)
print("force_mock:", force_mock, "append_mock_when_live:", append_mock)

auth = AuthProvider(runtime.auth)
counts = sync_governance_mirror(
    spark,
    runtime,
    auth,
    force_mock=force_mock,
    append_mock_when_live=append_mock,
)
print("Row counts written:", counts)

for label, fqn_fn in (
    ("legal_tags", runtime.delta.legal_tags_fqn),
    ("gov_entitlements", runtime.delta.entitlements_fqn),
    ("record_acl_mirror", runtime.delta.record_acl_mirror_fqn),
):
    fq = fqn_fn()
    print(f"--- {label}: {fq} ---")
    spark.read.table(fq).limit(20).show(truncate=60)
