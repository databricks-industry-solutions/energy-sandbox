#!/usr/bin/env python3
"""
Self-contained proof test for federated identity auth mode.
Mocks azure.identity so it can run without network dependencies.
"""
import sys
import os
import types
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Mock azure.identity and azure.core.credentials ---
class FakeAccessToken:
    def __init__(self, token, expires_on):
        self.token = token
        self.expires_on = expires_on


class FakeTokenCredential:
    pass


class FakeClientAssertionCredential(FakeTokenCredential):
    def __init__(self, tenant_id, client_id, func, **kwargs):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self._func = func

    def get_token(self, *scopes, **kwargs):
        assertion = self._func()
        return FakeAccessToken(f"exchanged-from:{assertion[:20]}", 9999999999)


class FakeClientSecretCredential(FakeTokenCredential):
    def __init__(self, tenant_id, client_id, client_secret, **kwargs):
        self.tenant_id = tenant_id
        self.client_id = client_id

    def get_token(self, *scopes, **kwargs):
        return FakeAccessToken("secret-token", 9999999999)


class FakeManagedIdentityCredential(FakeTokenCredential):
    def __init__(self, client_id=None, **kwargs):
        self.client_id = client_id

    def get_token(self, *scopes, **kwargs):
        return FakeAccessToken("mi-token", 9999999999)


# Wire up mock modules
azure_mod = types.ModuleType("azure")
azure_core_mod = types.ModuleType("azure.core")
azure_core_creds_mod = types.ModuleType("azure.core.credentials")
azure_core_creds_mod.AccessToken = FakeAccessToken
azure_core_creds_mod.TokenCredential = FakeTokenCredential
azure_identity_mod = types.ModuleType("azure.identity")
azure_identity_mod.ClientAssertionCredential = FakeClientAssertionCredential
azure_identity_mod.ClientSecretCredential = FakeClientSecretCredential
azure_identity_mod.ManagedIdentityCredential = FakeManagedIdentityCredential

sys.modules["azure"] = azure_mod
sys.modules["azure.core"] = azure_core_mod
sys.modules["azure.core.credentials"] = azure_core_creds_mod
sys.modules["azure.identity"] = azure_identity_mod

from connector.models.config import AuthConfig, AuthMode
from connector.auth.auth_provider import AuthProvider, build_credential

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
results = []


def assert_eq(label, actual, expected):
    if actual == expected:
        results.append((label, True))
        print(f"  {PASS} {label}")
    else:
        results.append((label, False))
        print(f"  {FAIL} {label}: expected {expected!r}, got {actual!r}")


def assert_raises(label, exc_type, match, fn):
    try:
        fn()
        results.append((label, False))
        print(f"  {FAIL} {label}: no exception raised")
    except exc_type as e:
        if match in str(e):
            results.append((label, True))
            print(f"  {PASS} {label}")
        else:
            results.append((label, False))
            print(f"  {FAIL} {label}: wrong message: {e}")
    except Exception as e:
        results.append((label, False))
        print(f"  {FAIL} {label}: wrong exception type: {type(e).__name__}: {e}")


# =====================================================================
print("\n" + "=" * 70)
print("TEST 1: Federated identity with INLINE token")
print("=" * 70)
auth = AuthConfig(
    mode=AuthMode.federated_identity,
    tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",
    adme_api_client_id="e37a6c70-7cbc-4593-80fc-01c1f20203f7",
    service_principal_client_id="sp-client-id-123",
    federated_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.inline-assertion-body",
)
cred = build_credential(auth)
assert_eq("credential type is ClientAssertionCredential",
           type(cred).__name__, "FakeClientAssertionCredential")
assert_eq("tenant_id passed correctly", cred.tenant_id, "72f988bf-86f1-41af-91ab-2d7cd011db47")
assert_eq("client_id is SP client id", cred.client_id, "sp-client-id-123")

tok = cred.get_token("api://e37a6c70-7cbc-4593-80fc-01c1f20203f7/.default")
assert_eq("token exchange simulated", tok.token.startswith("exchanged-from:"), True)

# =====================================================================
print("\n" + "=" * 70)
print("TEST 2: Federated identity with TOKEN FILE")
print("=" * 70)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write("eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.file-based-oidc-assertion\n")
    token_file_path = f.name

auth2 = AuthConfig(
    mode=AuthMode.federated_identity,
    tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",
    adme_api_client_id="e37a6c70-7cbc-4593-80fc-01c1f20203f7",
    service_principal_client_id="sp-client-id-123",
    federated_token_file=token_file_path,
)
cred2 = build_credential(auth2)
tok2 = cred2.get_token("api://e37a6c70-7cbc-4593-80fc-01c1f20203f7/.default")
assert_eq("file-based token read and exchanged", tok2.token.startswith("exchanged-from:"), True)
os.unlink(token_file_path)

# =====================================================================
print("\n" + "=" * 70)
print("TEST 3: Federated identity — MISSING service_principal_client_id")
print("=" * 70)
auth3 = AuthConfig(
    mode=AuthMode.federated_identity,
    tenant_id="t",
    adme_api_client_id="app",
    federated_token="some-assertion",
)
assert_raises("raises ValueError for missing SP client_id",
              ValueError, "service_principal_client_id",
              lambda: build_credential(auth3))

# =====================================================================
print("\n" + "=" * 70)
print("TEST 4: Federated identity — MISSING token AND token_file")
print("=" * 70)
auth4 = AuthConfig(
    mode=AuthMode.federated_identity,
    tenant_id="t",
    adme_api_client_id="app",
    service_principal_client_id="sp-id",
)
assert_raises("raises ValueError for missing federated token source",
              ValueError, "federated_token",
              lambda: build_credential(auth4))

# =====================================================================
print("\n" + "=" * 70)
print("TEST 5: AuthProvider with federated_identity mode (end-to-end)")
print("=" * 70)
auth5 = AuthConfig(
    mode=AuthMode.federated_identity,
    tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",
    adme_api_client_id="e37a6c70-7cbc-4593-80fc-01c1f20203f7",
    service_principal_client_id="sp-client-id-123",
    federated_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.e2e-federated-assertion",
)
provider = AuthProvider(auth5)
assert_eq("scope is correct", provider.scope, "api://e37a6c70-7cbc-4593-80fc-01c1f20203f7/.default")
bearer = provider.get_bearer_token()
assert_eq("bearer token acquired", bearer.startswith("exchanged-from:"), True)

# =====================================================================
print("\n" + "=" * 70)
print("TEST 6: Static token mode still works (regression)")
print("=" * 70)
auth6 = AuthConfig(
    mode=AuthMode.static_token,
    tenant_id="t",
    adme_api_client_id="app",
    static_access_token="pre-minted-jwt-from-az-cli",
)
provider6 = AuthProvider(auth6)
bearer6 = provider6.get_bearer_token()
assert_eq("static token passthrough works", bearer6, "pre-minted-jwt-from-az-cli")

# =====================================================================
print("\n" + "=" * 70)
print("TEST 7: Config YAML compatibility (simulates connector_runtime.yaml)")
print("=" * 70)
import yaml  # noqa: E402 - available in base Python installs via PyYAML

yaml_content = """
mode: federated_identity
tenant_id: 72f988bf-86f1-41af-91ab-2d7cd011db47
adme_api_client_id: e37a6c70-7cbc-4593-80fc-01c1f20203f7
service_principal_client_id: sp-client-id-123
federated_token: eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.from-yaml-config
"""
parsed = yaml.safe_load(yaml_content)
auth7 = AuthConfig(**parsed)
assert_eq("YAML config deserializes to AuthConfig", auth7.mode, AuthMode.federated_identity)
assert_eq("federated_token from YAML", auth7.federated_token,
           "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.from-yaml-config")

# =====================================================================
# SUMMARY
print("\n" + "=" * 70)
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
if failed == 0:
    print(f"\033[92mALL {total} ASSERTIONS PASSED\033[0m")
else:
    print(f"\033[91m{failed}/{total} ASSERTIONS FAILED\033[0m")
print("=" * 70 + "\n")
sys.exit(0 if failed == 0 else 1)
