# CLAUDE.md

ADME OSDU Connector — ingests Azure Data Manager for Energy (OSDU) records into Databricks Unity Catalog Delta tables via the LakeflowConnect interface.

## Key Constraint

This is a single-connector standalone repo. When modifying the connector, work in these directories only:
- `connector/lakeflow/` — LakeflowConnect interface + AdmeOsduLakeflowConnect implementation
- `connector/simulator/` — HTTP mock and corpus JSON fixtures
- `tests/unit/adme_osdu/` — pytest suite (conftest, test file)

Do **not** change `connector/clients/`, `connector/auth/`, `connector/models/`, `connector/domains/`, or `connector/governance/` unless explicitly asked — those are shared infrastructure.

## Reference Files

- **Interface**: `connector/lakeflow/interface.py` (`LakeflowConnect` ABC)
- **Implementation**: `connector/lakeflow/adme_osdu.py` (`AdmeOsduLakeflowConnect`)
- **Test harness**: `tests/unit/test_suite.py` (`AdmeConnectorTests` base class)
- **Test file**: `tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py`
- **Simulator**: `connector/simulator/http_mock.py` + `connector/simulator/corpus/*.json`
- **Connector spec**: `connector_spec.yaml`

## Running Tests

Tests run offline by default using the in-process HTTP mock (respx stub). No credentials needed.

```bash
PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest tests/unit/adme_osdu/ -v
```

Live mode (needs `dev_config.json` or env var):
```bash
CONNECTOR_TEST_MODE=live \
  CONNECTOR_TEST_CONFIG_JSON='{"base_url":"...","data_partition_id":"opendes","access_token":"<token>"}' \
  PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest tests/unit/adme_osdu/ -v
```

Stand-in credentials for simulate mode are declared as `replay_config` on the test class — the simulator never validates them.

## ADME Specifics

- **API**: `POST /api/search/v2/query` (cursor-based), `GET /api/legal/v1/legaltags`, `GET /api/entitlements/v2/groups`
- **Auth**: static_token (tests), managed_identity or service_principal (production)
- **Sandbox**: `https://admesbxscusins1.energy.azure.com`, partition `opendes`, tenant `72f988bf-86f1-41af-91ab-2d7cd011db47`, adme_api_client_id `e37a6c70-7cbc-4593-80fc-01c1f20203f7`
- **Live token**: `az account get-access-token --resource "api://e37a6c70-7cbc-4593-80fc-01c1f20203f7" --tenant "72f988bf-86f1-41af-91ab-2d7cd011db47"`

## Workflow

1. `/develop-connector` — Phase 1: implement changes, fix simulator, run simulate-mode tests (no credentials)
2. `/validate-connector` — Phase 2: authenticate against real ADME, run live tests, re-seed corpus

## Dependency Notes

`tests/stubs/` contains minimal offline stubs for `azure.identity`, `azure.core.credentials`, `tenacity`, and `respx`. The root `conftest.py` injects these into `sys.path` before any connector imports. This allows tests to run without `pip install` access.
