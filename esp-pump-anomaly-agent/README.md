[![Databricks](https://img.shields.io/badge/Databricks-Solution_Accelerator-FF3621?style=for-the-badge&logo=databricks)](https://databricks.com)
[![Unity Catalog](https://img.shields.io/badge/Unity_Catalog-Enabled-00A1C9?style=for-the-badge)](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
[![Serverless](https://img.shields.io/badge/Serverless-Compute-00C851?style=for-the-badge)](https://docs.databricks.com/en/compute/serverless.html)

# ESP Fleet Operations Command Center

A real-time ESP (Electric Submersible Pump) fleet monitoring platform built as a [Databricks App](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) with a Streamlit frontend. It combines high-frequency pump telemetry, threshold and statistical anomaly detection, an ML failure-prediction model, and a natural-language AI assistant, all on Unity Catalog and serverless compute.

## Overview

ESP failures are costly and hard to see coming in raw high-frequency telemetry. This app gives operators a single pane of glass:

- **Demo Guide**: a guided walkthrough with Scene, Business Case, What We'll Prove, and Databricks Story framing plus a click-through script.
- **Fleet Dashboard**: fleet posture KPIs, sensor gauges (motor temp, intake pressure, vibration, flow), an ML failure-probability ranking, a risk-distribution donut, and a sortable well status table.
- **Well Detail**: pick a well to see live readout tiles and a 24-hour, 4-sensor telemetry chart with threshold lines.
- **AI Investigation**: a Supervisor agent that routes between the live telemetry (Genie) and the ESP procedure documents, plus an optional live-SQL tool agent.
- **Data & Flow**: an interactive Data & AI flow diagram (Sources to Medallion to Serving) with click-to-detail.
- **Ask Genie sidebar**: natural-language questions over the fleet, available on every tab.

## Data (Unity Catalog)

All objects live in `oil_pump_monitor_catalog.esp_hackathon`:

| Object | Type | Description |
|---|---|---|
| `pump_telemetry` | Managed Delta | High-frequency pressure, temperature, vibration, current readings per well |
| `latest_reading_per_well` | View | Newest reading per well, drives the live dashboard |
| `pump_features` / `pump_features_hourly` | Managed Delta | Aggregated features for ML (per well-hour) |
| `pump_failure_predictions` | Managed Delta | ML failure-probability score per well-hour |

## Architecture

- **Data access**: serverless SQL warehouse via the Databricks SDK Statement Execution API (native app OAuth).
- **AI**: a Mosaic AI Multi-Agent Supervisor over a Genie space (telemetry) and a Knowledge Assistant (ESP procedures), plus a Mosaic AI tool agent with 6 live SQL functions.
- **Governance**: Unity Catalog governs all data; the app's service principal is granted USE CATALOG, USE SCHEMA, SELECT, and CAN_QUERY on the serving endpoints.

## Deploy

```bash
databricks workspace import-dir . /Workspace/Users/<you>/esp-pump-anomaly-agent --overwrite
databricks apps deploy esp-pump-anomaly-agent --source-code-path /Workspace/Users/<you>/esp-pump-anomaly-agent
```

Configure `app.yaml` env for your workspace: `AGENT_MODEL`, `DATABRICKS_WAREHOUSE_ID`, `GENIE_SPACE_ID`, `MAS_ENDPOINT`.

## Notes

The SQL warehouse and the AI serving endpoints scale to zero, so the first request after an idle period cold-starts (10 to 60 seconds), then runs fast. Warm them before a live demo.
