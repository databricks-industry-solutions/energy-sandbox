"""Minimal tenacity stub — retry is a passthrough (no actual retrying in tests)."""
from __future__ import annotations

from typing import Any, Callable, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])


def retry(*args: Any, **kwargs: Any) -> Any:
    """No-op retry decorator."""
    def decorator(fn: _F) -> _F:
        return fn
    # Support both @retry and @retry(...) call styles
    if args and callable(args[0]):
        return args[0]
    return decorator


def retry_if_exception(predicate: Any) -> Any:
    return predicate


def stop_after_attempt(n: int) -> Any:
    return n


def wait_exponential_jitter(**kwargs: Any) -> Any:
    return kwargs
