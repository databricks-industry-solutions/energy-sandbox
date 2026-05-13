"""Minimal respx stub using unittest.mock to intercept httpx.Client.send.

Implements the subset of the respx API used by the ADME connector tests:
    with respx.mock(assert_all_called=False) as router:
        router.post(url__regex=...).mock(side_effect=fn)
        router.get(url__regex=...).mock(side_effect=fn)
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional
from unittest.mock import patch

import httpx


class Route:
    def __init__(self, method: str, url_pattern: str) -> None:
        self._method = method.upper()
        self._pattern = re.compile(url_pattern)
        self._side_effect: Optional[Callable] = None
        self._return_value: Optional[httpx.Response] = None
        self.called: bool = False
        self.call_count: int = 0

    def mock(
        self,
        *,
        side_effect: Optional[Callable] = None,
        return_value: Optional[httpx.Response] = None,
    ) -> "Route":
        self._side_effect = side_effect
        self._return_value = return_value
        return self

    def matches(self, request: httpx.Request) -> bool:
        if request.method.upper() != self._method:
            return False
        return bool(self._pattern.search(str(request.url)))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.called = True
        self.call_count += 1
        if self._side_effect is not None:
            return self._side_effect(request)
        if self._return_value is not None:
            return self._return_value
        return httpx.Response(200)


class Router:
    def __init__(self) -> None:
        self._routes: list[Route] = []

    def post(self, url__regex: str = "", **kwargs: Any) -> Route:
        pattern = url__regex or kwargs.get("url__regex", "")
        route = Route("POST", pattern)
        self._routes.append(route)
        return route

    def get(self, url__regex: str = "", **kwargs: Any) -> Route:
        pattern = url__regex or kwargs.get("url__regex", "")
        route = Route("GET", pattern)
        self._routes.append(route)
        return route

    def dispatch(self, request: httpx.Request) -> httpx.Response:
        for route in self._routes:
            if route.matches(request):
                return route.handle(request)
        raise httpx.ConnectError(
            f"respx stub: no route matched {request.method} {request.url}",
            request=request,
        )


@contextmanager
def mock(assert_all_called: bool = True) -> Generator[Router, None, None]:
    """Context manager: intercept all httpx.Client.send calls and dispatch to routes."""
    router = Router()

    _original_send = httpx.Client.send

    def _fake_send(
        client_self: httpx.Client,
        request: httpx.Request,
        *,
        stream: bool = False,
        follow_redirects: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        response = router.dispatch(request)
        response.request = request
        return response

    with patch.object(httpx.Client, "send", _fake_send):
        yield router

    if assert_all_called:
        uncalled = [r for r in router._routes if not r.called]
        if uncalled:
            patterns = ", ".join(f"{r._method} {r._pattern.pattern}" for r in uncalled)
            raise AssertionError(
                f"respx stub: {len(uncalled)} route(s) were never called: {patterns}"
            )
