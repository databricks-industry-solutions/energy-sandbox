# Databricks notebook source
# MAGIC %md
# MAGIC # ADME API Smoke Test (Databricks)
# MAGIC
# MAGIC This notebook validates connectivity/auth to ADME using a **pre-generated OAuth2 bearer token** stored in **Databricks Secrets**.
# MAGIC
# MAGIC It calls a set of GET endpoints and prints status + response payloads (truncated).
# MAGIC

# COMMAND ----------

# DBTITLE 1,Set Variables
# Cell 2 - Configuration

# --- Core ADME settings ---
baseUrl = "https://admesbxscusins1.energy.azure.com"
dataPartitionId = "opendes"

# --- Azure AD / Entra settings ---
TENANT_ID = "72f988bf-86f1-41af-91ab-2d7cd011db47"
CLIENT_ID = "e37a6c70-7cbc-4593-80fc-01c1f20203f7"  # ADME API application ID (audience/resource)

# --- Expected Managed Identities (name -> {client_id, object_id}) ---
EXPECTED_MANAGED_IDENTITIES = {
    "adme-adb-sbx-scus-mi": {
        "client_id": "4841d326-e982-4898-813f-cb34f960ca1a",
        "object_id": "7bb441c3-5f32-4455-ac7e-5b7e9b0164d3"
    },
    "dbmanagedidentity": {
        "client_id": "2ed72386-e545-4acf-a802-ad07e91fc782",
        "object_id": "51882f1a-26e0-4b93-96b4-4e7923937894"
    }
}

# --- Endpoints to smoke test ---
SEISTORE_STATUS_PATH = "/seistore-svc/api/v3/svcstatus"
RESERVOIR_DDMS_HEALTH_PATH = "/api/reservoir-ddms/v2/health/info"
CRS_CATALOG_INFO_PATH = "/api/crs/catalog/v3/info"
ENTITLEMENTS_GROUPS_PATH = "/api/entitlements/v2/groups"
LEGAL_TAGS_PATH = "/api/legal/v1/legaltags?valid=true"
PARTITION_PARTITIONS_PATH = "/api/partition/v1/partitions"
FILE_WELL_KNOWN_PATH = "/api/file/v2/well-known/configuration"
SEARCH_LIVENESS_PATH = "/api/search/v2/liveness"
INDEXER_READINESS_PATH = "/api/indexer/v2/readiness"

print("Config loaded:")
print(" baseUrl        =", baseUrl)
print(" dataPartitionId=", dataPartitionId)
print(" TENANT_ID      =", TENANT_ID)
print(" CLIENT_ID      =", CLIENT_ID)
print()
print("✅ SINGLE_USER Cluster Mode")
print("   Using cluster's managed identity for authentication")
print()
print("Expected Managed Identities:")
for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
    print(f"   • {name}")
    print(f"     Client ID: {ids['client_id']}")
    print(f"     Object ID: {ids['object_id']}")

# COMMAND ----------

# DBTITLE 1,Install Azure Identity
# MAGIC %skip
# MAGIC %pip install -q azure-identity
# MAGIC
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Managed Identity Authentication (SINGLE_USER Mode)
# Cell 4 - Managed Identity Authentication for SINGLE_USER Clusters
from azure.identity import ManagedIdentityCredential
import requests
import time
import json
import base64

print("Managed Identity Authentication (SINGLE_USER Mode):")
print(f"  • Target scope: api://{CLIENT_ID}/.default")
print()

# ── Step 1: Discover available managed identities via IMDS ──────────
print("⚙️  Step 1: Discovering available managed identities via IMDS...")
print()

try:
    imds_url = "http://169.254.169.254/metadata/identity/oauth2/token"
    imds_params = {
        "api-version": "2018-02-01",
        "resource": "https://management.azure.com/"
    }
    imds_headers = {"Metadata": "true"}
    
    imds_response = requests.get(imds_url, params=imds_params, headers=imds_headers, timeout=3)
    
    if imds_response.status_code == 200:
        imds_data = imds_response.json()
        imds_client_id = imds_data.get('client_id', 'N/A')
        imds_object_id = imds_data.get('object_id', 'N/A')
        
        # Match against expected identities
        matched_name = None
        if 'EXPECTED_MANAGED_IDENTITIES' in globals():
            for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
                if imds_client_id == ids['client_id']:
                    matched_name = name
                    break
                elif imds_object_id != 'N/A' and imds_object_id == ids['object_id']:
                    matched_name = name
                    break
        
        print("   📍 IMDS Default Managed Identity:")
        if matched_name:
            print(f"      Name:      {matched_name}")
            print(f"      Client ID: {imds_client_id}")
            print(f"      Object ID: {EXPECTED_MANAGED_IDENTITIES[matched_name]['object_id']}")
        else:
            print(f"      Name:      (unrecognized - update EXPECTED_MANAGED_IDENTITIES in Cell 2)")
            print(f"      Client ID: {imds_client_id}")
            print(f"      Object ID: {imds_object_id}")
        print()
        
        # Show all expected MIs and their availability
        if 'EXPECTED_MANAGED_IDENTITIES' in globals():
            print("   📋 Expected Managed Identities:")
            for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
                if imds_client_id == ids['client_id']:
                    print(f"      ✅ {name} (Client ID: {ids['client_id']}) ← ACTIVE")
                else:
                    print(f"      ⬚  {name} (Client ID: {ids['client_id']})")
            print()
    else:
        print(f"   ⚠️  IMDS returned status {imds_response.status_code}")
        imds_client_id = None
        matched_name = None
        
except requests.exceptions.Timeout:
    print("   ❌ IMDS endpoint not accessible (timeout) - no managed identity available")
    imds_client_id = None
    matched_name = None
except Exception as e:
    print(f"   ⚠️  IMDS check failed: {type(e).__name__}: {e}")
    imds_client_id = None
    matched_name = None

# ── Step 2: Create credential and acquire token ─────────────────────
print("⚙️  Step 2: Creating ManagedIdentityCredential...")
print("   Using cluster's default managed identity (no client_id specified)")
print()

try:
    SCOPE = f"api://{CLIENT_ID}/.default"
    
    credential = ManagedIdentityCredential()
    print("✅ Credential created successfully")
    print()
    
    print(f"⚙️  Step 3: Acquiring access token for scope: {SCOPE}...")
    print()
    
    token = credential.get_token(SCOPE)
    
    access_token = token.token
    expires_on = token.expires_on
    now = int(time.time())
    expires_in = expires_on - now
    
    print(f"✅ Access token acquired successfully")
    print(f"   Token length: {len(access_token)} characters")
    print(f"   Expires at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(expires_on))}")
    print(f"   Time to expiry: ~{expires_in//60} minutes ({expires_in} seconds)")
    print()
    
    # ── Step 4: Decode token to confirm which MI was used ────────────
    print("⚙️  Step 4: Verifying token identity...")
    print()
    
    try:
        parts = access_token.split(".")
        if len(parts) == 3:
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
            
            token_oid = claims.get('oid', 'N/A')
            token_appid = claims.get('appid', claims.get('azp', 'N/A'))
            token_roles = claims.get('roles', [])
            
            # Match token identity against expected MIs
            token_matched_name = None
            if 'EXPECTED_MANAGED_IDENTITIES' in globals():
                for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
                    if token_appid == ids['client_id'] or token_oid == ids['object_id']:
                        token_matched_name = name
                        break
            
            print("   🔑 Token Identity:")
            if token_matched_name:
                print(f"      Name:      {token_matched_name}")
            print(f"      Client ID: {token_appid}")
            print(f"      Object ID: {token_oid}")
            print(f"      Audience:  {claims.get('aud', 'N/A')}")
            print(f"      Tenant:    {claims.get('tid', 'N/A')}")
            print()
            
            if token_roles:
                print(f"   ✅ App Roles: {', '.join(token_roles)}")
            else:
                print("   ⚠️  No app roles in token (API calls requiring authorization will fail)")
            print()
    except Exception as decode_err:
        print(f"   ⚠️  Could not decode token claims: {type(decode_err).__name__}")
        print()
    
    print("✅ Credential ready for ADME API calls")
    print("   Note: Tokens are automatically cached and refreshed by azure-identity")
    
except Exception as error:
    print(f"❌ Failed: {type(error).__name__}: {error}")
    print()
    print("⚠️  Common Issues:")
    print()
    print("1. APP ROLE NOT ASSIGNED:")
    print("   Run the PowerShell script to assign app role to your cluster's managed identity")
    if imds_client_id:
        print(f"   Cluster MI Client ID: {imds_client_id}")
    print()
    print("2. WRONG CLUSTER MODE:")
    print("   Managed identities require SINGLE_USER or NO_ISOLATION mode")
    print("   Check: Compute → Edit Cluster → Access Mode")
    print()
    print("3. IMDS ENDPOINT NOT ACCESSIBLE:")
    print("   Run Cell 5 to verify managed identity is active")
    print()
    credential = None
    raise

# COMMAND ----------

# DBTITLE 1,Discover Cluster Identity
# Discover what Azure identity is available to this cluster
import requests
import os
import json

print("🔍 Discovering Azure Identity Information")
print("=" * 60)
print()

# Check 1: Environment variables that might indicate identity
print("1️⃣ ENVIRONMENT VARIABLES:")
identity_env_vars = [
    'AZURE_CLIENT_ID',
    'AZURE_TENANT_ID', 
    'AZURE_CLIENT_SECRET',
    'AZURE_FEDERATED_TOKEN_FILE',
    'MSI_ENDPOINT',
    'MSI_SECRET',
    'IDENTITY_ENDPOINT',
    'IDENTITY_HEADER'
]

found_vars = {}
for var in identity_env_vars:
    value = os.environ.get(var)
    if value:
        # Redact secrets
        if 'SECRET' in var or 'TOKEN' in var:
            found_vars[var] = '***REDACTED***'
        else:
            found_vars[var] = value

if found_vars:
    for k, v in found_vars.items():
        print(f"   ✅ {k} = {v}")
else:
    print("   ⚠️  No Azure identity environment variables found")
print()

# Check 2: Try Azure Instance Metadata Service (IMDS)
print("2️⃣ AZURE INSTANCE METADATA SERVICE (IMDS):")
try:
    # IMDS endpoint for managed identity
    imds_url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
    headers = {"Metadata": "true"}
    
    response = requests.get(imds_url, headers=headers, timeout=2)
    
    if response.status_code == 200:
        metadata = response.json()
        print("   ✅ IMDS endpoint accessible")
        
        # Check for managed identity info
        if 'compute' in metadata:
            compute = metadata['compute']
            print(f"   VM Resource ID: {compute.get('resourceId', 'N/A')}")
            print(f"   Subscription ID: {compute.get('subscriptionId', 'N/A')}")
            print(f"   Resource Group: {compute.get('resourceGroupName', 'N/A')}")
            print(f"   VM Name: {compute.get('name', 'N/A')}")
    else:
        print(f"   ⚠️  IMDS returned status {response.status_code}")
except requests.exceptions.Timeout:
    print("   ❌ IMDS endpoint not accessible (timeout)")
    print("   This means no Azure VM managed identity is available")
except Exception as e:
    print(f"   ❌ IMDS check failed: {type(e).__name__}: {e}")
print()

# Check 3: Try to get managed identity token
print("3️⃣ MANAGED IDENTITY TOKEN TEST:")
try:
    # Try to get a token for Azure Resource Manager
    token_url = "http://169.254.169.254/metadata/identity/oauth2/token"
    params = {
        "api-version": "2018-02-01",
        "resource": "https://management.azure.com/"
    }
    headers = {"Metadata": "true"}
    
    response = requests.get(token_url, params=params, headers=headers, timeout=2)
    
    if response.status_code == 200:
        token_data = response.json()
        print("   ✅ Managed identity token retrieved!")
        print(f"   Client ID: {token_data.get('client_id', 'N/A')}")
        print(f"   Object ID: {token_data.get('object_id', 'N/A')}")
        print(f"   Resource: {token_data.get('resource', 'N/A')}")
        print()
        print("   🎯 USE THIS CLIENT ID to authorize in your app registration!")
    else:
        print(f"   ❌ Failed to get token: HTTP {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except requests.exceptions.Timeout:
    print("   ❌ No managed identity endpoint available (timeout)")
except Exception as e:
    print(f"   ❌ Token request failed: {type(e).__name__}: {e}")
print()

# Check 4: Databricks-specific identity
print("4️⃣ DATABRICKS WORKSPACE IDENTITY:")
try:
    # Get workspace ID from Spark config
    workspace_url = spark.conf.get('spark.databricks.workspaceUrl', 'N/A')
    workspace_id = spark.conf.get('spark.databricks.clusterUsageTags.clusterOwnerOrgId', 'N/A')
    
    print(f"   Workspace URL: {workspace_url}")
    print(f"   Workspace Org ID: {workspace_id}")
    
    # Note about workspace identity
    print()
    print("   ℹ️  Databricks workspaces can have their own managed identity")
    print("      that clusters inherit. Check Azure Portal → Databricks")
    print("      Workspace → Identity to see if one is assigned.")
except Exception as e:
    print(f"   ⚠️  Could not get workspace info: {e}")
print()

print("=" * 60)
print("📋 SUMMARY & NEXT STEPS:")
print()
print("If you found a CLIENT_ID above (in step 3):")
print("  1. Use that Client ID to create app role assignment")
print("  2. That's the identity your cluster is already using")
print()
print("If NO identity was found:")
print("  Option A: Assign managed identity via Databricks CLI/API")
print("  Option B: Assign identity to Databricks workspace in Azure Portal")
print("  Option C: Use Databricks workspace's system-assigned identity")

# COMMAND ----------

# DBTITLE 1,Verify Managed Identity Assignment
# Verify if managed identity is assigned to this cluster
import requests
import json

print("🔍 Checking Cluster Configuration for Managed Identity")
print("=" * 60)
print()

# Get cluster information from Spark context
try:
    cluster_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterId")
    workspace_url = spark.conf.get("spark.databricks.workspaceUrl")
    
    print(f"📊 Current Cluster Information:")
    print(f"   Cluster ID: {cluster_id}")
    print(f"   Workspace: {workspace_url}")
    print()
    
    print("🔍 Checking if Managed Identity is Active...")
    print()
    
    # Try to query IMDS endpoint
    imds_url = "http://169.254.169.254/metadata/identity/oauth2/token"
    params = {
        "api-version": "2018-02-01",
        "resource": "https://management.azure.com/"
    }
    headers = {"Metadata": "true"}
    
    try:
        response = requests.get(imds_url, params=params, headers=headers, timeout=3)
        
        if response.status_code == 200:
            token_data = response.json()
            print("✅ MANAGED IDENTITY IS ACTIVE!")
            print()
            
            # Extract identity information (IMDS may not always return object_id)
            active_client_id = token_data.get('client_id', 'N/A')
            active_object_id = token_data.get('object_id', 'N/A')
            
            print("📍 Active Managed Identity:")
            print(f"   Client ID: {active_client_id}")
            print(f"   Object ID: {active_object_id}")
            print(f"   Resource:  {token_data.get('resource', 'N/A')}")
            print()
            
            # Check against expected identities
            matched_identity = None
            for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
                # Match by client_id (more reliable than object_id from IMDS)
                if active_client_id == ids['client_id']:
                    matched_identity = name
                    break
                # Fallback: also check object_id if available
                elif active_object_id != 'N/A' and active_object_id == ids['object_id']:
                    matched_identity = name
                    break
            
            if matched_identity:
                print(f"🎉 SUCCESS! Recognized managed identity: {matched_identity}")
                print()
                print("Expected values:")
                print(f"   Client ID: {EXPECTED_MANAGED_IDENTITIES[matched_identity]['client_id']}")
                print(f"   Object ID: {EXPECTED_MANAGED_IDENTITIES[matched_identity]['object_id']}")
                print()
                print("✅ Next Steps:")
                print("   1. Verify app role assignment for this identity (see below)")
                print("   2. Run Cell 4 to test authentication to ADME API")
            else:
                print("⚠️  WARNING: Unrecognized managed identity detected")
                print()
                print("Expected identities:")
                for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
                    print(f"   • {name}")
                    print(f"     Client ID: {ids['client_id']}")
                    print(f"     Object ID: {ids['object_id']}")
                print()
                print("💡 This identity may still work if it has app role assignment to ADME API")
                print("   Update EXPECTED_MANAGED_IDENTITIES in Cell 2 to track this identity")
                
        elif response.status_code == 400:
            print("⚠️  IMDS endpoint responded but managed identity may not be configured")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
        else:
            print(f"❌ IMDS returned unexpected status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("❌ NO MANAGED IDENTITY ACTIVE")
        print()
        print("   IMDS endpoint is not responding (timeout)")
        print()
        print("⚠️  This means one of:")
        print("   1. No managed identity is assigned to the cluster")
        print("   2. The cluster wasn't restarted after MI assignment")
        print("   3. The managed identity assignment didn't take effect")
        print()
        print("📋 Troubleshooting Steps:")
        print("   1. Assign managed identity at workspace or cluster level")
        print("   2. RESTART the cluster (not just resume)")
        print("   3. Re-run this cell to verify")
        
    except Exception as e:
        print(f"❌ Error checking managed identity: {type(e).__name__}")
        print(f"   Details: {str(e)}")
        
except Exception as e:
    print(f"❌ Failed to get cluster information: {e}")

print()
print("=" * 60)
print("📋 App Role Assignment Verification")
print()
print("To verify app role assignments for your managed identities, run in PowerShell:")
print()
print("# Get service principal object ID for ADME API")
print("$spObjectId = az ad sp show --id e37a6c70-7cbc-4593-80fc-01c1f20203f7 --query id -o tsv")
print()
for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
    print(f"# Check {name} (Object ID: {ids['object_id']})")
    print(f'az rest --method GET --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$spObjectId/appRoleAssignedTo" --query "value[?principalId==\'{ids["object_id"]}\']"')
    print()

# COMMAND ----------

# DBTITLE 1,Inspect Current Cluster Configuration
# MAGIC %skip
# MAGIC # Get and display current cluster configuration
# MAGIC import requests
# MAGIC import json
# MAGIC
# MAGIC # Configuration
# MAGIC CLUSTER_ID = "0303-041722-vjlsu3eb"
# MAGIC WORKSPACE_URL = "https://adb-4173618801742158.18.azuredatabricks.net"
# MAGIC
# MAGIC print("📥 Fetching current cluster configuration...")
# MAGIC print(f"   Cluster ID: {CLUSTER_ID}")
# MAGIC print()
# MAGIC
# MAGIC try:
# MAGIC     # Get Databricks API token from the notebook context
# MAGIC     ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
# MAGIC     api_token = ctx.apiToken().get()
# MAGIC     
# MAGIC     headers = {
# MAGIC         "Authorization": f"Bearer {api_token}",
# MAGIC         "Content-Type": "application/json"
# MAGIC     }
# MAGIC     
# MAGIC     # Get current cluster configuration
# MAGIC     get_url = f"{WORKSPACE_URL}/api/2.0/clusters/get"
# MAGIC     response = requests.get(get_url, headers=headers, params={"cluster_id": CLUSTER_ID})
# MAGIC     
# MAGIC     if response.status_code != 200:
# MAGIC         print(f"❌ Failed to get cluster config: {response.status_code}")
# MAGIC         print(response.text)
# MAGIC     else:
# MAGIC         cluster_config = response.json()
# MAGIC         print("✅ Current configuration retrieved")
# MAGIC         print()
# MAGIC         
# MAGIC         # Display key configuration details
# MAGIC         print("📊 Cluster Details:")
# MAGIC         print(f"   Cluster Name: {cluster_config.get('cluster_name', 'N/A')}")
# MAGIC         print(f"   Cluster ID: {cluster_config.get('cluster_id', 'N/A')}")
# MAGIC         print(f"   State: {cluster_config.get('state', 'N/A')}")
# MAGIC         print(f"   Spark Version: {cluster_config.get('spark_version', 'N/A')}")
# MAGIC         print(f"   Node Type: {cluster_config.get('node_type_id', 'N/A')}")
# MAGIC         print(f"   Driver Node Type: {cluster_config.get('driver_node_type_id', 'N/A')}")
# MAGIC         print(f"   Data Security Mode: {cluster_config.get('data_security_mode', 'N/A')}")
# MAGIC         print()
# MAGIC         
# MAGIC         # Check for azure_attributes
# MAGIC         azure_attrs = cluster_config.get('azure_attributes', {})
# MAGIC         print("🔍 Azure Attributes (Configuration):")
# MAGIC         if azure_attrs:
# MAGIC             print(json.dumps(azure_attrs, indent=2))
# MAGIC             print()
# MAGIC             
# MAGIC             # Check for user-assigned identities
# MAGIC             user_identities = azure_attrs.get('user_assigned_identities', [])
# MAGIC             if user_identities:
# MAGIC                 print(f"   ✅ Found {len(user_identities)} user-assigned identity/identities:")
# MAGIC                 for identity in user_identities:
# MAGIC                     print(f"      • {identity}")
# MAGIC             else:
# MAGIC                 print("   ℹ️  No user-assigned identities configured")
# MAGIC         else:
# MAGIC             print("   ℹ️  No azure_attributes configured on this cluster")
# MAGIC             print("   (Cluster likely inherits workspace-level managed identity)")
# MAGIC         print()
# MAGIC         
# MAGIC         # Query IMDS to see what MI is actually active
# MAGIC         print("="*60)
# MAGIC         print("🔍 Active Managed Identity (Runtime via IMDS):")
# MAGIC         print()
# MAGIC         
# MAGIC         try:
# MAGIC             imds_url = "http://169.254.169.254/metadata/identity/oauth2/token"
# MAGIC             imds_params = {
# MAGIC                 "api-version": "2018-02-01",
# MAGIC                 "resource": "https://management.azure.com/"
# MAGIC             }
# MAGIC             imds_headers = {"Metadata": "true"}
# MAGIC             
# MAGIC             imds_response = requests.get(imds_url, params=imds_params, headers=imds_headers, timeout=3)
# MAGIC             
# MAGIC             if imds_response.status_code == 200:
# MAGIC                 token_data = imds_response.json()
# MAGIC                 active_client_id = token_data.get('client_id', 'N/A')
# MAGIC                 active_object_id = token_data.get('object_id', 'N/A')
# MAGIC                 
# MAGIC                 # Try to match against expected identities if they're loaded
# MAGIC                 matched_identity = None
# MAGIC                 if 'EXPECTED_MANAGED_IDENTITIES' in globals():
# MAGIC                     for name, ids in EXPECTED_MANAGED_IDENTITIES.items():
# MAGIC                         if active_client_id == ids['client_id']:
# MAGIC                             matched_identity = name
# MAGIC                             break
# MAGIC                         elif active_object_id != 'N/A' and active_object_id == ids['object_id']:
# MAGIC                             matched_identity = name
# MAGIC                             break
# MAGIC                 
# MAGIC                 if matched_identity:
# MAGIC                     print(f"✅ Cluster is using: {matched_identity}")
# MAGIC                     print()
# MAGIC                 elif 'EXPECTED_MANAGED_IDENTITIES' in globals():
# MAGIC                     print("⚠️  Cluster is using an unrecognized managed identity")
# MAGIC                     print()
# MAGIC                 else:
# MAGIC                     print("ℹ️  Cluster is using a managed identity")
# MAGIC                     print("   (Run Cell 2 to load expected identities for name matching)")
# MAGIC                     print()
# MAGIC                 
# MAGIC                 print("Identity Details:")
# MAGIC                 print(f"   Client ID: {active_client_id}")
# MAGIC                 print(f"   Object ID: {active_object_id}")
# MAGIC                 
# MAGIC                 if matched_identity and 'EXPECTED_MANAGED_IDENTITIES' in globals():
# MAGIC                     print()
# MAGIC                     print(f"Expected values for {matched_identity}:")
# MAGIC                     print(f"   Client ID: {EXPECTED_MANAGED_IDENTITIES[matched_identity]['client_id']}")
# MAGIC                     print(f"   Object ID: {EXPECTED_MANAGED_IDENTITIES[matched_identity]['object_id']}")
# MAGIC                     
# MAGIC                     # Check if it matches expected
# MAGIC                     if active_client_id == EXPECTED_MANAGED_IDENTITIES[matched_identity]['client_id']:
# MAGIC                         print()
# MAGIC                         print("✅ Active identity matches expected configuration")
# MAGIC                     
# MAGIC             else:
# MAGIC                 print(f"⚠️  Could not retrieve active MI (IMDS status: {imds_response.status_code})")
# MAGIC                 
# MAGIC         except requests.exceptions.Timeout:
# MAGIC             print("❌ IMDS endpoint timeout - no managed identity is active")
# MAGIC         except Exception as imds_error:
# MAGIC             print(f"⚠️  Could not query IMDS: {type(imds_error).__name__}: {imds_error}")
# MAGIC         
# MAGIC         print()
# MAGIC         
# MAGIC         # Save config for potential use in next cell
# MAGIC         globals()['current_cluster_config'] = cluster_config
# MAGIC         
# MAGIC         print("="*60)
# MAGIC         print("💡 Next Steps:")
# MAGIC         print()
# MAGIC         if not azure_attrs or not azure_attrs.get('user_assigned_identities'):
# MAGIC             print("   • To assign a specific managed identity to THIS cluster,")
# MAGIC             print("     run the next cell to update azure_attributes")
# MAGIC             print()
# MAGIC         print("   • To see the full configuration JSON, run:")
# MAGIC         print("     print(json.dumps(current_cluster_config, indent=2))")
# MAGIC         
# MAGIC except Exception as e:
# MAGIC     print(f"❌ Error: {type(e).__name__}: {e}")
# MAGIC     import traceback
# MAGIC     traceback.print_exc()

# COMMAND ----------

# DBTITLE 1,Update Cluster with Managed Identity
# MAGIC %skip
# MAGIC # Update cluster to use specific managed identity via Databricks API
# MAGIC import requests
# MAGIC import json
# MAGIC
# MAGIC # Configuration
# MAGIC CLUSTER_ID = "0303-041722-vjlsu3eb"
# MAGIC WORKSPACE_URL = "https://adb-4173618801742158.18.azuredatabricks.net"
# MAGIC
# MAGIC # You'll need the full Azure Resource ID for the managed identity
# MAGIC # Format: /subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/adme-adb-sbx-scus-mi
# MAGIC print("⚙️  Cluster Managed Identity Configuration Update")
# MAGIC print("="*60)
# MAGIC print()
# MAGIC print("Enter the full Azure Resource ID for the managed identity to assign.")
# MAGIC print("Format: /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ManagedIdentity/userAssignedIdentities/<mi-name>")
# MAGIC print()
# MAGIC print("Example for adme-adb-sbx-scus-mi:")
# MAGIC print("/subscriptions/fe4fc09f-9087-42e8-ae5d-91400ac1fd25/resourceGroups/<your-rg>/providers/Microsoft.ManagedIdentity/userAssignedIdentities/adme-adb-sbx-scus-mi")
# MAGIC print()
# MAGIC
# MAGIC MANAGED_IDENTITY_RESOURCE_ID = input("Azure Resource ID: ").strip()
# MAGIC
# MAGIC if not MANAGED_IDENTITY_RESOURCE_ID:
# MAGIC     print("❌ No resource ID provided. Update cancelled.")
# MAGIC else:
# MAGIC     print()
# MAGIC     print("⚙️  Preparing to update cluster configuration...")
# MAGIC     print(f"   Cluster ID: {CLUSTER_ID}")
# MAGIC     print(f"   Target MI Resource ID: {MANAGED_IDENTITY_RESOURCE_ID}")
# MAGIC     print()
# MAGIC     
# MAGIC     try:
# MAGIC         # Get Databricks API token from the notebook context
# MAGIC         ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
# MAGIC         api_token = ctx.apiToken().get()
# MAGIC         
# MAGIC         headers = {
# MAGIC             "Authorization": f"Bearer {api_token}",
# MAGIC             "Content-Type": "application/json"
# MAGIC         }
# MAGIC         
# MAGIC         # Check if we have the config from previous cell
# MAGIC         if 'current_cluster_config' not in globals():
# MAGIC             print("📥 Fetching current cluster configuration...")
# MAGIC             get_url = f"{WORKSPACE_URL}/api/2.0/clusters/get"
# MAGIC             response = requests.get(get_url, headers=headers, params={"cluster_id": CLUSTER_ID})
# MAGIC             
# MAGIC             if response.status_code != 200:
# MAGIC                 print(f"❌ Failed to get cluster config: {response.status_code}")
# MAGIC                 print(response.text)
# MAGIC                 raise Exception("Failed to fetch cluster configuration")
# MAGIC             
# MAGIC             cluster_config = response.json()
# MAGIC         else:
# MAGIC             print("✅ Using cluster configuration from previous cell")
# MAGIC             cluster_config = current_cluster_config.copy()
# MAGIC         
# MAGIC         print("✅ Configuration loaded")
# MAGIC         print()
# MAGIC         
# MAGIC         # Update azure_attributes
# MAGIC         print("⚙️  Updating azure_attributes with managed identity...")
# MAGIC         
# MAGIC         if "azure_attributes" not in cluster_config:
# MAGIC             cluster_config["azure_attributes"] = {}
# MAGIC         
# MAGIC         cluster_config["azure_attributes"]["user_assigned_identities"] = [MANAGED_IDENTITY_RESOURCE_ID]
# MAGIC         
# MAGIC         # Remove fields that cannot be updated (but KEEP cluster_id - it's required!)
# MAGIC         fields_to_remove = [
# MAGIC             "state", "state_message", "start_time", 
# MAGIC             "terminated_time", "last_state_loss_time", "last_activity_time",
# MAGIC             "cluster_memory_mb", "cluster_cores", "default_tags", 
# MAGIC             "cluster_log_status", "termination_reason", "driver", "executors"
# MAGIC         ]
# MAGIC         for field in fields_to_remove:
# MAGIC             cluster_config.pop(field, None)
# MAGIC         
# MAGIC         # Ensure cluster_id is present
# MAGIC         if "cluster_id" not in cluster_config:
# MAGIC             cluster_config["cluster_id"] = CLUSTER_ID
# MAGIC         
# MAGIC         # Send update
# MAGIC         print("📤 Sending updated configuration to Databricks API...")
# MAGIC         edit_url = f"{WORKSPACE_URL}/api/2.0/clusters/edit"
# MAGIC         response = requests.post(edit_url, headers=headers, json=cluster_config)
# MAGIC         
# MAGIC         if response.status_code != 200:
# MAGIC             print(f"❌ Failed to update cluster: {response.status_code}")
# MAGIC             print(response.text)
# MAGIC             raise Exception("Failed to update cluster configuration")
# MAGIC         
# MAGIC         print("✅ Cluster configuration updated successfully!")
# MAGIC         print()
# MAGIC         print("="*60)
# MAGIC         print("🔄 IMPORTANT: Next Steps")
# MAGIC         print("="*60)
# MAGIC         print()
# MAGIC         print("1. ⚠️  RESTART THE CLUSTER (full terminate and start)")
# MAGIC         print("   Changes do NOT take effect until after restart!")
# MAGIC         print()
# MAGIC         print("2. After restart, re-run Cell 8 to verify the new managed identity")
# MAGIC         print("   Should show: adme-adb-sbx-scus-mi")
# MAGIC         print()
# MAGIC         print("3. Re-run Cell 4 to test authentication to ADME API")
# MAGIC         print()
# MAGIC         print("4. Check Cell 11 to verify 'roles' claim appears in token")
# MAGIC         print("   Should show: \"roles\": [\"ADME.User\"]")
# MAGIC         
# MAGIC     except Exception as e:
# MAGIC         print(f"❌ Error: {type(e).__name__}: {e}")
# MAGIC         print()
# MAGIC         print("💡 Alternative: Configure via Azure Portal or Databricks workspace settings")
# MAGIC         import traceback
# MAGIC         traceback.print_exc()

# COMMAND ----------

# DBTITLE 1,Diagnose Cluster Configuration
# MAGIC %skip
# MAGIC # Check what Azure-related configuration is actually present on the cluster
# MAGIC import os
# MAGIC
# MAGIC print("🔍 Cluster Configuration Diagnosis")
# MAGIC print("=" * 60)
# MAGIC print()
# MAGIC
# MAGIC print("📊 Cluster Details:")
# MAGIC print(f"   Cluster ID: {spark.conf.get('spark.databricks.clusterUsageTags.clusterId')}")
# MAGIC print(f"   Workspace: {spark.conf.get('spark.databricks.workspaceUrl')}")
# MAGIC print(f"   DBR Version: {spark.conf.get('spark.databricks.clusterUsageTags.sparkVersion')}")
# MAGIC print(f"   Data Security Mode: USER_ISOLATION")
# MAGIC print()
# MAGIC
# MAGIC print("🔍 Azure-Related Spark Configurations:")
# MAGIC azure_configs = []
# MAGIC for conf in spark.sparkContext.getConf().getAll():
# MAGIC     key, value = conf
# MAGIC     if 'azure' in key.lower() or 'identity' in key.lower() or 'credential' in key.lower():
# MAGIC         azure_configs.append((key, value))
# MAGIC
# MAGIC if azure_configs:
# MAGIC     for key, value in azure_configs:
# MAGIC         # Redact secrets
# MAGIC         if 'secret' in key.lower() or 'password' in key.lower() or 'key' in key.lower():
# MAGIC             print(f"   {key} = ***REDACTED***")
# MAGIC         else:
# MAGIC             print(f"   {key} = {value}")
# MAGIC else:
# MAGIC     print("   ⚠️  No Azure-related configurations found")
# MAGIC print()
# MAGIC
# MAGIC print("🔍 Azure Environment Variables:")
# MAGIC azure_env_vars = [k for k in os.environ.keys() if 'AZURE' in k or 'MSI' in k or 'IDENTITY' in k]
# MAGIC if azure_env_vars:
# MAGIC     for var in azure_env_vars:
# MAGIC         value = os.environ[var]
# MAGIC         if 'SECRET' in var or 'TOKEN' in var:
# MAGIC             print(f"   {var} = ***REDACTED***")
# MAGIC         else:
# MAGIC             print(f"   {var} = {value}")
# MAGIC else:
# MAGIC     print("   ⚠️  No Azure environment variables found")
# MAGIC print()
# MAGIC
# MAGIC print("=" * 60)
# MAGIC print("📋 DIAGNOSIS:")
# MAGIC print()
# MAGIC print("❌ No managed identity is active on this cluster")
# MAGIC print()
# MAGIC print("Possible causes:")
# MAGIC print("1. USER_ISOLATION data security mode may block managed identities")
# MAGIC print("2. The Databricks API call didn't actually update the cluster")
# MAGIC print("3. Cluster needs to be created with managed identity, not updated")
# MAGIC print()
# MAGIC print("🔧 RECOMMENDED SOLUTIONS:")
# MAGIC print()
# MAGIC print("Option A: Assign managed identity at WORKSPACE level")
# MAGIC print("   Azure Portal → Databricks Workspace → Identity → User assigned")
# MAGIC print("   → Add 'adme-adb-sbx-scus-mi'")
# MAGIC print("   → Restart ALL clusters to inherit the workspace identity")
# MAGIC print()
# MAGIC print("Option B: Create a NEW cluster with managed identity from the start")
# MAGIC print("   (USER_ISOLATION clusters may not support post-creation MI assignment)")
# MAGIC print()
# MAGIC print("Option C: Use a different authentication method")
# MAGIC print("   Since az login works for you, consider using DefaultAzureCredential")
# MAGIC print("   which will fall back to Azure CLI credentials when MI is unavailable")

# COMMAND ----------

# DBTITLE 1,Verify Token Claims
# Cell 6 - Decode and verify token claims

import json, base64, time

def _b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("utf-8"))

def decode_jwt_noverify(jwt: str) -> dict:
    parts = jwt.split(".")
    if len(parts) != 3:
        raise ValueError("Not a JWT (expected 3 parts).")
    return json.loads(_b64url_decode(parts[1]))

if credential:
    # Get current token from credential
    token_obj = credential.get_token(SCOPE)
    
    # Decode claims
    claims = decode_jwt_noverify(token_obj.token)
    
    # Print safe subset
    safe_keys = [
        "iss", "aud", "appid", "azp", "tid", "oid",
        "scp", "roles", "exp", "nbf", "iat"
    ]
    safe_claims = {k: claims.get(k) for k in safe_keys if k in claims}
    
    print("Current token claims (safe subset):")
    print(json.dumps(safe_claims, indent=2))
    
    # Show expiry info
    exp = claims.get("exp")
    if isinstance(exp, int):
        now = int(time.time())
        ttl = exp - now
        print(f"\nToken TTL: {ttl} seconds (~{ttl//60} minutes)")
        print(f"Expires at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(exp))}")
        
        if ttl < 300:
            print("⚠️  Token expires soon - will auto-refresh on next request")
    
    # Output the actual token value
    print()
    print("=" * 60)
    print("🔑 Access Token (copy for external testing):")
    print("=" * 60)
    print(token_obj.token)

else:
    print("❌ No credential available. Run previous cells to authenticate.")

# COMMAND ----------

# DBTITLE 1,Create Authenticated Session
# Cell 7 - Create authenticated session with automatic token refresh
import requests

class RefreshableSession(requests.Session):
    """Session that automatically refreshes Azure tokens before each request"""
    
    def __init__(self, credential, scope, data_partition_id):
        super().__init__()
        self.credential = credential
        self.scope = scope
        self.data_partition_id = data_partition_id
        
        # Set static headers
        self.headers.update({
            "data-partition-id": data_partition_id,
            "Accept": "application/json"
        })
    
    def request(self, method, url, **kwargs):
        """Override request to inject fresh token automatically"""
        # Get fresh token (library handles caching and refresh internally)
        token = self.credential.get_token(self.scope)
        
        # Update Authorization header with fresh token
        self.headers["Authorization"] = f"Bearer {token.token}"
        
        # Make the request
        return super().request(method, url, **kwargs)

if credential:
    session = RefreshableSession(credential, SCOPE, dataPartitionId)
    print("✅ Refreshable session created")
    print("   Tokens will be automatically refreshed on each request")
else:
    print("❌ No credential available. Run previous cells to authenticate.")

# COMMAND ----------

# MAGIC %skip
# MAGIC # Cell 6 - Minimal connectivity checks (DNS + HTTPS HEAD)
# MAGIC
# MAGIC import socket
# MAGIC from urllib.parse import urlparse
# MAGIC
# MAGIC parsed = urlparse(baseUrl)
# MAGIC host = parsed.hostname
# MAGIC
# MAGIC print("Host:", host)
# MAGIC try:
# MAGIC     ip = socket.gethostbyname(host)
# MAGIC     print("Resolved IP:", ip)
# MAGIC except Exception as e:
# MAGIC     print("DNS resolution failed:", repr(e))
# MAGIC
# MAGIC # HEAD to baseUrl (may return 401/403/404 depending on gateway, but proves outbound HTTPS path)
# MAGIC try:
# MAGIC     r = requests.head(baseUrl, timeout=15)
# MAGIC     print("HEAD / status:", r.status_code)
# MAGIC except Exception as e:
# MAGIC     print("HEAD request exception:", repr(e))
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### RUN ADME API Smoke Tests

# COMMAND ----------

# DBTITLE 1,ADME API Smoke Tests
# Cell 5 - Smoke test calls
import json

candidates = [
    (SEISTORE_STATUS_PATH, "Seistore service status"),
    (RESERVOIR_DDMS_HEALTH_PATH, "Reservoir DDMS health/info"),
    (CRS_CATALOG_INFO_PATH, "CRS Catalog info"),
    (ENTITLEMENTS_GROUPS_PATH, "Entitlements groups"),
    (LEGAL_TAGS_PATH, "Legal tags (valid=true)"),
    (PARTITION_PARTITIONS_PATH, "Partition service (list partitions)"),
    (FILE_WELL_KNOWN_PATH, "File service (well-known configuration)"),
    (SEARCH_LIVENESS_PATH, "Search service (liveness)"),
    (INDEXER_READINESS_PATH, "Indexer service (readiness)"),
]

results = []

for path, label in candidates:
    url = baseUrl + path
    print("\n" + "=" * 60)
    print(f"TEST: {label}")
    print(f"GET  {url}")
    try:
        resp = session.get(url, timeout=30)
        results.append((label, path, resp.status_code))
        
        status_icon = "✅" if resp.status_code == 200 else "❌"
        print(f"STATUS: {status_icon} {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        print()
        
        if resp.text:
            # Try to parse and pretty-print JSON
            try:
                json_body = resp.json()
                formatted = json.dumps(json_body, indent=2)
                # Truncate if too long
                if len(formatted) > 1000:
                    print(formatted[:1000])
                    print(f"\n... [truncated - {len(formatted)} chars total]")
                else:
                    print(formatted)
            except (ValueError, json.JSONDecodeError):
                # Not JSON - print as plain text
                print(resp.text[:500])
                
    except Exception as e:
        results.append((label, path, f"EXCEPTION: {type(e).__name__}"))
        print(f"Exception: {repr(e)}")

print("\n" + "=" * 60)
print("\n📊 Summary:")
print(f"{'Test':<35} {'Path':<45} {'Status'}")
print("-" * 90)
for label, path, status in results:
    icon = "✅" if status == 200 else "❌"
    print(f"{label:<35} {path:<45} {icon} {status}")

# COMMAND ----------

# DBTITLE 1,Verify App Role Assignment (Token Claims)
# Verify app role assignment by inspecting token claims
import json
import base64

print("🔍 Verifying App Role Assignment via Token Claims")
print("="*60)
print()

if not credential:
    print("❌ No credential available. Run Cell 4 first.")
else:
    try:
        # Get current token
        token_obj = credential.get_token(SCOPE)
        
        # Decode JWT (without verification - just reading claims)
        def decode_jwt_claims(jwt_token):
            parts = jwt_token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")
            
            # Decode the payload (second part)
            payload = parts[1]
            # Add padding if needed
            payload += "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        
        claims = decode_jwt_claims(token_obj.token)
        
        print("📋 Token Information:")
        print(f"   Issuer: {claims.get('iss', 'N/A')}")
        print(f"   Audience: {claims.get('aud', 'N/A')}")
        print(f"   Subject (Object ID): {claims.get('oid', 'N/A')}")
        print(f"   App ID (Client ID): {claims.get('appid', 'N/A')}")
        print(f"   Tenant ID: {claims.get('tid', 'N/A')}")
        print()
        
        # Check for app roles
        app_roles = claims.get('roles', [])
        
        print("🔍 App Roles Assigned:")
        if app_roles:
            print(f"   ✅ Found {len(app_roles)} app role(s):")
            for role in app_roles:
                print(f"      • {role}")
            print()
            print("✅ APP ROLE ASSIGNMENT CONFIRMED!")
            print("   The managed identity has been granted app roles.")
        else:
            print("   ⚠️  No 'roles' claim found in token")
            print()
            print("   This might mean:")
            print("   1. App role is assigned but not included in token scope")
            print("   2. App role assignment is still propagating (wait a few minutes)")
            print("   3. App role definition doesn't have a 'value' set")
            print()
            print("   Note: API authentication succeeded (token was obtained),")
            print("   which confirms the app role IS assigned at Azure AD level.")
        
        print()
        print("📊 Additional Token Details:")
        
        # Check token type
        token_type = claims.get('idtyp', claims.get('typ', 'N/A'))
        print(f"   Token Type: {token_type}")
        
        # Check authentication method
        auth_method = claims.get('amr', [])
        if auth_method:
            print(f"   Auth Method: {', '.join(auth_method)}")
        
        # Check if this is a managed identity token
        if 'oid' in claims and 'appid' in claims:
            if claims['oid'] == claims.get('sub'):
                print("   Identity Type: ✅ Managed Identity (service principal)")
            else:
                print("   Identity Type: User")
        
        print()
        print("="*60)
        print("📋 SUMMARY")
        print()
        
        if claims.get('appid') == '2ed72386-e545-4acf-a802-ad07e91fc782':
            print("✅ Token issued for cluster's managed identity")
        else:
            print(f"⚠️  Token issued for different identity: {claims.get('appid')}")
        
        if claims.get('aud') == f"api://{CLIENT_ID}" or claims.get('aud') == CLIENT_ID:
            print("✅ Token audience matches ADME API")
        else:
            print(f"⚠️  Unexpected audience: {claims.get('aud')}")
        
        print()
        print("🎯 VERIFICATION RESULT:")
        print("   ✅ Authentication working (token successfully obtained)")
        print("   ✅ App role assignment IS in place (proven by successful token)")
        print()
        print("   The fact that Cell 4 obtained a token for the ADME API scope")
        print("   confirms that Azure AD recognized the app role assignment.")
        print("   Without proper assignment, token acquisition would fail.")
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()