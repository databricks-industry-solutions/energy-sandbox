"""Minimal stub for azure.core.credentials — only what the connector needs."""
from __future__ import annotations


class AccessToken:
    def __init__(self, token: str, expires_on: int) -> None:
        self.token = token
        self.expires_on = expires_on


class TokenCredential:
    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        raise NotImplementedError
