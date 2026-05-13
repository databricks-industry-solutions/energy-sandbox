---
name: test-and-fix-connector
description: "Run the AdmeOsduLakeflowConnect pytest suite, diagnose failures, and fix the connector or simulator until everything passes. Branches on mode={simulate|live}."
---

# Test and Fix the ADME OSDU Connector

## Goal

Validate **AdmeOsduLakeflowConnect** by running its pytest suite and applying
minimal fixes until everything passes.

| Mode       | When                    | Credentials        | Posture                                               |
|------------|-------------------------|--------------------|-------------------------------------------------------|
| `simulate` | Default (no creds)      | None — uses corpus | Either connector or corpus could be wrong — judge on merits |
| `live`     | Record against real ADME | dev_config.json   | Live API is authoritative — fix corpus/spec first     |

## 0. Rules (both modes)

- **Run pytest synchronously** — never in background. Never use `sleep`, poll loops, or `tail`.
- Do NOT run exploratory scripts before the test file exists.
- Read implementation source before diagnosing failures.

## 1. Setup (skip if test file already exists)

Verify these files exist:
- `connector/lakeflow/interface.py`
- `connector/lakeflow/adme_osdu.py`
- `connector/simulator/corpus/wellbore.json`
- `connector/simulator/corpus/reservoir.json`
- `connector/simulator/corpus/rock_and_fluid.json`
- `connector/simulator/corpus/legal_tags.json`
- `connector/simulator/corpus/entitlements.json`
- `tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py`

---

## SIMULATE MODE

### S1. Install dependencies
```bash
pip install -e ".[dev]" -q 2>/dev/null || pip install -r requirements-dev.txt -q
```

### S2. Run simulate-mode tests
```bash
pytest tests/unit/adme_osdu/ -v
```

No `CONNECTOR_TEST_MODE` env var. No credentials. No network.

### S3. Diagnose failures
- **Schema mismatch** — connector returns field not in schema, or schema field missing from record
- **Corpus bug** — primary key is None, modifyTime missing, JSON malformed
- **Routing bug** — search handler picks wrong corpus file (check `kind` field routing in conftest.py)
- **Pagination loop** — `read_terminates` fails because offset never stabilises; check `_read_domain` returns `start_offset` unchanged when results is empty

Fix the connector or corpus as needed. Iterate until all tests pass.

---

## LIVE MODE

### L1. Credentials

Place `tests/unit/adme_osdu/dev_config.json` (gitignored):
```json
{
  "base_url": "https://YOUR-ADME.energy.azure.com",
  "data_partition_id": "YOUR-PARTITION",
  "access_token": "YOUR-BEARER-TOKEN"
}
```

Or set `CONNECTOR_TEST_CONFIG_JSON` env var.

### L2. Run live tests
```bash
CONNECTOR_TEST_MODE=live pytest tests/unit/adme_osdu/ -v
```

### L3. Seed corpus from live responses

After a successful live run, update corpus files with real data:
- Copy representative records from the live responses into `connector/simulator/corpus/*.json`
- Keep 3–5 records per domain; real data improves simulate-mode realism

### L4. Final simulate pass
```bash
pytest tests/unit/adme_osdu/ -v
```

Must still be green.

---

## Debugging Hangs (live mode)

If a test hangs on a domain table:
1. Set a tight `page_size` — edit `conf/domains/wellbore.yaml` and set `page_size: 5`
2. Enable debug logging: `pytest ... -s --log-cli-level=DEBUG`
3. If search still hangs, check `incremental_filter_template` — an unbounded `query: ""` on large partitions can time out

## Merge note

After fixing the connector, no merge script is needed (this is a standalone repo, not the community connector monorepo).
