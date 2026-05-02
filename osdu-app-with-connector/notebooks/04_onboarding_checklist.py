# Databricks notebook source
# MAGIC %md
# MAGIC # ADME / OSDU Connector — Onboarding Checklist
# MAGIC
# MAGIC **Purpose** — Collect and validate the four prerequisites you need before running the connector.
# MAGIC Hand this notebook to your colleague or customer so they can fill in values,
# MAGIC run the cells, and confirm readiness **before** touching `00_smoke_test` or any pipeline notebook.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What you need (overview)
# MAGIC
# MAGIC | # | Prerequisite | Why |
# MAGIC |---|-------------|-----|
# MAGIC | 1 | **ADME instance base URL** | Every API call targets this endpoint |
# MAGIC | 2 | **Azure Entra ID authentication** | The connector must prove identity to ADME |
# MAGIC | 3 | **Data partition ID** | ADME routes requests by partition; wrong value → 403 |
# MAGIC | 4 | **ADME API permissions (entitlements)** | Even a valid token is rejected without the right ADME roles |
# MAGIC
# MAGIC After filling in each section, run the **validation cell** at the bottom to confirm connectivity end-to-end.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 1) ADME Instance Base URL
# MAGIC
# MAGIC This is the root URL of your Azure Data Manager for Energy instance.
# MAGIC
# MAGIC **How to find it:**
# MAGIC - Azure Portal → your ADME resource → **Overview** → **URI** field
# MAGIC - It looks like: `https://<your-instance-name>.energy.azure.com`
# MAGIC
# MAGIC **Example (Microsoft sandbox):** `https://admesbxscusins1.energy.azure.com`
# MAGIC
# MAGIC > If the URL ends in `/` remove the trailing slash.

# COMMAND ----------

# --- FILL IN ---
ADME_BASE_URL = ""  # e.g. "https://admesbxscusins1.energy.azure.com"

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 2) Azure Entra ID Authentication
# MAGIC
# MAGIC The connector needs a bearer token scoped to `api://<ADME_API_CLIENT_ID>/.default`.
# MAGIC Choose **one** of three modes:
# MAGIC
# MAGIC ### Option A — Managed Identity (recommended for Databricks on Azure)
# MAGIC
# MAGIC Best when your Databricks cluster runs in the **same tenant** as ADME.
# MAGIC The cluster's system-assigned or user-assigned managed identity acquires a token automatically — no secrets to rotate.
# MAGIC
# MAGIC | Field | Where to find it |
# MAGIC |-------|-----------------|
# MAGIC | `TENANT_ID` | Azure Portal → Entra ID → Overview → **Tenant ID** |
# MAGIC | `ADME_API_CLIENT_ID` | Azure Portal → ADME resource → **Authentication** → **Application (client) ID** of the ADME API app registration |
# MAGIC | `MANAGED_IDENTITY_CLIENT_ID` | Only if using a **user-assigned** MI. Azure Portal → Managed Identities → your MI → **Client ID**. Leave blank for system-assigned. |
# MAGIC
# MAGIC ### Option B — Service Principal (client_id + secret)
# MAGIC
# MAGIC Use when the cluster does not have a managed identity or for cross-tenant access.
# MAGIC
# MAGIC | Field | Where to find it |
# MAGIC |-------|-----------------|
# MAGIC | `TENANT_ID` | Same as above |
# MAGIC | `ADME_API_CLIENT_ID` | Same as above |
# MAGIC | `SP_CLIENT_ID` | Azure Portal → App Registrations → your SP → **Application (client) ID** |
# MAGIC | `SP_CLIENT_SECRET` | The secret value (store in a **Databricks secret scope**, not plain text in production) |
# MAGIC
# MAGIC ### Option C — Static Bearer Token (testing only)
# MAGIC
# MAGIC Paste a token you obtained manually (e.g. from `az account get-access-token`).
# MAGIC Tokens expire (typically 60–90 min), so this is only for quick validation.
# MAGIC
# MAGIC | Field | How to get it |
# MAGIC |-------|--------------|
# MAGIC | `STATIC_TOKEN` | `az account get-access-token --resource api://<ADME_API_CLIENT_ID> --query accessToken -o tsv` |

# COMMAND ----------

# --- FILL IN (choose one mode) ---
AUTH_MODE = "managed_identity"  # "managed_identity" | "service_principal" | "static_token"

TENANT_ID            = ""  # e.g. "72f988bf-86f1-41af-91ab-2d7cd011db47"
ADME_API_CLIENT_ID   = ""  # e.g. "e37a6c70-7cbc-4593-80fc-01c1f20203f7"

# Option A fields
MANAGED_IDENTITY_CLIENT_ID = ""  # blank = system-assigned

# Option B fields (store secret in Databricks secrets, not here)
SP_CLIENT_ID         = ""
SP_CLIENT_SECRET     = ""  # dbutils.secrets.get(scope="adme", key="sp-secret")

# Option C field
STATIC_TOKEN         = ""

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Cross-Tenant Setup (Databricks in Tenant A, ADME in Tenant B)
# MAGIC
# MAGIC **This is the most common production scenario.** Your Databricks workspace lives in one Azure tenant
# MAGIC (e.g. your company's "Databricks Dev" tenant) and the ADME instance lives in another tenant
# MAGIC (e.g. customer's or a shared "Energy" tenant). Managed identity **will not work** across tenants —
# MAGIC you'll get `AADSTS500011: The resource principal was not found in the tenant`.
# MAGIC
# MAGIC ### What you need: a Service Principal in the ADME tenant
# MAGIC
# MAGIC **Step 1 — Create the SP in the ADME tenant (done by ADME admin)**
# MAGIC
# MAGIC | Action | Where |
# MAGIC |--------|-------|
# MAGIC | Go to **Azure Portal → Entra ID** (in the ADME tenant) → **App Registrations** → **New registration** | |
# MAGIC | Name it something like `databricks-adme-connector` | |
# MAGIC | Under **Certificates & secrets** → **New client secret** → copy the **Value** immediately | |
# MAGIC | Copy the **Application (client) ID** from the Overview page | |
# MAGIC | The **Tenant ID** is on the same Overview page (this is the ADME tenant ID) | |
# MAGIC
# MAGIC **Step 2 — Grant ADME entitlements to the SP (done by ADME admin)**
# MAGIC
# MAGIC The SP needs to be added to ADME's entitlement groups. Use the Entitlements API or ask the ADME admin:
# MAGIC
# MAGIC ```
# MAGIC POST {ADME_BASE_URL}/api/entitlements/v2/groups/users.datalake.viewers@{partition}.dataservices.energy/members
# MAGIC Headers: Authorization: Bearer <admin-token>, data-partition-id: <partition>
# MAGIC Body: { "email": "<SP_CLIENT_ID>", "role": "MEMBER" }
# MAGIC ```
# MAGIC
# MAGIC Repeat for these groups (minimum for read + governance):
# MAGIC - `users.datalake.viewers@{partition}.dataservices.energy`
# MAGIC - `service.search.user@{partition}.dataservices.energy`
# MAGIC - `service.legal.user@{partition}.dataservices.energy`
# MAGIC - `service.entitlements.user@{partition}.dataservices.energy`
# MAGIC
# MAGIC **Step 3 — Collect these 3 values from the ADME admin**
# MAGIC
# MAGIC | Value | Example | You fill in |
# MAGIC |-------|---------|-------------|
# MAGIC | `SP_CLIENT_ID` | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` | __________ |
# MAGIC | `SP_CLIENT_SECRET` | `xYz...secret...` (store in Databricks Secret Scope!) | __________ |
# MAGIC | `TENANT_ID` (ADME tenant) | `72f988bf-86f1-41af-91ab-2d7cd011db47` | __________ |
# MAGIC
# MAGIC **Step 4 — Configure the connector**
# MAGIC
# MAGIC Set `AUTH_MODE = "service_principal"` in the cell above and fill in `SP_CLIENT_ID`, `SP_CLIENT_SECRET`,
# MAGIC and `TENANT_ID` (must be the ADME tenant ID, not your Databricks tenant).
# MAGIC
# MAGIC **Step 5 — Store the secret securely (production)**
# MAGIC
# MAGIC ```python
# MAGIC # Create a secret scope (one-time, from a notebook or CLI):
# MAGIC # databricks secrets create-scope adme
# MAGIC # databricks secrets put-secret adme sp-secret --string-value "<YOUR-SECRET>"
# MAGIC
# MAGIC # Then in the config cell above, replace the plaintext with:
# MAGIC SP_CLIENT_SECRET = dbutils.secrets.get(scope="adme", key="sp-secret")
# MAGIC ```
# MAGIC
# MAGIC > **Why managed identity fails cross-tenant:** Azure MI tokens are scoped to the local tenant.
# MAGIC > When Databricks is in Tenant A and ADME's API app registration is in Tenant B,
# MAGIC > Tenant A's MI cannot request a token for `api://<app-in-tenant-B>/.default`.
# MAGIC > A service principal registered in Tenant B solves this.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 3) Data Partition ID
# MAGIC
# MAGIC Every ADME/OSDU API request requires a `data-partition-id` header.
# MAGIC
# MAGIC **How to find it:**
# MAGIC - Azure Portal → ADME resource → **Data Partitions** blade → copy the partition name
# MAGIC - The default for Microsoft trial/sandbox instances is usually `opendes`
# MAGIC - Production instances may use a company-specific name (e.g. `contoso-energy`)
# MAGIC
# MAGIC **What happens if it is wrong:** You will get `403 Forbidden` or `404 Not Found` even with a valid token.

# COMMAND ----------

# --- FILL IN ---
DATA_PARTITION_ID = ""  # e.g. "opendes"

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 4) ADME API Permissions (Entitlements)
# MAGIC
# MAGIC A valid Entra token alone is not enough — ADME maintains its **own** entitlement groups.
# MAGIC The identity (MI, SP, or user) must be a member of the right groups in the target partition.
# MAGIC
# MAGIC ### Minimum required groups
# MAGIC
# MAGIC | Group pattern | Purpose |
# MAGIC |--------------|---------|
# MAGIC | `users.datalake.viewers@<partition>.<domain>` | **Read** search results, records, schemas |
# MAGIC | `users.datalake.editors@<partition>.<domain>` | **Write** records (only if the connector ever writes back) |
# MAGIC | `service.search.user@<partition>.<domain>` | Call the **Search** API |
# MAGIC | `service.legal.user@<partition>.<domain>` | Call the **Legal** API (governance sync) |
# MAGIC | `service.entitlements.user@<partition>.<domain>` | Call the **Entitlements** API (governance sync) |
# MAGIC | `service.storage.user@<partition>.<domain>` | Call the **Storage/File** API (Phase 2 file downloads) |
# MAGIC
# MAGIC **How to check / grant:**
# MAGIC 1. Call the ADME Entitlements API:
# MAGIC    `GET {base_url}/api/entitlements/v2/groups`
# MAGIC    with header `data-partition-id: <partition>` and a valid bearer token.
# MAGIC 2. Or ask your ADME admin to add the identity to the groups above via the Entitlements API:
# MAGIC    `POST {base_url}/api/entitlements/v2/groups/{group}/members`
# MAGIC
# MAGIC > **Tip:** For a read-only connector, `users.datalake.viewers` + `service.search.user` are the
# MAGIC > minimum. Add the others when you enable governance sync or future write-back features.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Validation — test connectivity with the values above
# MAGIC
# MAGIC Run the cell below. It will:
# MAGIC 1. Check that all required fields are filled in
# MAGIC 2. Attempt to acquire a token (if not using static mode)
# MAGIC 3. Call the ADME **info/version** or **health** endpoint
# MAGIC 4. Call the **Search** API with a small test query
# MAGIC 5. Print a summary table with PASS / FAIL per step

# COMMAND ----------

# MAGIC %pip install -q 'httpx>=0.27' 'azure-identity>=1.15'

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# Re-import after restart — copy values from the cells above or use widgets
import os, json, httpx

ADME_BASE_URL              = getattr(__builtins__, "ADME_BASE_URL", "") or spark.conf.get("adme.onboard.base_url", "")
AUTH_MODE                  = getattr(__builtins__, "AUTH_MODE", "") or spark.conf.get("adme.onboard.auth_mode", "managed_identity")
TENANT_ID                  = getattr(__builtins__, "TENANT_ID", "") or spark.conf.get("adme.onboard.tenant_id", "")
ADME_API_CLIENT_ID         = getattr(__builtins__, "ADME_API_CLIENT_ID", "") or spark.conf.get("adme.onboard.adme_api_client_id", "")
MANAGED_IDENTITY_CLIENT_ID = getattr(__builtins__, "MANAGED_IDENTITY_CLIENT_ID", "") or spark.conf.get("adme.onboard.mi_client_id", "")
SP_CLIENT_ID               = getattr(__builtins__, "SP_CLIENT_ID", "") or spark.conf.get("adme.onboard.sp_client_id", "")
SP_CLIENT_SECRET           = getattr(__builtins__, "SP_CLIENT_SECRET", "") or spark.conf.get("adme.onboard.sp_client_secret", "")
STATIC_TOKEN               = getattr(__builtins__, "STATIC_TOKEN", "") or spark.conf.get("adme.onboard.static_token", "")
DATA_PARTITION_ID          = getattr(__builtins__, "DATA_PARTITION_ID", "") or spark.conf.get("adme.onboard.data_partition_id", "")

results = []

def record(step, passed, detail=""):
    results.append({"Step": step, "Result": "PASS" if passed else "FAIL", "Detail": detail})

# --- Step 1: required fields ---
missing = []
if not ADME_BASE_URL:     missing.append("ADME_BASE_URL")
if not DATA_PARTITION_ID: missing.append("DATA_PARTITION_ID")
if AUTH_MODE != "static_token":
    if not TENANT_ID:          missing.append("TENANT_ID")
    if not ADME_API_CLIENT_ID: missing.append("ADME_API_CLIENT_ID")
if AUTH_MODE == "service_principal":
    if not SP_CLIENT_ID:     missing.append("SP_CLIENT_ID")
    if not SP_CLIENT_SECRET: missing.append("SP_CLIENT_SECRET")
if AUTH_MODE == "static_token" and not STATIC_TOKEN:
    missing.append("STATIC_TOKEN")

record("Required fields", len(missing) == 0, f"Missing: {', '.join(missing)}" if missing else "All present")

# --- Step 2: acquire token ---
token = None
if not missing:
    try:
        if AUTH_MODE == "static_token":
            token = STATIC_TOKEN
            record("Token acquisition", True, "Using static token")
        else:
            from azure.identity import ManagedIdentityCredential, ClientSecretCredential
            scope = f"api://{ADME_API_CLIENT_ID}/.default"
            if AUTH_MODE == "managed_identity":
                kwargs = {}
                if MANAGED_IDENTITY_CLIENT_ID:
                    kwargs["client_id"] = MANAGED_IDENTITY_CLIENT_ID
                cred = ManagedIdentityCredential(**kwargs)
            else:
                cred = ClientSecretCredential(TENANT_ID, SP_CLIENT_ID, SP_CLIENT_SECRET)
            token = cred.get_token(scope).token
            record("Token acquisition", True, f"Got token ({len(token)} chars)")
    except Exception as e:
        record("Token acquisition", False, str(e)[:200])

# --- Step 3: ADME health / info ---
if token:
    headers = {"Authorization": f"Bearer {token}", "data-partition-id": DATA_PARTITION_ID}
    try:
        r = httpx.get(f"{ADME_BASE_URL.rstrip('/')}/api/search/v2/health", headers=headers, timeout=15)
        record("ADME health endpoint", r.status_code < 300, f"HTTP {r.status_code}")
    except Exception as e:
        try:
            r2 = httpx.get(f"{ADME_BASE_URL.rstrip('/')}/api/entitlements/v2/groups", headers=headers, timeout=15)
            record("ADME health endpoint", r2.status_code < 300, f"Entitlements fallback HTTP {r2.status_code}")
        except Exception as e2:
            record("ADME health endpoint", False, str(e2)[:200])

# --- Step 4: Search API test ---
if token:
    try:
        body = {"kind": "osdu:wks:master-data--Wellbore:*", "query": "", "limit": 1}
        r = httpx.post(
            f"{ADME_BASE_URL.rstrip('/')}/api/search/v2/query",
            headers={**headers, "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        if r.status_code < 300:
            data = r.json()
            count = data.get("totalCount", len(data.get("results", [])))
            record("Search API (wellbore)", True, f"HTTP {r.status_code}, totalCount={count}")
        else:
            record("Search API (wellbore)", False, f"HTTP {r.status_code}: {r.text[:150]}")
    except Exception as e:
        record("Search API (wellbore)", False, str(e)[:200])

# --- Print summary ---
print("\n" + "=" * 70)
print("  ONBOARDING VALIDATION SUMMARY")
print("=" * 70)
for r in results:
    icon = "OK" if r["Result"] == "PASS" else "XX"
    print(f"  [{icon}] {r['Step']:30s}  {r['Detail']}")
print("=" * 70)
all_pass = all(r["Result"] == "PASS" for r in results)
print(f"\n  {'ALL CHECKS PASSED — ready for 00_smoke_test!' if all_pass else 'SOME CHECKS FAILED — fix the items above before proceeding.'}\n")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Next steps
# MAGIC
# MAGIC Once all four checks show **PASS**:
# MAGIC
# MAGIC 1. Copy your values into `conf/connector_runtime.yaml` (use the example file as template).
# MAGIC 2. Run **`00_smoke_test`** — validates auth + API + one-page extract (no Delta writes).
# MAGIC 3. Run **`02_run_all_domains`** — full bronze / silver / checkpoint ingestion for Phase 1 domains.
# MAGIC 4. Run **`03_governance_sync`** — mirrors legal tags and entitlements into `gov_*` tables.
# MAGIC
# MAGIC ### Quick reference: connector_runtime.yaml mapping
# MAGIC
# MAGIC | This notebook field | YAML field |
# MAGIC |--------------------|-----------:|
# MAGIC | `ADME_BASE_URL` | `base_url` |
# MAGIC | `AUTH_MODE` | `auth.mode` |
# MAGIC | `TENANT_ID` | `auth.tenant_id` |
# MAGIC | `ADME_API_CLIENT_ID` | `auth.adme_api_client_id` |
# MAGIC | `MANAGED_IDENTITY_CLIENT_ID` | `auth.managed_identity_client_id` |
# MAGIC | `SP_CLIENT_ID` | `auth.service_principal_client_id` |
# MAGIC | `SP_CLIENT_SECRET` | `auth.service_principal_client_secret` |
# MAGIC | `DATA_PARTITION_ID` | `data_partition_id` |
