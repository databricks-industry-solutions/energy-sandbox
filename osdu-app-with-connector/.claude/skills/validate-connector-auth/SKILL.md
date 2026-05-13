---
name: validate-connector-auth
description: Validate that credentials for the ADME OSDU connector authenticate successfully against the real ADME API.
---

# Validate Connector Auth

## Goal

Confirm that a bearer token (or other credential) can reach the ADME sandbox and return data from at least one endpoint.

## Prerequisites

- Python environment with connector installed (`PYTHONPATH=.`)
- Bearer token in `CONNECTOR_TEST_CONFIG_JSON`, `CONNECTOR_TEST_CONFIG_PATH`, or `tests/unit/adme_osdu/dev_config.json`
- Network access to `https://admesbxscusins1.energy.azure.com`

---

## Step 1 — Check token exists

```bash
cat tests/unit/adme_osdu/dev_config.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('token length:', len(d.get('access_token','')))"
```

If missing, get one:
```bash
az login --tenant 72f988bf-86f1-41af-91ab-2d7cd011db47
TOKEN=$(az account get-access-token --resource "api://e37a6c70-7cbc-4593-80fc-01c1f20203f7" --tenant "72f988bf-86f1-41af-91ab-2d7cd011db47" --query accessToken -o tsv)
```

---

## Step 2 — Smoke test with curl

```bash
TOKEN=$(cat tests/unit/adme_osdu/dev_config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "data-partition-id: opendes" \
  "https://admesbxscusins1.energy.azure.com/api/entitlements/v2/groups"
```

Expected: `200`. If `401` → token invalid or expired. If `403` → token valid but missing entitlements. If `000` → network not reachable.

---

## Step 3 — Validate via connector

```python
import json, sys
sys.path.insert(0, '.')
sys.path.insert(0, 'tests/stubs')

with open('tests/unit/adme_osdu/dev_config.json') as f:
    opts = json.load(f)

from connector.lakeflow.adme_osdu import AdmeOsduLakeflowConnect
c = AdmeOsduLakeflowConnect(opts)

# Snapshot table — quick, no pagination
recs, offset = c.read_table('entitlements', None, {})
groups = list(recs)
assert len(groups) > 0, "No groups returned — auth may be invalid"
assert offset is None, "Entitlements should return no offset (snapshot)"
print(f"✅ Auth valid — {len(groups)} entitlement groups returned")
```

---

## Pass Criteria

| Check | Expected |
|-------|----------|
| HTTP status from entitlements endpoint | 200 |
| At least 1 group returned | ✅ |
| `data-partition-id` header accepted | No 400 |
| Token expiry > 5 min | ✅ (warn if < 10 min) |

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Token expired or wrong resource | Re-run `az account get-access-token` |
| `403 Forbidden` | Token valid, missing `users.datalake.ops@opendes.contoso.com` group | Contact ADME admin |
| `AADSTS53003` | Conditional Access blocks local token | `az login --tenant 72f988bf...` interactively |
| Connection refused | Network restriction | Must have access to `*.energy.azure.com` |
