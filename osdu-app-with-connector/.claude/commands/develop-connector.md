# `/develop-connector`

Phase 1 workflow: implement or update the ADME OSDU connector and validate in simulate mode. No credentials required.

## Steps (run sequentially, each must complete before the next)

### 1. Understand the change
- Read `connector/lakeflow/adme_osdu.py` and `connector/lakeflow/interface.py`
- Read `connector/simulator/corpus/` to understand current fixture data
- Read `tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py` for expected behaviour

### 2. Implement
- Modify `connector/lakeflow/adme_osdu.py` with the required change
- If adding tables: add schema, metadata, and `read_table` routing
- If changing HTTP behaviour: update `connector/simulator/http_mock.py` routes
- Update `connector_spec.yaml` if connection parameters change

### 3. Update corpus (if needed)
- If new tables or changed record structure: update or add JSON in `connector/simulator/corpus/`
- Corpus format for domain tables: plain JSON array of OSDU records
- Corpus format for legal_tags: `{"legalTags": [...], "totalCount": N}`
- Corpus format for entitlements: `{"groups": [...], "desId": "...", "memberEmail": "..."}`

### 4. Run simulate-mode tests
```bash
PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest tests/unit/adme_osdu/ -v
```

Fix all failures before proceeding. Reference `connector-tester` agent for fix priority order.

### 5. Gate check
All 18+ tests must be green. If any fail, loop back to step 2/3.

### 6. Done
Report what changed and note that live validation requires `/validate-connector`.
