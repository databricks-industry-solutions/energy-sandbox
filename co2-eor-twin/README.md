[![Databricks](https://img.shields.io/badge/Databricks-Solution_Accelerator-FF3621?style=for-the-badge&logo=databricks)](https://databricks.com)
[![Unity Catalog](https://img.shields.io/badge/Unity_Catalog-Enabled-00A1C9?style=for-the-badge)](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
[![Serverless](https://img.shields.io/badge/Serverless-Compute-00C851?style=for-the-badge)](https://docs.databricks.com/en/compute/serverless.html)

# CO2-EOR Digital Twin — Delaware Basin Operations Command Center

A real-time digital twin and agentic AI command center for managing CO2 Enhanced Oil Recovery (EOR) operations in the Permian Basin. Built as a [Databricks App](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) with an Express/TypeScript backend and React frontend, this solution demonstrates how Databricks can power carbon-aware upstream operations — from injection pattern management and CO2 mass balance through economics and environmental compliance.

## Overview

CO2-EOR is the largest-scale carbon utilization technology in the oil & gas industry, injecting CO2 into mature reservoirs to boost oil recovery while permanently storing carbon underground. This digital twin brings together real-time field operations, multi-agent AI, and environmental monitoring into a unified command center:

- **Geospatial Field Overview** — Interactive map of the Delaware Basin operation with 24 wells across 4 injection patterns, 6 pads, 4 facilities, pipelines, CO2 sources, monitoring stations, fleet assets, and flare points
- **Digital Twin** — Live operations view with subsurface reservoir visualization, DAS fiber optic monitoring, DTS temperature profiles, and microseismic event tracking
- **Injection Pattern Management** — 5-spot and inverted 5-spot patterns with CO2/WAG cycle tracking, breakthrough estimation, and slug volume monitoring
- **CO2 Mass Balance** — End-to-end CO2 accounting from source (Val Verde Gas Plant, Bravo Dome) through injection, recycling, and net storage
- **Economics** — Revenue, OPEX, CO2 cost, netback, incremental EOR economics, and breakeven analysis
- **Shift Log** — Structured operator shift handoff with agent action logging
- **Agentic AI Engine** — Five autonomous agents (Monitoring, Optimization, Maintenance, Commercial, Orchestrator) with proposal workflows and human-in-the-loop approval
- **Data & AI Flow** — Interactive architecture diagram showing the medallion pipeline

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Field Sensors (simulated)                                       │
│  24 wells × 12 tags, 4 facilities, 8 monitors, 6 pipelines      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Bronze    │  Raw telemetry, events
                    ├─────────────┤
                    │   Silver    │  Cleaned readings, health scores
                    ├─────────────┤
                    │    Gold     │  KPIs, pattern analytics, economics
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │        │        │        │        │
   ┌─────▼──┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼────┐
   │Monitor │ │Optim.│ │Maint.│ │Comm. │ │Orch.  │
   │ Agent  │ │Agent │ │Agent │ │Agent │ │Agent  │
   └────────┘ └──────┘ └──────┘ └──────┘ └───────┘
         │        │        │        │        │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │  React UI   │  Databricks App
                    │  + Express  │  7-tab command center
                    └─────────────┘
```

## Wells & Patterns

24 wells across 4 injection patterns in the Delaware Basin (~31.80°N, -103.50°W):

| Pattern | Type | Producers | Injectors | Zone | Phase |
|---------|------|-----------|-----------|------|-------|
| **Apache (PAT-A)** | 5-spot | 4 | 1 CO2 | Wolfcamp A | CO2 injection (cycle 5) |
| **Bravo (PAT-B)** | Inverted 5-spot | 4 | 2 WAG | Wolfcamp B | Water injection (cycle 4) |
| **Charlie (PAT-C)** | 5-spot | 4 | 1 CO2 | 2nd Bone Spring | CO2 injection (cycle 8) |
| **Delta (PAT-D)** | Inverted 5-spot | 4 | 1 CO2 | Wolfcamp A | CO2 injection (cycle 2) |

Plus 1 monitor well (Apache OBS-A) and 1 saltwater disposal well (SWD-1).

## Facilities

| Facility | Type | Key Metrics |
|----------|------|-------------|
| **Delaware Basin CPF** | Central Processing | 5,000 bbl/d oil capacity, 82% utilization |
| **CO2 Recycle Plant** | CO2 recovery | 10,000 Mcf/d CO2 capacity, 70% utilization |
| **CO2 Compression Station** | Compression | 12,000 Mcf/d, 88% utilization |
| **Salt Water Disposal** | SWD | 12,000 bbl/d water capacity |

## CO2 Sources

| Source | Type | Delivery | Purity | Cost |
|--------|------|----------|--------|------|
| Val Verde Gas Plant | Anthropogenic | 3,800 Mcf/d | 96% | $1.25/Mcf |
| Bravo Dome Supply | Natural | 5,200 Mcf/d | 98.5% | $0.85/Mcf |

## Environmental Monitoring

| Monitor | Type | Location | Threshold |
|---------|------|----------|-----------|
| Seismic Array North/South | Seismic | Field perimeter | 2.0 Richter |
| Pressure Gauges (×2) | Reservoir pressure | Pattern A / D | 3,500 psi |
| Soil Gas Sensors (×2) | CO2 leakage | NE / SW quadrants | 500 ppm |
| Groundwater Monitors (×2) | TDS contamination | N / S boundaries | 1,000 ppm |

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Field Overview** | Geospatial map with wells, facilities, pipelines, fleet, monitors, and alerts |
| **Data & AI Flow** | Interactive medallion pipeline architecture diagram |
| **Injection Patterns** | Pattern-by-pattern CO2/WAG cycle status, pressure tracking, breakthrough estimates |
| **CO2 Balance** | End-to-end carbon accounting — sourced, injected, recycled, stored, emitted |
| **Economics** | Revenue, OPEX, CO2 cost, netback, incremental EOR value, breakeven |
| **Shift Log** | Operator shift entries with agent actions and safety events |
| **Digital Twin** | Subsurface reservoir, DAS fiber optic, DTS temperature, and microseismic views |

## AI Agents

| Agent | Role | Autonomy | Example Action |
|-------|------|----------|----------------|
| **Monitoring** | Well & facility scanning | Autonomous | Flagged W-C01 rising CO2 concentration |
| **Optimization** | Injection rate tuning | Supervised | Proposed 8% injection reduction on Pattern A |
| **Maintenance** | Predictive maintenance | Advisory | Predicted ESP failure on W-C03, dispatched workover |
| **Commercial** | Economics & netback | Advisory | Daily netback calculation — $42.80/boe |
| **Orchestrator** | Agent coordination | Autonomous | Shift handoff synchronization |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/twin/state` | Full digital twin state (wells, facilities, KPIs, agents, alerts) |
| `GET` | `/api/twin/alerts` | Active alerts list |
| `GET` | `/api/commercial/economics` | Economics KPIs and netback calculations |
| `GET` | `/api/map/geojson` | GeoJSON feature collections for map rendering |
| `POST` | `/api/agent/chat` | Chat with the AI operations assistant |
| `GET` | `/api/shift/current` | Current shift log with entries |

## Getting Started

### Prerequisites

- A Databricks workspace with [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) enabled
- Databricks CLI installed and configured
- Node.js 18+ (for builds)

### Build

```bash
# Backend
npm install
npm run build

# Frontend
cd ui
npm install
npm run build
cd ..
```

### Deploy with Databricks Asset Bundles (recommended)

```bash
databricks bundle deploy -t dev
databricks bundle run -t dev
```

### Deploy manually

1. Import the app into your workspace:
   ```bash
   databricks workspace import-dir . /Workspace/Users/<your-email>/co2-eor-twin --overwrite
   ```

2. Create and deploy:
   ```bash
   databricks apps create co2-eor-twin --description "CO2-EOR Digital Twin"
   databricks apps deploy co2-eor-twin --source-code-path /Workspace/Users/<your-email>/co2-eor-twin
   ```

### Run Locally

```bash
# Terminal 1 — Backend
npm run dev

# Terminal 2 — Frontend (with HMR)
cd ui
npm run dev
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + TypeScript 5.6 + Vite 6 |
| **Backend** | Express 4 + TypeScript + tsx (dev) |
| **AI** | Multi-agent system with proposal workflows |
| **Deployment** | Databricks Apps (Node.js runtime) |

## Project Support

Please note the code in this project is provided for your exploration only, and is not formally supported by Databricks with Service Level Agreements (SLAs). It is provided AS-IS and we do not make any guarantees of any kind. Please do not submit a support ticket relating to any issues arising from the use of this project.

Any issues discovered through the use of this project should be filed as GitHub Issues on this repository. They will be reviewed on a best-effort basis but no formal SLA or support is guaranteed.

## Third-Party Library Licenses

(c) 2025 Databricks, Inc. All rights reserved. The source in this project is provided subject to the [Databricks License](LICENSE). All included or referenced third-party libraries are subject to the licenses set forth below.

### Backend Dependencies

| Library | License | Source |
|---------|---------|--------|
| express | MIT | https://github.com/expressjs/express |
| cors | MIT | https://github.com/expressjs/cors |
| typescript | Apache 2.0 | https://github.com/microsoft/TypeScript |

### Frontend Dependencies

| Library | License | Source |
|---------|---------|--------|
| react | MIT | https://github.com/facebook/react |
| react-dom | MIT | https://github.com/facebook/react |
| vite | MIT | https://github.com/vitejs/vite |
| typescript | Apache 2.0 | https://github.com/microsoft/TypeScript |
