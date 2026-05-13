#!/usr/bin/env bash
# ============================================================================
# CI Pre-Step: Federated Token Authentication for ADME Connector
# ============================================================================
#
# This script demonstrates the ZERO-CODE-CHANGE approach:
#   1. Authenticate using a federated token (OIDC) via az login
#   2. Mint a bearer token for the ADME API scope
#   3. Pass it to the connector as static_access_token
#
# Works with: GitHub Actions OIDC, Azure DevOps Workload Identity, any OIDC IdP
# ============================================================================

set -euo pipefail

# --- Configuration (set these in CI environment variables) ---
TENANT_ID="${AZURE_TENANT_ID:?'Set AZURE_TENANT_ID'}"
SP_CLIENT_ID="${AZURE_CLIENT_ID:?'Set AZURE_CLIENT_ID (Service Principal app ID)'}"
ADME_API_CLIENT_ID="${ADME_API_CLIENT_ID:?'Set ADME_API_CLIENT_ID'}"

# ============================================================================
# OPTION A: Use az login --federated-token (simplest, recommended)
# The OIDC token is provided by the CI platform (e.g., ACTIONS_ID_TOKEN_REQUEST_URL)
# ============================================================================

echo "▶ Step 1: Login with federated identity (OIDC)"
# In GitHub Actions, the token is automatically available:
#   FEDERATED_TOKEN=$(curl -sS "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=api://AzureADTokenExchange" \
#                     -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" | jq -r '.value')
#
# In Azure DevOps with Workload Identity:
#   FEDERATED_TOKEN is set by the service connection

az login --service-principal \
  --tenant "${TENANT_ID}" \
  --username "${SP_CLIENT_ID}" \
  --federated-token "${FEDERATED_TOKEN:?'Federated token not available'}" \
  --output none

echo "▶ Step 2: Mint bearer token for ADME API scope"
ADME_BEARER=$(az account get-access-token \
  --resource "api://${ADME_API_CLIENT_ID}" \
  --query accessToken --output tsv)

echo "▶ Step 3: Export for connector"
export CONNECTOR_AUTH_MODE="static_token"
export CONNECTOR_STATIC_ACCESS_TOKEN="${ADME_BEARER}"

echo "✓ Bearer token acquired (expires in ~1hr)"
echo "  Token prefix: ${ADME_BEARER:0:20}..."

# ============================================================================
# OPTION B: Write connector_runtime.yaml override
# ============================================================================

cat > /tmp/connector_auth_override.yaml <<EOF
auth:
  mode: static_token
  tenant_id: ${TENANT_ID}
  adme_api_client_id: ${ADME_API_CLIENT_ID}
  static_access_token: ${ADME_BEARER}
EOF

echo "▶ Step 4: Run connector smoke test"
# python -m connector.cli smoke-test --config /tmp/connector_auth_override.yaml

echo "============================================================"
echo "DONE — Federated token → static bearer → connector"
echo "Zero code changes required."
echo "============================================================"
