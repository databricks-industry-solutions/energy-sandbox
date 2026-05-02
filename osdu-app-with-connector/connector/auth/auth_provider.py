"""
Core Entra credentials (no imports from other ``connector.*`` packages at module load).

Split from ``providers.py`` so ``ADMEApiClient`` / notebooks can load auth without import cycles.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import ClientSecretCredential, ManagedIdentityCredential

__all__ = ["AuthProvider", "StaticBearerTokenCredential", "build_credential"]


class StaticBearerTokenCredential(TokenCredential):
    """Pre-issued JWT (secrets / CI)."""

    def __init__(self, token: str, expires_on: Optional[int] = None) -> None:
        if not token or not token.strip():
            raise ValueError("static token must be non-empty")
        self._token = token.strip()
        self._expires_on = expires_on if expires_on is not None else int(time.time()) + 3600

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        return AccessToken(self._token, self._expires_on)


def build_credential(auth: Any) -> TokenCredential:
    """Lazy import of config enums to avoid cycles."""
    from connector.models.config import AuthMode

    mode = auth.mode
    if mode == AuthMode.static_token:
        if not auth.static_access_token:
            raise ValueError("static_token mode requires static_access_token")
        return StaticBearerTokenCredential(
            auth.static_access_token,
            expires_on=auth.static_token_expires_on,
        )
    if mode == AuthMode.service_principal:
        if not auth.service_principal_client_id or not auth.service_principal_client_secret:
            raise ValueError("service_principal mode requires client id and secret")
        return ClientSecretCredential(
            tenant_id=auth.tenant_id,
            client_id=auth.service_principal_client_id,
            client_secret=auth.service_principal_client_secret,
        )
    if auth.managed_identity_client_id:
        return ManagedIdentityCredential(client_id=auth.managed_identity_client_id)
    return ManagedIdentityCredential()


class AuthProvider:
    """Wraps credential + scope for ADME API tokens."""

    def __init__(self, auth: Any) -> None:
        self._auth = auth
        self._credential = build_credential(auth)

    @property
    def scope(self) -> str:
        return self._auth.token_scope

    def get_bearer_token(self) -> str:
        tok = self._credential.get_token(self.scope)
        return tok.token

    @property
    def credential(self) -> TokenCredential:
        return self._credential
