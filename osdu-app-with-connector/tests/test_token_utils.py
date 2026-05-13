import base64
import json

from connector.auth.token_utils import decode_jwt_payload_noverify, safe_token_claims_summary


def _b64url(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def test_decode_and_summary():
    payload = {"aud": "api://x", "tid": "t1", "oid": "o1", "appid": "a1", "roles": ["r"], "exp": 9999999999}
    jwt = f"eyJhbGciOiJub25lIn0.{_b64url(payload)}.sig"
    claims = decode_jwt_payload_noverify(jwt)
    assert claims["aud"] == "api://x"
    summary = safe_token_claims_summary(jwt)
    assert summary["tid"] == "t1"
    assert summary["roles"] == ["r"]
