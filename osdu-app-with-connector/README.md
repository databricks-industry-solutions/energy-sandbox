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
| `02_run_all_domains.py` | Extract all configured domains to Bronze/Silver |
| `03_governance_sync.py` | Sync legal tags, entitlements, ACL mirror |
| `04_onboarding_checklist.py` | Interactive guide to collect ADME connection details |

## Project Structure

```
adme-osdu-connector/
├── connector/              # Core Python package
│   ├── auth/               # Azure Entra ID auth (MI, SP, static token)
│   ├── clients/            # ADME HTTP client with retries
│   ├── domains/            # Record normalization and registry
│   ├── governance/         # Legal tags, entitlements, ACL sync
│   ├── models/             # Pydantic config models
│   ├── pipelines/          # Orchestration with DLQ + metrics
│   ├── storage/            # Delta writers (bronze, silver, DLQ, metrics)
│   └── utils/              # Logging, pagination, UC helpers
├── conf/
│   ├── connector_runtime.example.yaml   # Template config — copy and fill
│   └── domains/                         # Per-domain extraction configs
│       ├── wellbore.yaml
│       ├── reservoir.yaml
│       └── rock_and_fluid.yaml
├── notebooks/              # Databricks notebooks
├── resources/              # DAB job definitions
├── databricks.yml          # Databricks Asset Bundle config
└── requirements.txt        # Python dependencies
```

## Authentication

| Mode | Use Case | Config |
|------|----------|--------|
| `managed_identity` | Databricks cluster in the **same** Azure tenant as ADME | Set `managed_identity_client_id` (or null for system-assigned) |
| `service_principal` | **Cross-tenant** — Databricks in tenant A, ADME in tenant B | Set `service_principal_client_id` + `service_principal_client_secret` |
| `static_token` | Quick testing only | Paste a bearer token in `static_access_token` |

For cross-tenant setups, ask your ADME admin to:
1. Create a service principal in the ADME tenant
2. Grant it `users.datalake.viewers@<partition>.dataservices.energy`
3. Share the `client_id`, `client_secret`, and `tenant_id`

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

## Requirements

- Databricks workspace on Azure
- Azure Data Manager for Energy (ADME) instance
- Unity Catalog enabled
- Databricks CLI v0.200+

## License

Released under the **Databricks License**. See [LICENSE](LICENSE) for the full text. Use of this Software is limited to the scope of your Databricks Agreement (MCSA, Beta Services Terms, or Databricks License Agreement).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).
