"""JWT payload inspection without signature verification (demo / diagnostics only)."""

from __future__ import annotations

import base64
import json
from typing import Any, Optional


def decode_jwt_payload_noverify(jwt: str) -> dict[str, Any]:
    parts = jwt.split(".")
    if len(parts) != 3:
        raise ValueError("Not a JWT (expected 3 parts).")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))


def safe_token_claims_summary(token: str) -> dict[str, Any]:
    """
    Return a small dict safe to print (aud, tid, oid, appid/azp, roles).

    Does not verify signature — suitable for smoke tests on trusted acquisition paths only.
    """
    claims = decode_jwt_payload_noverify(token)
    roles = claims.get("roles")
    return {
        "aud": claims.get("aud"),
        "tid": claims.get("tid"),
        "oid": claims.get("oid"),
        "appid": claims.get("appid") or claims.get("azp"),
        "roles": roles,
        "exp": claims.get("exp"),
    }
