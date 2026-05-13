---
name: authenticate-source
description: Set up authentication for the ADME OSDU connector — get an Azure bearer token and write dev_config.json for live testing.
---

# Authenticate Source (ADME)

## Goal

Produce a valid `tests/unit/adme_osdu/dev_config.json` that the live-mode tests can use.

## ADME Auth Details

| Field | Value |
|-------|-------|
| Tenant ID | `72f988bf-86f1-41af-91ab-2d7cd011db47` |
| ADME API Client ID (resource) | `e37a6c70-7cbc-4593-80fc-01c1f20203f7` |
| Token scope | `api://e37a6c70-7cbc-4593-80fc-01c1f20203f7/.default` |
| Sandbox base URL | `https://admesbxscusins1.energy.azure.com` |
| Data partition | `opendes` |

---

## Step 1 — Check existing config

```bash
cat tests/unit/adme_osdu/dev_config.json 2>/dev/null && echo "config exists"
```

If present and token not expired, skip to Step 3.

---

## Step 2 — Get a token

**Option A: az CLI (interactive, may need browser)**

```bash
# Login to ADME tenant if not already
az login --tenant 72f988bf-86f1-41af-91ab-2d7cd011db47

# Get token
TOKEN=$(az account get-access-token \
  --resource "api://e37a6c70-7cbc-4593-80fc-01c1f20203f7" \
  --tenant "72f988bf-86f1-41af-91ab-2d7cd011db47" \
  --query accessToken -o tsv)

echo "Token length: ${#TOKEN}"
```

**Option B: From Databricks workspace (Managed Identity on cluster)**

If running on the Databricks cluster that has `adme-adb-sbx-scus-mi` attached:
```python
from azure.identity import ManagedIdentityCredential
cred = ManagedIdentityCredential(client_id="4841d326-e982-4898-813f-cb34f960ca1a")
token = cred.get_token("api://e37a6c70-7cbc-4593-80fc-01c1f20203f7/.default").token
```

---

## Step 3 — Write dev_config.json

```bash
cat > tests/unit/adme_osdu/dev_config.json << EOF
{
  "base_url": "https://admesbxscusins1.energy.azure.com",
  "data_partition_id": "opendes",
  "tenant_id": "72f988bf-86f1-41af-91ab-2d7cd011db47",
  "adme_api_client_id": "e37a6c70-7cbc-4593-80fc-01c1f20203f7",
  "access_token": "$TOKEN"
}
EOF
```

> `dev_config.json` is gitignored — never commit tokens.

---

## Step 4 — Validate auth

Run the validate-connector-auth skill or quick smoke check:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "data-partition-id: opendes" \
  "https://admesbxscusins1.energy.azure.com/api/entitlements/v2/groups"
```

Expected: `200`. Then run `/validate-connector-auth` for full connector-level check.

---

## Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| `AADSTS53003` Conditional Access | Local machine not compliant | `az login --tenant 72f988bf...` via browser |
| `AADSTS700016` App not found | Wrong tenant | Confirm `--tenant 72f988bf-86f1-41af-91ab-2d7cd011db47` |
| `401` from ADME | Token for wrong resource | Use `api://e37a6c70-7cbc-4593-80fc-01c1f20203f7` as resource |
| Token expires in < 5 min | CLI cached expired token | `az account get-access-token --resource ... --tenant ...` re-authenticates |
