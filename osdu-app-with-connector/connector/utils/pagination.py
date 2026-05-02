"""Generic pagination helpers for ADME/OSDU JSON responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional

from connector.models.config import PaginationConfig


def _get_path(obj: Any, dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


@dataclass
class PageResult:
    """One page of records plus optional cursor for the next request."""

    records: list[dict[str, Any]]
    next_cursor: Optional[str] = None


def parse_page(body: Any, pagination: PaginationConfig) -> PageResult:
    """
    Extract records and next cursor from a JSON response body using configured paths.

    ``records_path`` is a dotted path to a list (e.g. ``results``).
    ``cursor_path`` is a dotted path to the next cursor token string.
    """
    if not isinstance(body, dict):
        return PageResult(records=[], next_cursor=None)
    items = _get_path(body, pagination.records_path)
    records: list[dict[str, Any]] = []
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                records.append(it)
    cursor_val = _get_path(body, pagination.cursor_path) if pagination.cursor_path else None
    next_cursor = cursor_val if isinstance(cursor_val, str) and cursor_val else None
    return PageResult(records=records, next_cursor=next_cursor)


def iter_pages(
    fetch_page: Callable[[Optional[str]], Any],
    *,
    pagination: PaginationConfig,
) -> Iterator[PageResult]:
    """
    Yield pages until no cursor (caller supplies ``fetch_page(cursor) -> response JSON body``).
    """
    cursor: Optional[str] = None
    while True:
        body = fetch_page(cursor)
        page = parse_page(body, pagination)
        yield page
        if not page.next_cursor:
            break
        cursor = page.next_cursor
