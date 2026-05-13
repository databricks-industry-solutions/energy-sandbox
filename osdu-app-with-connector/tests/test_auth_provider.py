from connector.auth.providers import AuthProvider, build_credential
from connector.models.config import AuthConfig, AuthMode


def test_static_token_credential():
    auth = AuthConfig(
        mode=AuthMode.static_token,
        tenant_id="t",
        adme_api_client_id="app",
        static_access_token="x.y.z",
    )
    cred = build_credential(auth)
    tok = cred.get_token("api://app/.default")
    assert tok.token == "x.y.z"


def test_safe_token_claims_summary_reexport():
    import base64
    import json

    from connector.auth.providers import safe_token_claims_summary

    payload = {"aud": "api://x", "tid": "t1"}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    jwt = f"eyJhbGciOiJub25lIn0.{b64}.sig"
    s = safe_token_claims_summary(jwt)
    assert s.get("aud") == "api://x"


def test_auth_provider_scope():
    auth = AuthConfig(
        mode=AuthMode.static_token,
        tenant_id="t",
        adme_api_client_id="myapp",
        static_access_token="a.b.c",
    )
    p = AuthProvider(auth)
    assert p.scope == "api://myapp/.default"


def test_federated_identity_inline_token():
    """Federated identity mode with inline assertion token builds ClientAssertionCredential."""
    auth = AuthConfig(
        mode=AuthMode.federated_identity,
        tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",
        adme_api_client_id="e37a6c70-7cbc-4593-80fc-01c1f20203f7",
        service_principal_client_id="sp-client-id-123",
        federated_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake-assertion",
    )
    cred = build_credential(auth)
    from azure.identity import ClientAssertionCredential

    assert isinstance(cred, ClientAssertionCredential)


def test_federated_identity_token_file(tmp_path):
    """Federated identity mode reads assertion from file."""
    token_file = tmp_path / "federated-token.txt"
    token_file.write_text("eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.file-based-assertion\n")

    auth = AuthConfig(
        mode=AuthMode.federated_identity,
        tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",
        adme_api_client_id="e37a6c70-7cbc-4593-80fc-01c1f20203f7",
        service_principal_client_id="sp-client-id-123",
        federated_token_file=str(token_file),
    )
    cred = build_credential(auth)
    from azure.identity import ClientAssertionCredential

    assert isinstance(cred, ClientAssertionCredential)


def test_federated_identity_missing_client_id():
    """Federated identity mode without SP client ID raises ValueError."""
    import pytest

    auth = AuthConfig(
        mode=AuthMode.federated_identity,
        tenant_id="t",
        adme_api_client_id="app",
        federated_token="some-assertion",
    )
    with pytest.raises(ValueError, match="service_principal_client_id"):
        build_credential(auth)


def test_federated_identity_missing_token():
    """Federated identity mode without token or file raises ValueError."""
    import pytest

    auth = AuthConfig(
        mode=AuthMode.federated_identity,
        tenant_id="t",
        adme_api_client_id="app",
        service_principal_client_id="sp-id",
    )
    with pytest.raises(ValueError, match="federated_token"):
        build_credential(auth)
