# ADME OSDU → Databricks Connector

Reference connector that extracts subsurface data from **Azure Data Manager for Energy (ADME)** into **Databricks Unity Catalog**, with governance metadata sync.

## Disclaimer

This is a **solution accelerator**, not a production-ready connector. It is provided as reference code to demonstrate patterns for ingesting OSDU data from ADME into Databricks. It has not been hardened, security-audited, or tested for production workloads. Review, adapt, and validate the code in your own environment before any operational use. Databricks makes no warranty regarding fitness for any particular purpose. See [LICENSE](LICENSE) and the repository-level [DISCLAIMER.md](../DISCLAIMER.md).

## What It Does

- **Domain Ingestion** — Paginated extraction of OSDU records (Wellbore, Reservoir, Rock & Fluid) via the ADME Search API
- **Bronze / Silver / Checkpoint** — Raw JSON → normalized Delta tables with MERGE dedup and incremental watermarks
- **Governance Sync** — Mirrors legal tags, entitlements groups, and ACL metadata from ADME into UC tables
- **Dead Letter Queue** — Failed records captured for retry, never silently dropped
- **Run Metrics** — Per-domain stats (rows extracted/bronze/silver/failed, duration) written to a metrics table
- **Schema Evolution** — New fields in ADME records automatically added to Silver tables
- **Daily Scheduling** — Cron-based job with email alerts on failure
- **Lakeflow Connect interface** (v1.2.0): `connector/lakeflow/adme_osdu.py` exposes the ingestion path via the Lakeflow Connect contract for UC Connection-driven ingestion (`connector_spec.yaml`)
- **Spark Declarative Pipelines** (v1.2.0): bronze/silver/gold flows at `src/adme_sdp/` orchestrated by `resources/adme_sdp_pipeline.yml`
- **Offline test harness** (v1.2.0): in-process HTTP simulator (`connector/simulator/`) + stubbed `azure.identity`/`respx`/`tenacity` (`tests/stubs/`) so the unit suite runs without network
- **Federated identity auth** (v1.2.0): OIDC / Workload Identity Federation via `ClientAssertionCredential`, plus CI script `ci/federated_auth_example.sh`

## Quick Start

### 1. Configure

```bash
cp conf/connector_runtime.example.yaml conf/connector_runtime.yaml
```

Edit `conf/connector_runtime.yaml` with your:
- ADME instance URL
- Azure tenant ID and auth mode (managed identity / service principal)
- Unity Catalog catalog and schema name

### 2. Deploy with Databricks Asset Bundles

```bash
# Install Databricks CLI if not already installed
# https://docs.databricks.com/dev-tools/cli/install.html

# Authenticate
databricks auth login --host https://YOUR-WORKSPACE.azuredatabricks.net

# Validate and deploy
databricks bundle validate -t dev \
  --var workspace_host=https://YOUR-WORKSPACE.azuredatabricks.net \
  --var alert_email=you@example.com

databricks bundle deploy -t dev \
  --var workspace_host=https://YOUR-WORKSPACE.azuredatabricks.net \
  --var alert_email=you@example.com
```

### 3. Run

```bash
# Trigger the pipeline manually
databricks bundle run adme_connector_pipeline -t dev

# Or run from the Databricks Jobs UI — it's also scheduled daily at 06:00 UTC
```

### 4. Manual Notebook Execution

You can also run notebooks individually on any cluster:

| Notebook | Purpose |
|----------|---------|
| `00_smoke_test.py` | Validate ADME auth and connectivity |
| `01_uc_write_test.py` | Probe whether your cluster identity can create UC schemas and write Delta tables (no ADME creds needed) |
| `02_run_all_domains.py` | Extract all configured domains to Bronze/Silver |
| `03_governance_sync.py` | Sync legal tags, entitlements, ACL mirror |
| `04_onboarding_checklist.py` | Interactive guide to collect ADME connection details |
| `ADME_API_SmokeTest_Databricks.py` | ADME REST smoke test using a pre-issued bearer token from Databricks Secrets |
| `Auth_with_Entra_Token_ADME_API_SmokeTest_Databricks.py` | Same as above, with the bearer minted live via Entra (notebook walks both flows) |
| `DLT_ADME_ManagedIdentity_Token_Smoke.py` | Spark Declarative Pipelines variant — mirrors the smoke checks as separate streaming tables, auth via cluster Managed Identity |
| `ADME_API_SmokeTest.ipynb` | Jupyter version of the smoke test for non-Databricks environments |

## Project Structure

```
adme-osdu-connector/
├── connector/              # Core Python package
│   ├── auth/               # Azure Entra ID auth (MI, SP, static token, federated)
│   ├── clients/            # ADME HTTP client with retries
│   ├── domains/            # Record normalization and registry
│   ├── governance/         # Legal tags, entitlements, ACL sync
│   ├── lakeflow/           # Lakeflow Connect interface + adme_osdu adapter (v1.2.0)
│   ├── models/             # Pydantic config models
│   ├── pipelines/          # Orchestration with DLQ + metrics
│   ├── schema/             # Schema discovery + validation helpers (v1.2.0)
│   ├── simulator/          # In-process HTTP simulator + OSDU corpus for offline tests (v1.2.0)
│   ├── storage/            # Delta writers (bronze, silver, DLQ, metrics)
│   └── utils/              # Logging, pagination, UC helpers
├── conf/
│   ├── connector_runtime.example.yaml          # Template config — copy and fill
│   ├── connector_runtime_ci_federated.yaml     # CI example using federated identity (v1.2.0)
│   └── domains/                                # Per-domain extraction configs
│       ├── wellbore.yaml
│       ├── reservoir.yaml
│       └── rock_and_fluid.yaml
├── ci/
│   └── federated_auth_example.sh   # Reference script to obtain a federated token in CI (v1.2.0)
├── notebooks/              # Databricks notebooks (incl. v1.2.0 ADME REST + DLT smoke tests)
├── resources/
│   ├── adme_connector_job.yml      # DAB job definition (extractor pipeline)
│   └── adme_sdp_pipeline.yml       # Spark Declarative Pipelines spec (v1.2.0)
├── schemas/                # OSDU schema fixtures (v1.2.0)
├── src/
│   └── adme_sdp/           # SDP transformations: bronze_ingestion, silver_normalization, gold_views, governance_sync (v1.2.0)
├── tests/
│   ├── stubs/              # Stub packages (azure.identity, respx, tenacity) for offline unit tests (v1.2.0)
│   └── unit/               # Lakeflow Connect unit suite + adme_osdu coverage (v1.2.0)
├── .github/workflows/      # CI matrix (pytest 3.9–3.12) (v1.2.0)
├── .claude/                # Connector-dev agents, commands, skills (v1.2.0)
├── connector_spec.yaml     # UC Connection parameters for Lakeflow Connect (v1.2.0)
├── conftest.py             # Pytest config wiring tests/stubs onto sys.path (v1.2.0)
├── pyproject.toml          # Build + dependency manifest (v1.2.0)
├── uv.lock                 # Lockfile for reproducible env (v1.2.0)
├── requirements.txt        # Runtime Python dependencies
├── requirements-dev.txt    # Dev/test extras (v1.2.0)
├── CLAUDE.md               # Project context for Claude-assisted contributors (v1.2.0)
└── databricks.yml          # Databricks Asset Bundle config
```

## Authentication

| Mode | Use Case | Config |
|------|----------|--------|
| `managed_identity` | Databricks cluster in the **same** Azure tenant as ADME | Set `managed_identity_client_id` (or null for system-assigned) |
| `service_principal` | **Cross-tenant** — Databricks in tenant A, ADME in tenant B | Set `service_principal_client_id` + `service_principal_client_secret` |
| `federated_identity` (v1.2.0) | Workload Identity / OIDC federation — CI runners, GKE/EKS workloads, or any compute that exchanges an OIDC assertion for an Entra token | Set `service_principal_client_id` + `tenant_id`, and supply the OIDC assertion via either `federated_token` (inline) or `federated_token_file` (path) |
| `static_token` | Quick testing only | Paste a bearer token in `static_access_token` |

For cross-tenant setups, ask your ADME admin to:
1. Create a service principal in the ADME tenant
2. Grant it `users.datalake.viewers@<partition>.dataservices.energy`
3. Share the `client_id`, `client_secret`, and `tenant_id`

For federated identity, see `conf/connector_runtime_ci_federated.yaml` and `ci/federated_auth_example.sh` for a reference CI flow that pulls an OIDC assertion from the runner and exchanges it for an ADME token via `azure.identity.ClientAssertionCredential`.

## Adding a New Domain

1. Create `conf/domains/your_domain.yaml`:

```yaml
name: your_domain
description: "Your OSDU domain"
primary_key: id
incremental_field: data.modifyTime
phase: 1

extraction:
  method: POST
  path: /api/search/v2/query
  base_query:
    kind: "osdu:wks:master-data--YourKind:*"
    query: ""
  incremental_filter_template: 'data.modifyTime:>="{watermark}"'

pagination:
  style: cursor_body
  records_path: results
  cursor_path: cursor
  cursor_request_field: cursor
  page_size: 50

normalization:
  record_id_path: id
  record_kind_path: kind
  modify_time_path: data.modifyTime
  field_map:
    field_name: data.FieldName
    another_field: data.AnotherField
```

2. Redeploy: `databricks bundle deploy -t dev`

## Tables Created

| Table | Description |
|-------|-------------|
| `bronze_<domain>` | Raw JSON from ADME API |
| `silver_<domain>` | Normalized, deduplicated records |
| `checkpoint_<domain>` | Incremental watermarks |
| `gov_legal_tags` | ADME legal tag definitions |
| `gov_entitlements` | ADME entitlement groups |
| `gov_record_acl_mirror` | Record-level ACL assignments |
| `adme_osdu_dlq` | Dead Letter Queue for failed records |
| `adme_osdu_run_metrics` | Per-domain run statistics |

## Lakeflow Connect Integration (v1.2.0)

`connector/lakeflow/adme_osdu.py` exposes the ingestion path through the Lakeflow Connect contract (`list_tables` / `get_table_schema` / `read_table_metadata` / `read_table`). It can be wired into a Unity Catalog Connection so an end user configures ADME ingestion via the standard UC Connection UI rather than running the DAB.

`connector_spec.yaml` declares the UC Connection parameters: `base_url`, `data_partition_id`, `auth_mode` (one of `managed_identity` / `service_principal` / `federated_identity` / `static_token`), plus the auth-mode-specific fields (`adme_api_client_id`, `service_principal_client_id`/`_secret`, `managed_identity_client_id`, `federated_token`/`_file`, `access_token`). Two table-level options are passed through via `externalOptionsAllowList`: `page_size` and `load_type` (`full` or `incremental`).

This integration is being upstreamed to [`databrickslabs/lakeflow-community-connectors`](https://github.com/databrickslabs/lakeflow-community-connectors/pull/170) where it is packaged for installation as a Spark Python Data Source with `SupportsPartitionedStream`.

## Spark Declarative Pipelines (v1.2.0)

`src/adme_sdp/` contains the bronze→silver→gold flows expressed as SDP transformations:

| File | Purpose |
|------|---------|
| `bronze_ingestion.py` | Pull raw OSDU records page-by-page into `bronze_<domain>` |
| `silver_normalization.py` | Normalize, deduplicate (MERGE on `id`), apply schema evolution |
| `gold_views.py` | Curated views suitable for direct analyst / BI consumption |
| `governance_sync.py` | Mirror legal tags, entitlements groups, and per-record ACL into `gov_*` tables |

The pipeline is declared in `resources/adme_sdp_pipeline.yml` and deploys via the same DAB. SDP gives serverless compute, automatic backfills, and incremental processing without hand-rolled checkpoint code.

## Testing

`tests/` is split into two layers:

1. **Top-level unit tests** (`tests/test_*.py`) exercise individual modules — auth, normalization, token utilities, UC catalog helpers — using lightweight fakes.
2. **Lakeflow Connect unit suite** (`tests/unit/adme_osdu/`) drives the full connector against the in-process HTTP simulator (`connector/simulator/`), which replays a corpus seeded from the OSDU master-data schemas at `connector/simulator/corpus/*.json`. The simulator intercepts the connector's `requests.Session.send` calls so the suite runs without any network traffic.

Optional dependencies (`azure.identity`, `respx`, `tenacity`) are provided as stub packages under `tests/stubs/` — `conftest.py` adds them to `sys.path` so the unit tests pass on a vanilla Python 3.9+ environment without the real Azure SDK installed.

Run the suite locally:

```bash
pip install -e ".[dev]"   # uses pyproject.toml + requirements-dev.txt
pytest tests/             # ~6s, no network
```

CI runs the same suite across Python 3.9 / 3.10 / 3.11 / 3.12 via `.github/workflows/ci.yml`. The workflow file lives nested inside `osdu-app-with-connector/` — GitHub Actions discovers workflows only at the repository root, so to enable CI in this monorepo either hoist this workflow file to the repo root or copy its pytest steps into an existing root-level workflow.

## Claude-assisted Development (v1.2.0)

`.claude/` ships connector-development tooling for Claude Code users contributing to this connector or building new ones in the same shape:

- **Agents** (`.claude/agents/`): `connector-dev`, `connector-tester`, `connector-auth-validator` — sub-agents tuned for connector authoring, test execution, and auth verification.
- **Commands** (`.claude/commands/`): `/develop-connector` and `/validate-connector` slash commands.
- **Skills** (`.claude/skills/`): `authenticate-source`, `test-and-fix-connector`, `validate-connector-auth`, `validate-incremental-sync`, `self-review-connector`.

See `CLAUDE.md` for the project-level context Claude uses when assisting.

## Requirements

- Databricks workspace on Azure
- Azure Data Manager for Energy (ADME) instance
- Unity Catalog enabled
- Databricks CLI v0.200+
- Python 3.9+ for local tooling; the unit suite runs on 3.9–3.12 in CI (v1.2.0)
- `azure-identity>=1.15.0` only when using `managed_identity` or `federated_identity` auth modes

## License

Released under the **Databricks License**. See [LICENSE](LICENSE) for the full text. Use of this Software is limited to the scope of your Databricks Agreement (MCSA, Beta Services Terms, or Databricks License Agreement).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).
