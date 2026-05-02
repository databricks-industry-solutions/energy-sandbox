"""ADME HTTP client: Entra bearer token, required headers, retries, pagination helpers."""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from connector.auth.auth_provider import AuthProvider
from connector.models.config import ConnectorRuntimeConfig, DomainConfig
from connector.utils.pagination import PageResult, iter_pages

logger = logging.getLogger(__name__)


def _should_retry_http(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class ADMEApiClient:
    """
    Low-level ADME client.

    - Acquires tokens for ``api://<adme_api_client_id>/.default``
    - Sends ``data-partition-id`` on every request
    - Retries transient failures with exponential backoff + jitter
    """

    def __init__(
        self,
        runtime: ConnectorRuntimeConfig,
        auth: AuthProvider,
        *,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._runtime = runtime
        self._auth = auth
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=runtime.api_base(),
            timeout=httpx.Timeout(runtime.http.timeout_seconds),
            limits=httpx.Limits(max_connections=runtime.http.max_connections),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ADMEApiClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        token = self._auth.get_bearer_token()
        # Omit Content-Type on generic headers: some gateways mis-handle GET with
        # ``Content-Type: application/json`` and no body. POST/PUT use ``json=`` so httpx sets it.
        return {
            "Authorization": f"Bearer {token}",
            "data-partition-id": self._runtime.data_partition_id,
            "Accept": "application/json",
        }

    def _do_request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=1, max=60),
            retry=retry_if_exception(_should_retry_http),
            reraise=True,
        )
        def one() -> httpx.Response:
            extra_headers = kwargs.get("headers") or {}
            merged = {**self._headers(), **extra_headers}
            rest = {k: v for k, v in kwargs.items() if k != "headers"}
            r = self._client.request(method, path, headers=merged, **rest)
            r.raise_for_status()
            return r

        return one()

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Perform a request with retries; does not raise on 4xx/5xx (for diagnostics)."""
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=1, max=60),
            retry=retry_if_exception(_should_retry_http),
            reraise=True,
        )
        def one() -> httpx.Response:
            extra_headers = kwargs.get("headers") or {}
            merged = {**self._headers(), **extra_headers}
            rest = {k: v for k, v in kwargs.items() if k != "headers"}
            return self._client.request(method, path, headers=merged, **rest)

        return one()

    def get_json(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        r = self._do_request("GET", path, params=params or {})
        return r.json()

    def post_json(self, path: str, *, json_body: Optional[dict[str, Any]] = None) -> Any:
        r = self._do_request("POST", path, json=json_body or {})
        return r.json()

    def fetch_domain_page(
        self,
        domain: DomainConfig,
        *,
        cursor: Optional[str],
        watermark: Optional[str],
        load_full: bool,
    ) -> Any:
        """Build request from domain config and return parsed JSON body."""
        body = {k: v for k, v in domain.extraction.base_query.items() if v not in ("", None)}
        body["limit"] = domain.pagination.page_size
        if domain.pagination.cursor_request_field and cursor:
            body[domain.pagination.cursor_request_field] = cursor
        if not load_full and watermark and domain.extraction.incremental_filter_template:
            frag = domain.extraction.incremental_filter_template.format(watermark=watermark)
            q = body.get("query")
            if isinstance(q, str) and q.strip():
                body["query"] = f"({q}) AND ({frag})"
            else:
                body["query"] = frag
        method = domain.extraction.method
        path = domain.extraction.path
        if method == "GET":
            raise NotImplementedError("GET extraction requires custom params mapping — use POST search for Phase 1.")
        return self.post_json(path, json_body=body)

    def iter_domain_pages(
        self,
        domain: DomainConfig,
        *,
        watermark: Optional[str],
        load_full: bool,
    ) -> Iterator[PageResult]:
        """Paginate using domain pagination config."""

        def fetch(cursor: Optional[str]) -> Any:
            return self.fetch_domain_page(
                domain,
                cursor=cursor,
                watermark=watermark,
                load_full=load_full,
            )

        yield from iter_pages(fetch, pagination=domain.pagination)

    def smoke_get(self, path: str, *, timeout: Optional[float] = None) -> httpx.Response:
        """GET without forcing raise_for_status (for notebook diagnostics)."""
        t = timeout or self._runtime.http.timeout_seconds
        return self.request("GET", path, timeout=t)
