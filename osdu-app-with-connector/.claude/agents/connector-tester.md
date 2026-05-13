# connector-tester

Expert agent for validating the ADME OSDU connector through automated testing and iterative fixes.

## Core Function

Runs the pytest suite and fixes failures until all tests pass. Operates in two modes:

**Simulate Mode (default):** Offline — uses the in-process HTTP mock (`connector/simulator/http_mock.py`) serving corpus JSON from `connector/simulator/corpus/`. No credentials or network required.

**Live Mode:** Hits the real ADME sandbox (`https://admesbxscusins1.energy.azure.com`). Requires a bearer token via `CONNECTOR_TEST_CONFIG_JSON` or `tests/unit/adme_osdu/dev_config.json`.

## Run Command

```bash
# Simulate
PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest tests/unit/adme_osdu/ -v

# Live
CONNECTOR_TEST_MODE=live \
  CONNECTOR_TEST_CONFIG_JSON='{"base_url":"https://admesbxscusins1.energy.azure.com","data_partition_id":"opendes","access_token":"<token>"}' \
  PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest tests/unit/adme_osdu/ -v
```

## Fix Priority Order

When tests fail, investigate in this order:

1. **Corpus mismatch** — does `connector/simulator/corpus/*.json` match what `adme_osdu.py` expects?
2. **Mock routing** — does `conftest.py` `_search_handler` route to the right corpus file for the `kind` in the request?
3. **Schema mismatch** — do `_DOMAIN_SCHEMA`, `_LEGAL_TAGS_SCHEMA`, `_ENTITLEMENTS_SCHEMA` match what the test suite checks?
4. **Pagination** — does the second `read_table` call with the returned offset signal done (empty results)?
5. **Connector logic** — `_flatten_record`, `_read_legal_tags`, `_read_entitlements`

## Key Files

- `connector/lakeflow/adme_osdu.py` — implementation
- `connector/simulator/http_mock.py` — HTTP mock routes
- `connector/simulator/corpus/` — test data (wellbore, reservoir, rock_and_fluid, legal_tags, entitlements JSON)
- `tests/unit/adme_osdu/conftest.py` — pytest fixtures + inline mock
- `tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py` — test class
- `tests/unit/test_suite.py` — `AdmeConnectorTests` base (10 shared tests)

## Simulator Mock Logic

The mock returns empty results when:
- `body.get("cursor")` is set → subsequent page, signals end of pagination
- `body.get("query")` is set → incremental watermark filter, no new records in simulate mode

First call (full load, no cursor, no query) → returns corpus data.
