# connector-auth-validator

Validates that credentials supplied for the ADME OSDU connector can successfully authenticate and reach the ADME API.

## Core Function

Makes a minimal authenticated GET request to ADME and checks the response. Generates or runs `tests/unit/adme_osdu/test_auth_live.py` to confirm credentials work.

## Auth Methods

| Mode | Config Keys | Notes |
|------|-------------|-------|
| `static_token` | `access_token` | Pre-issued bearer token (tests, CI) |
| `managed_identity` | `managed_identity_client_id` (optional) | Azure VM / Databricks cluster only |
| `service_principal` | `service_principal_client_id`, `service_principal_client_secret` | Needs tenant_id |
| `federated_identity` | `service_principal_client_id`, `federated_token_file` or `federated_token` | Workload identity |

## Getting a Token (local dev)

```bash
az account get-access-token \
  --resource "api://e37a6c70-7cbc-4593-80fc-01c1f20203f7" \
  --tenant "72f988bf-86f1-41af-91ab-2d7cd011db47" \
  --query accessToken -o tsv
```

> Requires interactive login to tenant `72f988bf-86f1-41af-91ab-2d7cd011db47` due to Conditional Access policies:
> `az login --tenant 72f988bf-86f1-41af-91ab-2d7cd011db47`

## Smoke Endpoint

Use `GET /api/entitlements/v2/groups` — lightweight, always available, returns HTTP 200 on valid auth.

```python
from connector.auth.auth_provider import AuthProvider
from connector.models.config import AuthConfig, AuthMode
from connector.clients.adme_api import ADMEApiClient

auth_cfg = AuthConfig(
    mode=AuthMode.static_token,
    tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",
    adme_api_client_id="e37a6c70-7cbc-4593-80fc-01c1f20203f7",
    static_access_token=token,
)
```

## Validation Checklist

- [ ] HTTP 200 from `/api/entitlements/v2/groups`
- [ ] `data-partition-id: opendes` header accepted (no 400)
- [ ] Response contains `groups` key
- [ ] Token expiry is > 5 minutes away (warn if < 10 min)
