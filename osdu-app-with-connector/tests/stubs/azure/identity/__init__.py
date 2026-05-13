"""Minimal stub for azure.identity — only what the connector imports at module level.

These classes are never instantiated in simulate-mode tests because _build_runtime
always uses AuthMode.static_token, which short-circuits to StaticBearerTokenCredential
before any Azure credential is created.
"""
from __future__ import annotations


class ClientAssertionCredential:
    def __init__(self, tenant_id: str, client_id: str, func) -> None:
        raise RuntimeError("ClientAssertionCredential stub — not available in test environment")


class ClientSecretCredential:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        raise RuntimeError("ClientSecretCredential stub — not available in test environment")


class ManagedIdentityCredential:
    def __init__(self, *, client_id: str | None = None) -> None:
        raise RuntimeError("ManagedIdentityCredential stub — not available in test environment")
