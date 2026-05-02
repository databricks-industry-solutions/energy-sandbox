"""Stable import surface for auth (re-exports + token helpers)."""

from __future__ import annotations

from typing import Any

from connector.auth.auth_provider import AuthProvider, StaticBearerTokenCredential, build_credential

__all__ = [
    "AuthProvider",
    "StaticBearerTokenCredential",
    "build_credential",
    "safe_token_claims_summary",
]


def safe_token_claims_summary(token: str) -> dict[str, Any]:
    from connector.auth import token_utils as _tu

    return _tu.safe_token_claims_summary(token)
