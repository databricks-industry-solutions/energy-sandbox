# Databricks notebook source
# MAGIC %md
# MAGIC # ADME / OSDU connector — `00_smoke_test` (connector only)
# MAGIC
# MAGIC **Purpose** — Validate the reusable `connector/` package on a Databricks cluster with **Azure managed identity** (or static token), aligned with `notebooks/DLT_ADME_ManagedIdentity_Token_Smoke.py` patterns:
# MAGIC - Entra scope `api://<ADME_API_CLIENT_ID>/.default`
# MAGIC - Header `data-partition-id`
# MAGIC - **This notebook:** token → ADME API → one-page domain extract (**no Unity Catalog, no Delta**)
# MAGIC
# MAGIC **Deploy** — Import this file into your Databricks workspace (Repos or Workspace), ensure repo root contains `connector/` and `conf/`, attach a cluster with **managed identity** and outbound access to ADME.
# MAGIC
# MAGIC **Security** — Do not print full JWTs in shared dashboards; this notebook prints **decoded claim summaries** only for demos.
# MAGIC
# MAGIC **If you see import errors after a deploy:** **Restart Python kernel**, clear ``/tmp/adme_osdu_connector_materialized``, re-run from the top. This notebook imports ``AuthProvider`` from ``auth_provider`` (not ``providers``) so a stale synced ``providers.py`` on the cluster cannot break it.
# MAGIC
# MAGIC **Materialization** — Only ``connector/`` and ``conf/`` are copied to ``/tmp`` (not the whole repo), with short FUSE retries then Workspace Export API if needed. Run **%restart_python** after **%pip**, then run all.
# MAGIC
# MAGIC **“Failed to store the result” / 403 DBFS upload** — Defaults: **``adme.connector.notebook.minimal_output`` = ``true``** redirects most stdout/stderr to **``/tmp/adme_connector_notebook.log``**. The **config summary** and **screenshot summary** block still print to the **notebook UI** (via the saved stream). Set ``minimal_output`` = ``false`` for full verbose output everywhere.

# COMMAND ----------

# MAGIC %pip install -q 'httpx>=0.27' 'azure-identity>=1.15' 'pydantic>=2.5' 'PyYAML>=6' 'tenacity>=8'

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC **Pip + restart:** ``%restart_python`` stops the current **Run all** after the pip cell — **run all again** from the top (or from section 1). That matches the working ADME API smoke notebook and avoids half-updated wheels / import state.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1) Paths and configuration
# MAGIC Edit `REPO_ROOT` if your checkout path differs. Optionally set Spark conf `adme.connector.*` to override YAML.
# MAGIC
# MAGIC **Steps:** **1a** (path check), **1b** (materialize + import + load YAML), **1c** (compact **cfg** line). Run **1a → 1b → 1c** before section 2. **Delta / medallion** ingestion lives in other notebooks — not here.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1a) Define helpers + show detected repo (fast)

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
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _project_root_from_walk(start: Path) -> Optional[Path]:
    """
    Find directory to put on sys.path (must contain ``connector/`` and ``conf/``).

    Databricks Asset Bundles sync sources under ``<bundle_root>/files/``, while the
    open notebook often lives at ``<bundle_root>/notebooks/`` or ``.../files/notebooks/``.
    """
    try:
        b = start.resolve()
    except Exception:
        return None
    for p in [b, *b.parents]:
        if (p / "connector" / "__init__.py").is_file():
            return p
        # Bundle dev sync layout: .../adme_osdu_connector/files/connector/
        if p.name == "notebooks":
            continue
        if (p / "files" / "connector" / "__init__.py").is_file():
            return (p / "files").resolve()
    return None


def _detect_repo_root() -> Path:
    """
    On Databricks, ``Path.cwd()`` is usually ``/databricks/driver``, so we must not rely on it alone.
    Order: Spark conf ``adme.connector.repo_root`` → notebook path walk → cwd walk.

    Never return a bare ``.../notebooks`` directory: mis-set ``repo_root`` there used to make the
    code probe ``notebooks/files/connector`` (404 on Workspace).
    """
    conf_root = spark.conf.get("adme.connector.repo_root", "").strip()
    if conf_root:
        p = Path(conf_root).expanduser().resolve()
        found = _project_root_from_walk(p)
        if found is not None:
            return found
        # Invalid conf: fall through to notebook path / cwd (do not return ``p`` raw).

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
    """
    Fetch file bytes via ``/api/2.0/workspace/export`` (bypasses flaky ``/Workspace`` FUSE reads).
    """
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
    """Few FUSE attempts, then Export API, then short ``cat`` — avoid long per-file delays."""
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


def _materialize_connector_and_conf_only(src: Path, dst: Path, *, quiet: bool = False) -> tuple[int, int]:
    """
    Copy only ``connector/`` and ``conf/`` to ``dst`` (minimal set for this notebook).

    Returns ``(connector_file_count, conf_file_count)``.
    """
    if dst.is_dir():
        shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    counts: dict[str, int] = {"connector": 0, "conf": 0}
    for top in ("connector", "conf"):
        s_top = src / top
        if not s_top.is_dir():
            if top == "connector":
                raise OSError(f"missing {src}/{top} — sync bundle or set adme.connector.repo_root")
            continue
        if not quiet:
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
                blob = _read_workspace_file_fast(sp)
                dp.write_bytes(blob)
                n += 1
                if not quiet and n % 30 == 0:
                    print(f"   … {top}: {n} files")
        counts[top] = n
        if not quiet:
            print(f"   done {top}/: {n} files")
    return counts["connector"], counts["conf"]


def _materialize_workspace_tree(src: Path, *, quiet: bool = False) -> tuple[Path, bool]:
    """
    Copy ``connector/`` + ``conf/`` from ``/Workspace/...`` to ``/tmp`` for stable imports.

    Returns ``(repo_root, copied_to_tmp)``. If copy fails, returns ``(src, False)``.
    """
    src_s = str(src)
    if not src_s.startswith("/Workspace"):
        return src, False
    dst = Path(tempfile.gettempdir()) / "adme_osdu_connector_materialized"
    try:
        nc, nf = _materialize_connector_and_conf_only(src, dst, quiet=quiet)
    except OSError as e:
        print(f"WARN: materialize failed ({e}); using Workspace (risky): {src}")
        return src, False
    if quiet:
        print(f"Materialized to /tmp (connector_files={nc}, conf_files={nf}).")
    else:
        print(f"Materialized (connector+conf only): {src} -> {dst}")
    return dst, True


_workspace_src = _detect_repo_root()
_1a_min = spark.conf.get("adme.connector.notebook.minimal_output", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)
if _1a_min:
    print(
        "1a",
        _workspace_src,
        "connector=",
        (_workspace_src / "connector" / "__init__.py").is_file(),
    )
else:
    print("Step 1a — repo root:", _workspace_src)
    print(
        "Step 1a — connector present:",
        (_workspace_src / "connector" / "__init__.py").is_file(),
    )


def _adme_notebook_maybe_redirect_stdio(*, minimal: bool) -> None:
    """
    When ``minimal_output`` is on, send this kernel's stdout/stderr to a driver log file once.

    Databricks persists notebook cell results to workspace storage; large stdout or Spark UI
    payloads can trigger **AuthorizationFailure** on upload. Reading logs: cluster **SSH** or
    ``%sh head -200 /tmp/adme_connector_notebook.log`` (if your policy allows).
    """
    if not minimal:
        return
    if globals().get("_ADME_NB_STDIO_REDIRECTED"):
        return
    log_path = "/tmp/adme_connector_notebook.log"
    f = open(log_path, "w", encoding="ascii", errors="backslashreplace")
    globals()["_ADME_NB_STDIO_ORIG_OUT"] = sys.stdout
    globals()["_ADME_NB_STDIO_ORIG_ERR"] = sys.stderr
    globals()["_ADME_NB_STDIO_LOG_FP"] = f
    sys.stdout = f
    sys.stderr = f
    globals()["_ADME_NB_STDIO_REDIRECTED"] = True


def _adme_notebook_ui_print(*args, **kwargs) -> None:
    """
    Print to the real notebook stream while ``minimal_output`` has redirected ``sys.stdout``.

    Config summary and the screenshot summary block use this so they still appear in the cell UI; other cells
    mostly write to ``/tmp/adme_connector_notebook.log`` until you set
    ``adme.connector.notebook.minimal_output=false``.
    """
    kwargs.setdefault("flush", True)
    orig = globals().get("_ADME_NB_STDIO_ORIG_OUT")
    if orig is not None:
        print(*args, file=orig, **kwargs)
    else:
        print(*args, **kwargs)


# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1b) Materialize ``connector`` + ``conf`` to ``/tmp``, then import package

# COMMAND ----------

if "_materialize_workspace_tree" not in globals():
    raise RuntimeError("Run Step 1a (cell above) first — it defines helpers and _workspace_src.")
if "_workspace_src" not in globals():
    _workspace_src = _detect_repo_root()

_NB_MIN = spark.conf.get("adme.connector.notebook.minimal_output", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)
_adme_notebook_maybe_redirect_stdio(minimal=_NB_MIN)
REPO_ROOT, _copied = _materialize_workspace_tree(_workspace_src, quiet=_NB_MIN)

# Drop Workspace copy from sys.path so we never import a half-broken ``connector`` from FUSE.
if _copied:
    ws = str(_workspace_src)
    sys.path[:] = [p for p in sys.path if p != ws and not str(p).startswith(ws + os.sep)]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Drop stale imports if this cell was run earlier with a wrong REPO_ROOT (common in notebooks).
for _k in list(sys.modules):
    if _k == "connector" or _k.startswith("connector."):
        del sys.modules[_k]

if not (REPO_ROOT / "connector" / "__init__.py").is_file():
    raise ModuleNotFoundError(
        "Cannot import `connector`: project root not found.\n"
        f"  Detected REPO_ROOT: {REPO_ROOT}\n"
        "  If you use ``databricks bundle sync``, code lives under ``.../adme_osdu_connector/files/``.\n"
        "  Set Spark conf, e.g.:\n"
        "    adme.connector.repo_root = /Workspace/Users/<you>/adme_osdu_connector/files"
    )

_ap_path = REPO_ROOT / "connector" / "auth" / "auth_provider.py"
try:
    _ap_text = _ap_path.read_text(encoding="utf-8", errors="replace")
except OSError as e:
    raise ModuleNotFoundError(
        f"Cannot read connector sources at {_ap_path}: {e}\n"
        "  Re-run ``databricks bundle sync``; on cluster, ``rm -rf /tmp/adme_osdu_connector_materialized``."
    ) from e
if "class AuthProvider" not in _ap_text:
    raise ImportError(
        f"{_ap_path} does not define AuthProvider (len={len(_ap_text)}). "
        "Workspace copy is truncated or stale — re-sync the bundle and clear /tmp materialization."
    )

# Stale bytecode under /tmp can resurrect old half-imported modules.
sys.dont_write_bytecode = True
for _pc in list(REPO_ROOT.rglob("__pycache__")):
    if _pc.is_dir():
        shutil.rmtree(_pc, ignore_errors=True)
importlib.invalidate_caches()

_runtime_yaml = REPO_ROOT / "conf" / "connector_runtime.yaml"
RUNTIME_YAML = _runtime_yaml if _runtime_yaml.is_file() else REPO_ROOT / "conf" / "connector_runtime.example.yaml"
DOMAINS_DIR = REPO_ROOT / "conf" / "domains"

# AuthProvider from auth_provider (same as ADMEApiClient) — avoids stale workspace copies of
# providers.py that omit the re-export. Claims helper lives in token_utils (stdlib only).
from connector.auth.auth_provider import AuthProvider
from connector.auth.token_utils import safe_token_claims_summary
from connector.clients.adme_api import ADMEApiClient
from connector.config_loader import load_runtime_config
from connector.domains.registry import load_domain_config
from connector.utils.logging import setup_logging

setup_logging()

# Load YAML then apply Spark conf overrides (same keys as DLT smoke notebook style)
_runtime = load_runtime_config(RUNTIME_YAML)
_runtime.base_url = spark.conf.get("adme.connector.base_url", _runtime.base_url)
_runtime.data_partition_id = spark.conf.get(
    "adme.connector.data_partition_id", _runtime.data_partition_id
)
_runtime.auth.tenant_id = spark.conf.get("adme.connector.tenant_id", _runtime.auth.tenant_id)
_runtime.auth.adme_api_client_id = spark.conf.get(
    "adme.connector.adme_api_client_id", _runtime.auth.adme_api_client_id
)
mi = spark.conf.get("adme.connector.managed_identity_client_id", "").strip()
if mi:
    _runtime.auth.managed_identity_client_id = mi

# --- User-editable notebook variables (defaults after Spark conf) ---
DOMAIN_TO_TEST = spark.conf.get("adme.connector.domain", "wellbore")
LOAD_TYPE_STR = spark.conf.get("adme.connector.load_type", "full")  # full | incremental for smoke

# ``minimal_output`` (default true): tiny stdout, no Spark .show() HTML — best effort vs DBFS 403.
# ``compact_output``: used only when minimal_output is false.
_CMP = (not _NB_MIN) and spark.conf.get("adme.connector.notebook.compact_output", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1c) Config summary
# MAGIC Compact **cfg** line for the notebook UI (no Unity Catalog / Delta in this notebook).

# COMMAND ----------

if "_runtime" not in globals():
    raise RuntimeError("Run Step 1b first (defines _runtime).")

_1c_min = spark.conf.get("adme.connector.notebook.minimal_output", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)

if _1c_min:
    _adme_notebook_ui_print(
        "cfg:",
        f"repo={REPO_ROOT}",
        f"partition={_runtime.data_partition_id}",
        f"domain={DOMAIN_TO_TEST}",
        sep=" | ",
    )
    _adme_notebook_ui_print(
        "[hint] With minimal_output=true, auth/API prints go to /tmp/adme_connector_notebook.log — "
        "run: tail -80 /tmp/adme_connector_notebook.log in a Shell cell if you need them in the UI.",
    )
else:
    _adme_notebook_ui_print("REPO_ROOT:", REPO_ROOT)
    _adme_notebook_ui_print("RUNTIME_YAML:", RUNTIME_YAML)
    _adme_notebook_ui_print("base_url:", _runtime.base_url)
    _adme_notebook_ui_print("data_partition_id:", _runtime.data_partition_id)
    _adme_notebook_ui_print("adme_api_client_id:", _runtime.auth.adme_api_client_id)
    _adme_notebook_ui_print("domain:", DOMAIN_TO_TEST, "load:", LOAD_TYPE_STR)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2) Authentication smoke test
# MAGIC Initialize `AuthProvider`, acquire token, print safe claims (`aud`, `tid`, `oid`, `appid`, `roles`).

# COMMAND ----------

results = {
    "auth": False,
    "api": False,
    "extract": False,
}

try:
    auth = AuthProvider(_runtime.auth)
    token = auth.get_bearer_token()
    claims = safe_token_claims_summary(token)
    if _NB_MIN:
        print("AUTH OK", "aud=", claims.get("aud"), "appid=", claims.get("appid"))
    elif _CMP:
        print("Token claims (one line):", json.dumps(claims, default=str)[:400])
    else:
        print("Token claims (summary):", json.dumps(claims, indent=2, default=str))
    if not claims.get("aud"):
        raise RuntimeError("Token missing aud claim — check ADME API app id / scope.")
    results["auth"] = True
    if not _NB_MIN:
        print("AUTH: PASS")
except Exception as e:
    print("AUTH: FAIL —", e)
    if not _NB_MIN:
        traceback.print_exc()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3) API connectivity smoke test
# MAGIC Instantiate `ADMEApiClient`, call lightweight GETs (partition list + legal tags pattern from DLT smoke).
# MAGIC
# MAGIC **HTTP 500** on partition with body *"An unknown error has occurred"* is an **ADME service-side** fault (not bad Databricks auth). Capture **`traceparent`** from the response headers for the platform team. Your token can be valid while partition microservice is failing. Search/extract steps may still work.

# COMMAND ----------

if not results["auth"]:
    print("Skipping API test — auth failed.")
else:
    try:
        auth = AuthProvider(_runtime.auth)
        with ADMEApiClient(_runtime, auth) as client:
            checks = [
                ("/api/partition/v1/partitions", True),
                ("/api/legal/v1/legaltags?valid=true", False),
            ]
            partition_ok = False
            _part_http = None  # type: Optional[int]
            _legal_http = None  # type: Optional[int]
            _part_tp = ""
            for path, required in checks:
                r = client.smoke_get(path, timeout=45)
                tp = r.headers.get("traceparent") or r.headers.get("x-ms-request-id", "")
                if "partition" in path:
                    _part_http = r.status_code
                    _part_tp = tp or ""
                else:
                    _legal_http = r.status_code
                if not _NB_MIN:
                    prev_n = 180 if _CMP else 500
                    body_preview = (r.text or "")[:prev_n]
                    if len(r.text or "") > prev_n:
                        body_preview = body_preview + "…"
                    if _CMP:
                        print(
                            f"--- {path} | HTTP {r.status_code} | partition={_runtime.data_partition_id}"
                            + (f" | traceparent={tp}" if tp else "")
                        )
                        print("  preview:", body_preview.replace("\n", " ")[:200])
                    else:
                        print("---")
                        print("PATH:", path)
                        print("HTTP:", r.status_code)
                        print("sent data-partition-id:", _runtime.data_partition_id)
                        print("response preview:", body_preview)
                        print("response headers (subset):", dict(list(r.headers.items())[:8]))
                        if tp:
                            print("correlation (traceparent or request id):", tp)
                if r.status_code == 200:
                    if "partition" in path:
                        partition_ok = True
                elif required:
                    if r.status_code >= 500 and not _NB_MIN:
                        print(
                            "Partition returned 5xx — treat as ADME platform incident; "
                            "share traceparent + partition id with ADME ops."
                        )
                    elif r.status_code < 500:
                        r.raise_for_status()
                elif not _NB_MIN:
                    print("WARN (non-fatal):", path, "returned", r.status_code)
            if _NB_MIN:
                print(
                    "API",
                    f"partition_http={_part_http}",
                    f"legal_http={_legal_http}",
                    f"partition_ok={partition_ok}",
                    f"tp={(_part_tp[:72] + '...') if len(_part_tp) > 72 else _part_tp}",
                )
            elif not partition_ok:
                print(
                    "WARN: Partition GET did not return 200 — continuing notebook; "
                    "try Search/extract below (often independent of partition list)."
                )
        results["api"] = True
        if not _NB_MIN:
            print("API: PASS (partition list may have warnings — see above)")
    except Exception as e:
        print("API: FAIL —", e)
        if not _NB_MIN:
            traceback.print_exc()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4) Domain extraction test
# MAGIC Load domain YAML, fetch at least one page via Search API, print counts and sample payload.

# COMMAND ----------

domain_cfg = load_domain_config(DOMAINS_DIR / f"{DOMAIN_TO_TEST}.yaml")
sample_records = []

if not results["api"]:
    print("Skipping extraction — API smoke failed.")
else:
    try:
        auth = AuthProvider(_runtime.auth)
        with ADMEApiClient(_runtime, auth) as client:
            pages = 0
            for page in client.iter_domain_pages(
                domain_cfg,
                watermark=None,
                load_full=True,
            ):
                sample_records.extend(page.records)
                pages += 1
                break
        if _NB_MIN:
            print("EXTRACT pages=", pages, "records=", len(sample_records))
        else:
            print("Pages fetched (capped at 1 for smoke):", pages)
            print("Records in first page:", len(sample_records))
            if sample_records:
                lim = 400 if _CMP else 2000
                print("Sample record keys:", list(sample_records[0].keys())[:12])
                print("Sample record (truncated):", json.dumps(sample_records[0], default=str)[:lim])
        results["extract"] = True
        if not _NB_MIN:
            print("EXTRACT: PASS")
    except Exception as e:
        print("EXTRACT: FAIL —", e)
        if not _NB_MIN:
            traceback.print_exc()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5) Final validation summary
# MAGIC At the end of this cell, a bordered **screenshot summary** block is printed on the notebook stream (works even when ``minimal_output=true`` redirects other stdout).

# COMMAND ----------

lines = [
    ("auth", results["auth"]),
    ("api_reachability", results["api"]),
    ("extraction", results["extract"]),
]
overall = all(v for _, v in lines)
if _NB_MIN:
    print(
        "SUMMARY",
        " ".join(f"{n}={'OK' if v else 'NO'}" for n, v in lines),
        "overall=" + ("OK" if overall else "NO"),
    )
else:
    print("\n=== SUMMARY ===")
    for name, ok in lines:
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    print("\nOVERALL:", "PASS" if overall else "FAIL (see cells above)")

# Screenshot summary: always on the real notebook stream (works with minimal_output=true).
_TS_SHARE = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
_LABELS = {
    "auth": "Authentication (token)",
    "api_reachability": "ADME API reachability",
    "extraction": "Domain extract (Search)",
}
_SEP72 = "=" * 72
_SUB72 = "-" * 72
_adme_notebook_ui_print("")
_adme_notebook_ui_print(_SEP72)
_adme_notebook_ui_print("  ADME / OSDU connector — smoke result (screenshot summary)")
_adme_notebook_ui_print(_SEP72)
_adme_notebook_ui_print(f"  When:      {_TS_SHARE}")
_adme_notebook_ui_print(f"  Mode:      connector (auth + API + extract)")
_adme_notebook_ui_print(f"  ADME URL:  {_runtime.base_url}")
_adme_notebook_ui_print(f"  Partition: {_runtime.data_partition_id}")
_adme_notebook_ui_print(f"  Domain:    {DOMAIN_TO_TEST}")
_adme_notebook_ui_print(_SUB72)
for _n, _ok in lines:
    _lab = _LABELS.get(_n, _n)
    _mark = "PASS" if _ok else "FAIL"
    _adme_notebook_ui_print(f"  {_mark:4}  {_lab}")
_adme_notebook_ui_print(_SUB72)
_adme_notebook_ui_print(f"  OVERALL: {'PASS' if overall else 'FAIL'}")
_adme_notebook_ui_print(_SEP72)
