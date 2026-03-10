[![Databricks](https://img.shields.io/badge/Databricks-Solution_Accelerators-FF3621?style=for-the-badge&logo=databricks)](https://databricks.com)
[![Unity Catalog](https://img.shields.io/badge/Unity_Catalog-Enabled-00A1C9?style=for-the-badge)](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)

# Energy Sandbox

A collection of Databricks solution accelerators for the **upstream and midstream oil & gas** industry. Each project demonstrates end-to-end data engineering, real-time analytics, and AI capabilities on the Databricks Lakehouse Platform.

## Projects

| Project | Description | Key Technologies |
|---------|-------------|-----------------|
| [**BOP Guardian**](bop-guardian/) | Offshore Blowout Preventer monitoring command center with a digital twin P&ID schematic, five agentic AI sub-agents, predictive maintenance, SAP ERP integration, and crew management. | Databricks Apps, Streamlit, Lakebase, Foundation Model API |
| [**CO2-EOR Digital Twin**](co2-eor-twin/) | CO2 Enhanced Oil Recovery digital twin for the Delaware Basin with 24 wells across 4 injection patterns, multi-agent AI (monitoring, optimization, maintenance, commercial, orchestrator), CO2 mass balance, economics, and environmental compliance. | Databricks Apps, Express, React, Node.js |
| [**ESP Predictive Maintenance**](esp-pm/) | Electric Submersible Pump monitoring and failure prediction for 12 wells across the Permian Basin, Eagle Ford, DJ Basin, Bakken, and Marcellus. XGBoost ML pipeline, streaming inference, and SAP maintenance integration. | Databricks Apps, Streamlit, Lakebase, XGBoost, Foundation Model API |
| [**LAS Viewer**](las-viewer/) | Enterprise well log visualization and petrophysics platform. Interactive SVG log curve viewer, automated QC, processing recipes, and AI-powered petrophysical advisory. | Databricks Apps, FastAPI, React, Lakebase, Foundation Model API |
| [**Oil Pump Vibration Monitor**](oil-pump-monitor/) | Real-time vibration monitoring for fracking pumps in the North Dakota Bakken Formation. Live dashboards, FFT spectrum analysis, anomaly detection, and an AI operations assistant. | Databricks Apps, FastAPI, React, Lakebase, Foundation Model API |
| [**Pipeline Command Center**](pipeline-command-center/) | Midstream pipeline digital twin command center with 18 assets across the Eagle Ford Trunk. Six agentic AI sub-agents, skill-based crew dispatch, predictive maintenance, and SCADA/ERP integration. | Databricks Apps, Streamlit, Lakebase, Foundation Model API |
| [**Reservoir Simulator**](reservoir-simulator/) | Interactive 3D reservoir simulation and production optimization platform calibrated to the Norne field (North Sea) benchmark. Scenario management, well performance, economic evaluation, and SAP ERP integration. | Databricks Apps, Streamlit, Three.js, Lakebase, Foundation Model API |
| [**ROP Prediction**](rop-prediction/) | Real-time Rate of Penetration prediction and drilling optimization using MSEEL field data. XGBoost ML pipeline, Spark Structured Streaming inference, hazard detection, and SAP ERP integration. | Databricks Apps, Streamlit, Lakebase, XGBoost, Foundation Model API |

## Getting Started

Each project is self-contained in its own directory with its own README, deployment instructions, and dependencies. Navigate to the project folder for detailed setup guides.

### Deploy with Databricks Asset Bundles

Each project includes a `databricks.yml` for deployment via [Databricks Asset Bundles](https://docs.databricks.com/en/dev-tools/bundles/index.html):

```bash
cd <project-directory>
databricks bundle deploy -t dev
databricks bundle run -t dev
```

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
