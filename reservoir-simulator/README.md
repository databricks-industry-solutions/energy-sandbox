[![Databricks](https://img.shields.io/badge/Databricks-Solution_Accelerator-FF3621?style=for-the-badge&logo=databricks)](https://databricks.com)
[![Unity Catalog](https://img.shields.io/badge/Unity_Catalog-Enabled-00A1C9?style=for-the-badge)](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
[![Serverless](https://img.shields.io/badge/Serverless-Compute-00C851?style=for-the-badge)](https://docs.databricks.com/en/compute/serverless.html)

# Reservoir Simulator

A real-time reservoir simulation and production optimization platform built as a [Databricks App](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html). This solution accelerator demonstrates an interactive 3D reservoir model — with scenario management, well performance analysis, economic evaluation, and SAP ERP integration — for upstream oil & gas reservoir engineering workflows. The simulator uses a simplified analytical engine calibrated to the [Norne field](https://opm-project.org/?page_id=559) (North Sea) benchmark dataset.

<img src="images/ressim_3d_reservoir.png" alt="Reservoir Simulator — 3D Reservoir Visualization" width="100%">

## Overview

Reservoir simulation is the cornerstone of field development planning. A single simulation study can influence $100M+ in capital allocation decisions. This accelerator delivers:

- **Scenario Management** — Create, configure, and compare simulation scenarios with adjustable well rates, injection strategies, and economic assumptions
- **3D Reservoir Visualization** — Interactive Three.js-powered 3D viewport with oil/water saturation heatmaps, well trajectories, and layer-by-layer navigation
- **Well Results** — Per-well production profiles (oil, water, gas), cumulative curves, water cut trends, and GOR tracking across simulation timesteps
- **Operations** — Operational KPIs, well status monitoring, and field-level production summaries

<img src="images/ressim_economics.png" alt="Reservoir Simulator — Economics & NPV Analysis" width="100%">

- **Cost Analysis** — Detailed cost breakdown with SAP BDC integration for CAPEX/OPEX tracking, procurement, and vendor contracts

<img src="images/ressim_cost_analysis.png" alt="Reservoir Simulator — Cost Analysis with SAP BDC" width="100%">

- **Economics** — NPV, IRR, payout period, and cashflow analysis with configurable oil price, discount rate, and fiscal terms
- **Scenario Comparison** — Side-by-side comparison of multiple simulation runs with production, economics, and efficiency metrics
- **Reservoir Agent** — Foundation Model API-powered AI assistant for natural-language reservoir analysis and optimization recommendations
- **Data & AI Flow** — Interactive architecture diagram showing the end-to-end pipeline from Norne data through simulation to serving

## Architecture

<img src="images/ressim_dataflow.png" alt="Reservoir Simulator — Data & AI Flow" width="100%">

## Dashboard Tabs

<img src="images/ressim_scenarios.png" alt="Reservoir Simulator — Scenario Management" width="100%">

| Tab | Description |
|-----|-------------|
| **Scenarios** | Create and manage simulation scenarios with well configuration, injection rates, and economic parameters |
| **3D Reservoir** | Interactive Three.js viewport with oil/water saturation, pressure distribution, well paths, and layer navigation |
| **Well Results** | Per-well production curves (oil, water, gas), cumulative production, water cut, and GOR over time |
| **Operations** | Field-level operational KPIs, well status, and production summary |
| **Cost Analysis** | CAPEX/OPEX breakdown with SAP BDC integration, procurement tracking, and vendor contracts |
| **Economics** | NPV, IRR, payout, cashflow waterfall with configurable price decks and fiscal assumptions |
| **Compare** | Side-by-side scenario comparison with production, economics, and efficiency delta analysis |
| **Agent** | AI-powered reservoir engineering assistant using Foundation Model API |
| **Data & AI Flow** | Interactive architecture diagram showing the simulation pipeline |

<img src="images/ressim_sap.png" alt="Reservoir Simulator — SAP Work Orders" width="100%">

## Reservoir Model

The Res Flow engine is a lightweight analytical simulator calibrated to the [Norne field](https://opm-project.org/?page_id=559) — a real North Sea oil field operated by Equinor. It uses distance-based pressure decline, saturation tracking, and heuristic production curves on a representative sub-grid (the full Norne deck is 46×112×22). Res Flow reproduces realistic field behavior for demonstration and visualization purposes:

| Parameter | Value |
|-----------|-------|
| Grid | 20 × 10 × 5 (1,000 cells) |
| Timesteps | 40 |
| Porosity | 0.15 – 0.30 |
| Permeability | 50 – 500 mD |
| Initial Pressure | 3,000 psi |
| Oil Viscosity | 2.0 cp |
| Water Viscosity | 0.5 cp |

## Wells

| Well | Type | Location | Description |
|------|------|----------|-------------|
| B-2H | Producer | (5, 3) | Primary producer, north sector |
| D-1H | Producer | (15, 7) | Primary producer, south sector |
| E-3H | Producer | (10, 5) | Central producer |
| D-2H | Producer | (8, 8) | Secondary producer |
| C-4H | Injector | (10, 5) | Water injection for pressure support |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + TypeScript + Vite |
| 3D Rendering | Three.js + React Three Fiber + Drei |
| Charts | Recharts |
| Data Platform | Databricks SQL Warehouse + Unity Catalog |

## Getting Started

### Prerequisites

- A Databricks workspace with [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) and a SQL Warehouse
- Databricks CLI installed and configured
- Unity Catalog enabled
- Node.js 18+ (for frontend builds)

### Deploy the Databricks App

1. Update `app.yaml` with your SQL Warehouse ID.

2. Import the app into your workspace:
   ```bash
   databricks workspace import-dir ./server /Workspace/Users/<your-email>/reservoir-simulator/server --overwrite
   databricks workspace import-dir ./frontend /Workspace/Users/<your-email>/reservoir-simulator/frontend --overwrite
   databricks workspace import-file ./app.yaml /Workspace/Users/<your-email>/reservoir-simulator/app.yaml --overwrite
   ```

3. Create and deploy:
   ```bash
   databricks apps create reservoir-simulator --description "Reservoir Simulator"
   databricks apps deploy reservoir-simulator --source-code-path /Workspace/Users/<your-email>/reservoir-simulator
   ```

## Project Support

Please note the code in this project is provided for your exploration only, and is not formally supported by Databricks with Service Level Agreements (SLAs). It is provided AS-IS and we do not make any guarantees of any kind. Please do not submit a support ticket relating to any issues arising from the use of this project.

Any issues discovered through the use of this project should be filed as GitHub Issues on this repository. They will be reviewed on a best-effort basis but no formal SLA or support is guaranteed.

## Third-Party Library Licenses

(c) 2025 Databricks, Inc. All rights reserved. The source in this project is provided subject to the [Databricks License](LICENSE). All included or referenced third-party libraries are subject to the licenses set forth below.

| Library | License | Source |
|---------|---------|--------|
| react | MIT | https://github.com/facebook/react |
| three | MIT | https://github.com/mrdoob/three.js |
| @react-three/fiber | MIT | https://github.com/pmndrs/react-three-fiber |
| @react-three/drei | MIT | https://github.com/pmndrs/drei |
| recharts | MIT | https://github.com/recharts/recharts |
| vite | MIT | https://github.com/vitejs/vite |
| typescript | Apache 2.0 | https://github.com/microsoft/TypeScript |


## License

**Definitions.**

**Agreement:** The agreement between Databricks, Inc., and you governing the use of the Databricks Services, as that term is defined in the Master Cloud Services Agreement (MCSA) located at www.databricks.com/legal/mcsa.

**Licensed Materials:** The source code, object code, data, and/or other works to which this license applies.

**Scope of Use.** You may not use the Licensed Materials except in connection with your use of the Databricks Services pursuant to the Agreement. Your use of the Licensed Materials must comply at all times with any restrictions applicable to the Databricks Services, generally, and must be used in accordance with any applicable documentation. You may view, use, copy, modify, publish, and/or distribute the Licensed Materials solely for the purposes of using the Licensed Materials within or connecting to the Databricks Services. If you do not agree to these terms, you may not view, use, copy, modify, publish, and/or distribute the Licensed Materials.

**Redistribution.** You may redistribute and sublicense the Licensed Materials so long as all use is in compliance with these terms. In addition:

- You must give any other recipients a copy of this License;
- You must cause any modified files to carry prominent notices stating that you changed the files;
- You must retain, in any derivative works that you distribute, all copyright, patent, trademark, and attribution notices, excluding those notices that do not pertain to any part of the derivative works; and
- If a "NOTICE" text file is provided as part of its distribution, then any derivative works that you distribute must include a readable copy of the attribution notices contained within such NOTICE file, excluding those notices that do not pertain to any part of the derivative works.

You may add your own copyright statement to your modifications and may provide additional license terms and conditions for use, reproduction, or distribution of your modifications, or for any such derivative works as a whole, provided your use, reproduction, and distribution of the Licensed Materials otherwise complies with the conditions stated in this License.

**Termination.** This license terminates automatically upon your breach of these terms or upon the termination of your Agreement. Additionally, Databricks may terminate this license at any time on notice. Upon termination, you must permanently delete the Licensed Materials and all copies thereof.

**DISCLAIMER; LIMITATION OF LIABILITY.**

THE LICENSED MATERIALS ARE PROVIDED "AS-IS" AND WITH ALL FAULTS. DATABRICKS, ON BEHALF OF ITSELF AND ITS LICENSORS, SPECIFICALLY DISCLAIMS ALL WARRANTIES RELATING TO THE LICENSED MATERIALS, EXPRESS AND IMPLIED, INCLUDING, WITHOUT LIMITATION, IMPLIED WARRANTIES, CONDITIONS AND OTHER TERMS OF MERCHANTABILITY, SATISFACTORY QUALITY OR FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. DATABRICKS AND ITS LICENSORS TOTAL AGGREGATE LIABILITY RELATING TO OR ARISING OUT OF YOUR USE OF OR DATABRICKS' PROVISIONING OF THE LICENSED MATERIALS SHALL BE LIMITED TO ONE THOUSAND ($1,000) DOLLARS. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE LICENSED MATERIALS OR THE USE OR OTHER DEALINGS IN THE LICENSED MATERIALS.
