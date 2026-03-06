[![Databricks](https://img.shields.io/badge/Databricks-Solution_Accelerator-FF3621?style=for-the-badge&logo=databricks)](https://databricks.com)
[![Unity Catalog](https://img.shields.io/badge/Unity_Catalog-Enabled-00A1C9?style=for-the-badge)](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
[![Serverless](https://img.shields.io/badge/Serverless-Compute-00C851?style=for-the-badge)](https://docs.databricks.com/en/compute/serverless.html)

# Pipeline Command Center — Midstream Pipeline Digital Twin

A real-time digital twin and agentic AI command center for monitoring midstream oil & gas pipeline networks. Built as a [Databricks App](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) using Streamlit, this solution demonstrates how Databricks can power critical infrastructure monitoring for midstream pipeline operations across the Eagle Ford Trunk system.

<img src="images/pipeline_overview.png" alt="Pipeline Command Center — Pipeline Overview" width="100%">

## Overview

Midstream pipeline operators manage hundreds of miles of trunk lines with compressor stations, pump stations, metering, pigging, and cathodic protection systems. Pipeline Command Center brings together real-time telemetry simulation, predictive maintenance, crew management, and multi-agent AI into a single command center:

- **Digital Twin Visualization** — Live SVG schematic of the 87.3-mile Eagle Ford Midstream Trunk with traffic-light health indicators, pressure readings, and fill-level bars for all 18 assets (pipe segments, compressor stations, pump stations, meters, pig launchers/receivers, valves, RTUs, cathodic protection)
- **Agentic AI Engine** — Six rule-based sub-agents (Health, Integrity, Leak Detection, Operations, Compliance, Crew Allocation) analyze every simulator tick and produce severity-ranked recommendations with automatic crew dispatch
- **AI Crew Allocation** — Skill-based crew dispatch with certification tiers, proximity scoring, workload balancing, multi-crew incident matrix, and reasoning chains explaining each assignment
- **Predictive Maintenance** — Remaining Useful Life (RUL) predictions, failure probability forecasting, and failure pattern matching per asset
- **SCADA / ERP Integration** — Work order tracking, spare parts inventory with min-stock alerts, and operations schedule
- **Data & AI Flow** — Interactive Lakeflow-style architecture diagram showing the medallion pipeline from sensors through Bronze/Silver/Gold to serving agents

<img src="images/data_ai_flow.png" alt="Data & AI Architecture Flow" width="100%">

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Pipeline Sensors (simulated)                                    │
│  18 assets × 3-5 tags each → telemetry stream                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Bronze    │  Raw telemetry, events, anomalies
                    ├─────────────┤
                    │   Silver    │  Cleaned readings, health scores
                    ├─────────────┤
                    │    Gold     │  KPIs, RUL predictions, work orders
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │        │        │        │        │
   ┌─────▼──┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼────┐
   │ Health │ │Integ.│ │ Leak │ │ Ops  │ │Compli.│
   │ Agent  │ │Agent │ │Agent │ │Agent │ │Agent  │
   └────────┘ └──────┘ └──────┘ └──────┘ └───────┘
         │        │        │        │        │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Crew       │  Skill-based dispatch
                    │  Allocation │  with reasoning chains
                    │  Agent      │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Streamlit  │  Databricks App
                    │  Dashboard  │  8-tab command center
                    └─────────────┘
```

**Assets monitored:**
| Asset ID | Component | Key Sensors |
|----------|-----------|-------------|
| PS-01, PS-02 | Pipe Segments | Wall thickness, pressure, flow rate, temperature |
| CS-01, CS-02 | Compressor Stations | Discharge pressure, suction pressure, vibration, temperature |
| PMP-01 | Pump Station | Discharge pressure, flow rate, current, vibration |
| MTR-01, MTR-02 | Metering Stations | Flow rate, pressure, temperature, density |
| PIG-01, PIG-02 | Pig Launcher/Receiver | Pressure, pig position, signal strength |
| VLV-01 to VLV-04 | Block/Check Valves | Position, actuator pressure, cycle count, leak rate |
| RTU-01, RTU-02 | Remote Terminal Units | CPU load, memory, signal strength, battery |
| CP-01 | Cathodic Protection | Rectifier voltage, current, pipe-to-soil potential |

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Pipeline Overview** | Live digital twin with KPI tiles, full-width SVG schematic, traffic-light health, status bar with crew dispatch |
| **Diagnostics** | Sensor trend charts, anomaly overlays, component deep-dives |
| **Predictive Maint.** | RUL predictions, failure probability, failure pattern library |
| **Events & Alarms** | Real-time event log with severity filtering |
| **SCADA / ERP** | Work orders, spare parts inventory, operations schedule |
| **Crew & Ops** | Crew roster, certification matrix, AI-driven crew allocation with skill scores and reasoning |
| **Data & AI Flow** | Interactive Lakeflow-style architecture diagram with medallion pipeline |
| **Pipeline Advisor** | Natural-language chat interface to the agentic AI engine |

<img src="images/pipeline_advisor.png" alt="Pipeline Advisor — AI Chat Interface" width="100%">

## Getting Started

### Prerequisites

- A Databricks workspace with [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) enabled
- Databricks CLI installed and configured

### Deploy as a Databricks App

1. Clone this repository into your Databricks workspace:
   ```bash
   databricks workspace import-dir ./app /Workspace/Users/<your-email>/pipeline-command-center/app --overwrite
   databricks workspace import-file ./app.yaml /Workspace/Users/<your-email>/pipeline-command-center/app.yaml --overwrite
   ```

2. Create and deploy the app:
   ```bash
   databricks apps create pipeline-command-center --description "Midstream Pipeline Digital Twin Command Center"
   databricks apps deploy pipeline-command-center --source-code-path /Workspace/Users/<your-email>/pipeline-command-center
   ```

3. Open the app URL printed by the deploy command.

## Simulated Event Cycle

The simulator runs a repeating 40-tick event cycle to demonstrate anomaly detection and agent response:

| Ticks | Event | Affected Assets |
|-------|-------|-----------------|
| 0–9 | Normal operations | All green |
| 10–14 | Wall thinning detected | Pipe Segment PS-01 |
| 15–19 | Compressor vibration anomaly | Compressor Station CS-01 |
| 20–24 | Pressure drop / potential leak | Pipe Segment PS-02 |
| 25–29 | Valve actuator degradation | Block Valve VLV-02 |
| 30–34 | Recovery / stabilization | Systems recovering |
| 35–39 | Cathodic protection decay | CP System CP-01 |

## AI Crew Allocation

The Crew Allocation Agent uses a composite scoring system for intelligent dispatch:

- **Certification Tiers** — Crew members ranked by specialization (Pipeline Inspector, Corrosion Engineer, Compressor Tech, etc.)
- **Proximity Scoring** — Distance-weighted assignment for faster response
- **Workload Balancing** — Tracks concurrent assignments per crew member (max 2)
- **Multi-Crew Dispatch** — INCIDENT_CREW_MATRIX defines required roles per (asset_type, severity) combination
- **Reasoning Chains** — Each assignment includes a natural-language explanation of why that crew member was selected

## Project Support

Please note the code in this project is provided for your exploration only, and is not formally supported by Databricks with Service Level Agreements (SLAs). It is provided AS-IS and we do not make any guarantees of any kind. Please do not submit a support ticket relating to any issues arising from the use of this project.

Any issues discovered through the use of this project should be filed as GitHub Issues on this repository. They will be reviewed on a best-effort basis but no formal SLA or support is guaranteed.



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
