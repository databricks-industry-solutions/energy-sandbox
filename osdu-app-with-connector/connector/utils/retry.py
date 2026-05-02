"""HTTP retry with exponential backoff (tenacity)."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

F = TypeVar("F", bound=Callable[..., Any])


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


def retry_http(fn: F) -> F:
    """Decorator for httpx calls: retry on timeouts, transport errors, and 429/5xx."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception(_should_retry),
    )(fn)
