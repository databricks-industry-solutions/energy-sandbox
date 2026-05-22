[![Databricks](https://img.shields.io/badge/Databricks-Solution_Accelerator-FF3621?style=for-the-badge&logo=databricks)](https://databricks.com)
[![Unity Catalog](https://img.shields.io/badge/Unity_Catalog-Enabled-00A1C9?style=for-the-badge)](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
[![Genie](https://img.shields.io/badge/AI%2FBI-Genie-FF6A4A?style=for-the-badge)](https://docs.databricks.com/aws/en/genie/)
[![Mosaic AI](https://img.shields.io/badge/Mosaic_AI-Foundation_Models-7C3AED?style=for-the-badge)](https://docs.databricks.com/en/machine-learning/foundation-models/index.html)

# Production Optimizer

A real-time well production optimization platform built as a [Databricks App](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html). The app combines an interactive 3D digital twin, Arps decline-curve analytics, governed natural-language access via [AI/BI Genie](https://docs.databricks.com/aws/en/genie/), and a multi-agent **Recommendation Approval Supervisor** that fans out across five Databricks AI primitives to synthesise a deployment verdict.

Production optimizer demonstrates the operator workflow: see the field state in 3D, query the underlying gold tables in plain English, and run any optimization recommendation through a five-specialist approval supervisor before committing capex.

## Overview

Mature fields lose 5–15% of production every year to natural decline. Engineers chase the curves with workover, choke, and injection-pattern changes — but those decisions touch reservoir physics, well economics, operations crews, and prior precedent. Tying them together usually means stitching five tools and three spreadsheets per decision.

Production Optimizer collapses that workflow into one Databricks App:

- **Field Overview** — Geospatial map of all wells and patterns with current rates and status.
- **3D Digital Twin** — Interactive well-trajectory and pattern visualization with live production overlays.
- **Production Optimizer Workbench** — Per-well Arps decline-curve fits (qi, di, b-factor) with EUR, remaining reserves, and the platform-generated recommendations table.
- **✨ Ask Genie** — Natural-language access to the governed Unity Catalog gold tables. Genie writes the SQL, executes against the warehouse, and returns answers as text + inline tables.
- **🧠 Supervisor** — Five-specialist Recommendation Approval Supervisor (see below). Streams per-specialist results in parallel via SSE and synthesises a single verdict: **APPROVE · APPROVE-WITH-MODS · DEFER · REJECT**.
- **Data & AI Flow** — Architecture diagram showing the medallion pipeline, AI surfaces, and governance.

## Recommendation Approval Supervisor

Question: *"Should we adopt recommendation REC-{id} on well WELL-{id}?"*

| # | Specialist | Databricks primitive | What it does |
|---|---|---|---|
| 1 | **Decline Curve Analyst** | Foundation Model API (Claude) | Reads the Arps fit for the target well from `gold_decline_curves` and gives a 3-line risk assessment. |
| 2 | **Economic Impact Evaluator** | UC SQL | Combines the recommendation row with `gold_field_economics` for revenue, opex, breakeven, and incremental netback. |
| 3 | **Recommendation History** | UC SQL | Past recommendations affecting the same well or pattern, ordered by annual revenue impact. |
| 4 | **Analog Field Reference** | Vector Search (curated stub) | SPE / industry references via semantic search over `petroleum_documents`. |
| 5 | **Operations Feasibility** | UC SQL | Current well status + rates + neighbor-pattern context from `bronze_wells`. |

Each specialist hits a different first-class Databricks primitive — UC governed SQL, the Foundation Model API, Vector Search — and all decisions are logged for audit. The synthesis prompt produces the verdict + 3 supporting facts + 1 top risk.

## Architecture

| Layer | Component | Notes |
|---|---|---|
| Storage | **Delta tables in Unity Catalog** | `bronze_wells`, `bronze_patterns`, `silver_production_history`, `silver_economics`, `gold_decline_curves`, `gold_field_economics`, `gold_recommendations`, `petroleum_documents`. |
| Compute | **Databricks SQL Warehouse** | App-time queries via `/api/2.0/sql/statements`. |
| AI | **Foundation Model API** (Claude) | Decline analyst + final synthesis. |
| AI | **AI/BI Genie Space** | Natural-language SQL over the gold tables. |
| App backend | **Express + TypeScript (Node)** | Single process — no Python sidecar. Genie + Supervisor implemented directly via Databricks REST API. |
| App frontend | **React + TypeScript + Vite** | Field Overview · Digital Twin · Production Optimizer · ✨ Ask Genie · 🧠 Supervisor · Data & AI Flow. |
| Governance | **Unity Catalog** | One permission model across data, AI, and audit. |

The Node-native AI implementation (`src/routes/genie.ts` + `src/routes/supervisor.ts`) uses the OAuth client-credentials flow against the Apps-injected service-principal credentials. No `databricks-sdk` Python dependency, no FastAPI sidecar, no pip-install at startup.

## MFG Rules of the Road tags

Per `go/mfg/demo/rules`, the governed Unity Catalog tags for this demo are:

- `mfg_subindustry` = **Oil & Gas Upstream**
- `mfg_outcome_usecase` = **Production Monitoring**

These are applied to `energy_utilities.production_optimizer` by the bootstrap step in the prod target.

## Getting Started

### Prerequisites

- A Databricks workspace with [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) enabled
- A SQL Warehouse (Serverless recommended)
- An [AI/BI Genie Space](https://docs.databricks.com/aws/en/genie/) scoped to the production_optimizer gold tables
- Foundation Model API access (Claude Sonnet 4.5 or compatible)
- Node.js 18+ for the frontend build
- Databricks CLI installed and configured

### AI configuration (env vars)

The Genie sidebar and Supervisor are driven by these env vars in `app.yaml`:

| Env | Purpose | Default |
|---|---|---|
| `GENIE_SPACE_ID` | Genie Space scoped to the demo's gold tables. Required. | (none) |
| `AGENT_MODEL` | Foundation Model API endpoint for the supervisor synthesis. | `databricks-claude-sonnet-4-5` |
| `DEMO_CATALOG` | Unity Catalog target. | `energy_utilities` (prod) |
| `DEMO_SCHEMA` | Schema under the catalog. | `production_optimizer` |
| `DATABRICKS_WAREHOUSE_ID` | SQL warehouse for UC queries + Genie. | (required) |

### Deploy with Databricks Asset Bundles

```bash
cd production-optimizer
# Build the frontend + Express
npx tsc -p tsconfig.json
cd ui && npm install && npx vite build && cd ..

# Validate + deploy
databricks bundle validate -t prod
databricks bundle deploy -t prod
```

### Deploy manually

1. Update `app.yaml` with your `DATABRICKS_WAREHOUSE_ID` and `GENIE_SPACE_ID`.
2. Build:
   ```bash
   npx tsc -p tsconfig.json
   cd ui && npm install && npx vite build && cd ..
   ```
3. Upload + deploy:
   ```bash
   databricks workspace import-dir . /Workspace/Users/<your-email>/production-optimizer --overwrite
   databricks apps create production-optimizer --description "Production Optimizer"
   databricks apps deploy production-optimizer --source-code-path /Workspace/Users/<your-email>/production-optimizer
   ```

### Required Permissions

Grant the app's service principal access to your catalog, schema, warehouse, and Genie Space:

```sql
GRANT USE CATALOG ON CATALOG energy_utilities TO `<app-sp-client-id>`;
GRANT USE SCHEMA  ON SCHEMA  energy_utilities.production_optimizer TO `<app-sp-client-id>`;
GRANT SELECT      ON SCHEMA  energy_utilities.production_optimizer TO `<app-sp-client-id>`;
-- Warehouse: grant CAN_USE via the workspace UI or permissions API.
-- Genie Space: grant CAN_RUN via the workspace UI or permissions API.
```

## Project Support

This is a solution accelerator — not a production-ready application. It is provided as reference code to demonstrate patterns for combining Genie, the Foundation Model API, Vector Search, and Unity Catalog in a single multi-tab Databricks App. Review, adapt, and validate the code in your own environment before any operational use. Databricks makes no warranty regarding fitness for any particular purpose. See [LICENSE](LICENSE) and the repository-level [DISCLAIMER.md](../DISCLAIMER.md).

## License

See [LICENSE](LICENSE) and [NOTICE](NOTICE).
