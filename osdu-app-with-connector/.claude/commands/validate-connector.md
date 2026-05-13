# `/validate-connector`

Phase 2 workflow: authenticate against real ADME, run live tests, re-seed corpus with real data.

## Prerequisites

Phase 1 must be complete:
- `connector/lakeflow/adme_osdu.py` exists
- `tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py` exists
- Simulate-mode tests pass (`pytest tests/unit/adme_osdu/ -v`)

## Steps

### 1. Authenticate
Run `/authenticate-source` or manually:
```bash
TOKEN=$(az account get-access-token \
  --resource "api://e37a6c70-7cbc-4593-80fc-01c1f20203f7" \
  --tenant "72f988bf-86f1-41af-91ab-2d7cd011db47" \
  --query accessToken -o tsv)
```

If blocked by Conditional Access:
```bash
az login --tenant 72f988bf-86f1-41af-91ab-2d7cd011db47
```

### 2. Create dev_config.json
```bash
cat > tests/unit/adme_osdu/dev_config.json << EOF
{
  "base_url": "https://admesbxscusins1.energy.azure.com",
  "data_partition_id": "opendes",
  "access_token": "$TOKEN"
}
EOF
```

Or use env var:
```bash
export CONNECTOR_TEST_CONFIG_JSON='{"base_url":"https://admesbxscusins1.energy.azure.com","data_partition_id":"opendes","access_token":"<token>"}'
```

### 3. Validate auth
Run `connector-auth-validator` agent or:
```bash
PYTHONPATH=. python -c "
from connector.lakeflow.adme_osdu import AdmeOsduLakeflowConnect
import json, os
cfg = json.loads(os.environ['CONNECTOR_TEST_CONFIG_JSON'])
c = AdmeOsduLakeflowConnect(cfg)
recs, _ = c.read_table('entitlements', None, {})
print('auth ok:', len(list(recs)), 'groups')
"
```

### 4. Run live tests
```bash
CONNECTOR_TEST_MODE=live \
  PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest tests/unit/adme_osdu/ -v
```

### 5. Re-seed corpus (if live data differs from synthetic)
If live responses reveal different record shapes or field values, update `connector/simulator/corpus/*.json` with real records (anonymised if needed), then re-run simulate tests to confirm they still pass.

### 6. Final simulate pass
```bash
PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest tests/unit/adme_osdu/ -v
```

All tests green in both modes = validation complete.
