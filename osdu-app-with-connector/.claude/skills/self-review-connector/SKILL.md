---
name: self-review-connector
description: Mechanical audit of the ADME OSDU connector — implementation correctness, test coverage, artifacts completeness, and security. Produces a scored report.
disable-model-invocation: true
---

# Self-Review: ADME OSDU Connector

## Scoring

| Band | Score | Verdict |
|------|-------|---------|
| 90+ | — | READY |
| 75–89 | — | ALMOST |
| 50–74 | — | NEEDS WORK |
| < 50 or BLOCKER | — | NOT READY |

Severity weights: BLOCKER (−10), MAJOR (−3), MINOR (−1).

---

## Section A — Implementation (max 30)

Check each item. Award points for PASS, deduct for failures.

| # | Check | How | Points |
|---|-------|-----|--------|
| A1 | `AdmeOsduLakeflowConnect` extends `LakeflowConnect` | `grep "class AdmeOsduLakeflowConnect" connector/lakeflow/adme_osdu.py` | 3 |
| A2 | All 4 abstract methods implemented | grep for `def list_tables`, `def get_table_schema`, `def read_table_metadata`, `def read_table` | 4 |
| A3 | `read_table` returns `(Iterator, offset\|None)` | Read `_read_domain`, `_read_legal_tags`, `_read_entitlements` return types | 3 |
| A4 | Pagination terminates — empty results return `start_offset` unchanged | Read `_read_domain`: check `if not records: return iter([]), start_offset` | 4 |
| A5 | Governance tables return `None` offset | Check `_read_legal_tags` and `_read_entitlements` return `(iter(rows), None)` | 3 |
| A6 | `incremental_filter_template` set on domain configs | `grep incremental_filter_template connector/lakeflow/adme_osdu.py` | 3 |
| A7 | `_flatten_record` extracts all `_DOMAIN_SCHEMA` fields | Compare `_flatten_record` output keys against `_DOMAIN_SCHEMA` names | 3 |
| A8 | No hardcoded real tokens or secrets | `grep -r "eyJ\|Bearer " connector/lakeflow/` — must find none | BLOCKER |
| A9 | HTTP client uses `with self._new_client() as client:` pattern (closes cleanly) | Read `_read_domain`, `_read_legal_tags`, `_read_entitlements` | 2 |
| A10 | Unknown table raises `ValueError` | Read `read_table`, `get_table_schema`, `read_table_metadata` | 1 |

---

## Section B — Testing (max 30)

| # | Check | How | Points |
|---|-------|-----|--------|
| B1 | All 10 base `AdmeConnectorTests` tests present | `grep "def test_" tests/unit/test_suite.py \| wc -l` ≥ 10 | 3 |
| B2 | All ADME-specific tests present | `grep "def test_" tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py \| wc -l` ≥ 8 | 3 |
| B3 | Simulate tests all pass | `PYTHONPATH=. pytest tests/unit/adme_osdu/ -v` — 0 failures | BLOCKER |
| B4 | `conftest.py` autouse mock fixture present | `grep "autouse=True" tests/unit/adme_osdu/conftest.py` | 2 |
| B5 | Mock handles cursor pagination (returns empty on cursor) | `grep "body.get.*cursor" tests/unit/adme_osdu/conftest.py` | 2 |
| B6 | Mock handles incremental filter (returns empty on query) | `grep "body.get.*query" tests/unit/adme_osdu/conftest.py` | 2 |
| B7 | Corpus has ≥ 3 records per domain table | `python3 -c "import json; d=json.load(open('connector/simulator/corpus/wellbore.json')); print(len(d))"` ≥ 3 | 2 |
| B8 | Legal tags corpus has correct wrapper format | `python3 -c "import json; d=json.load(open('connector/simulator/corpus/legal_tags.json')); assert 'legalTags' in d"` | 2 |
| B9 | Entitlements corpus has correct wrapper format | `assert 'groups' in json.load(open('connector/simulator/corpus/entitlements.json'))` | 2 |
| B10 | `dev_config.json.template` present (documents live config format) | `ls tests/unit/adme_osdu/dev_config.json.template` | 2 |
| B11 | `dev_config.json` absent (not committed) | `ls tests/unit/adme_osdu/dev_config.json` must NOT exist | MAJOR |
| B12 | Stubs directory present and functional | `python3 -c "import sys; sys.path.insert(0,'tests/stubs'); import respx, tenacity"` | 3 |
| B13 | Root `conftest.py` injects stubs | `grep "tests/stubs" conftest.py` | 1 |
| B14 | Test mode env var documented | `grep CONNECTOR_TEST_MODE tests/unit/adme_osdu/conftest.py` | 1 |

---

## Section C — Artifacts (max 20)

| # | Check | How | Points |
|---|-------|-----|--------|
| C1 | `CLAUDE.md` present and has ADME-specific content | `grep admesbx CLAUDE.md` | 3 |
| C2 | `connector_spec.yaml` present and valid YAML | `python3 -c "import yaml; yaml.safe_load(open('connector_spec.yaml'))"` | 3 |
| C3 | `connector_spec.yaml` documents all required connection params | Check for `base_url`, `data_partition_id`, `adme_api_client_id`, `tenant_id` | 3 |
| C4 | `README.md` present | `ls README.md` | 2 |
| C5 | `requirements.txt` and `requirements-dev.txt` present | `ls requirements*.txt` | 2 |
| C6 | `.claude/agents/` has connector-dev and connector-tester | `ls .claude/agents/` | 2 |
| C7 | `.claude/skills/` has test-and-fix-connector and validate-connector-auth | `ls .claude/skills/` | 2 |
| C8 | `.claude/commands/` has develop-connector and validate-connector | `ls .claude/commands/` | 1 |
| C9 | `pyproject.toml` has testpaths and pythonpath configured | `grep testpaths pyproject.toml` | 2 |

---

## Section D — Security (max 20)

| # | Check | How | Points |
|---|-------|-----|--------|
| D1 | No hardcoded JWT tokens (eyJ...) in source | `grep -r "eyJ" connector/ tests/ --include="*.py" \| grep -v stub` must be empty | BLOCKER |
| D2 | No hardcoded passwords or secrets | `grep -ri "password.*=" connector/ --include="*.py"` — only test stubs | MAJOR |
| D3 | `dev_config.json` in `.gitignore` | `grep dev_config.json .gitignore` | 2 |
| D4 | `static_access_token` is Optional with no default | `grep static_access_token connector/models/config.py` shows `Optional[str] = None` | 3 |
| D5 | No `ssl_verify=False` or cert bypass | `grep -r "verify=False\|ssl_verify" connector/ --include="*.py"` must be empty | MAJOR |
| D6 | No `subprocess` or `eval` in connector code | `grep -r "subprocess\|eval(" connector/lakeflow/ --include="*.py"` must be empty | MAJOR |
| D7 | Stub azure.identity raises on instantiation (not silently succeeds) | `grep "raise RuntimeError" tests/stubs/azure/identity/__init__.py` | 2 |
| D8 | Corpus JSON has no real PII (real person names, real SSNs) | Review `connector/simulator/corpus/*.json` — synthetic data only | 3 |

---

## Section E — Consistency (max 10)

| # | Check | How | Points |
|---|-------|-----|--------|
| E1 | Tables in `TABLES` constant match those in test `replay_config` and corpus directory | Compare `AdmeOsduLakeflowConnect.TABLES` with `connector/simulator/corpus/` filenames | 3 |
| E2 | Schema field names in `_DOMAIN_SCHEMA` match `_flatten_record` output keys | Manual comparison | 3 |
| E3 | `connector_spec.yaml` params match `_build_runtime` option keys | Compare spec `parameters[].name` with `options[...]` calls in `adme_osdu.py` | 2 |
| E4 | `incremental_filter_template` uses `{watermark}` placeholder (not `{cursor}` etc.) | `grep incremental_filter_template connector/lakeflow/adme_osdu.py` | 2 |

---

## Output Format

```markdown
# ADME OSDU Connector Self-Review

## Results

| Section | Score | Max |
|---------|-------|-----|
| A Implementation | X | 30 |
| B Testing | X | 30 |
| C Artifacts | X | 20 |
| D Security | X | 20 |
| E Consistency | X | 10 |
| **Total** | **X** | **110** |

**Verdict: READY / ALMOST / NEEDS WORK / NOT READY**

## Findings

### BLOCKERS
- (none) / list

### MAJOR
- (none) / list

### MINOR
- (none) / list
```
