"""respx-based ADME HTTP mock — routes requests to corpus JSON files."""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import httpx
import respx

CORPUS_DIR = Path(__file__).parent / "corpus"

_KIND_CORPUS = [
    (re.compile(r"Wellbore", re.IGNORECASE),          "wellbore.json"),
    (re.compile(r"Reservoir", re.IGNORECASE),          "reservoir.json"),
    (re.compile(r"Rock|Fluid|RockAndFluid", re.IGNORECASE), "rock_and_fluid.json"),
]


def _load(name: str) -> object:
    p = CORPUS_DIR / name
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _search_side_effect(request: httpx.Request) -> httpx.Response:
    try:
        body = json.loads(request.content)
    except Exception:
        body = {}

    # Subsequent page (cursor) or incremental query (watermark filter) → empty, signals end of pagination
    if body.get("cursor") or body.get("query"):
        return httpx.Response(200, json={"results": [], "cursor": None, "totalCount": 0})

    kind = body.get("kind", "")
    corpus_file = "wellbore.json"
    for pattern, fname in _KIND_CORPUS:
        if pattern.search(kind):
            corpus_file = fname
            break

    records = _load(corpus_file)
    if not isinstance(records, list):
        records = []
    return httpx.Response(200, json={"results": records, "cursor": None, "totalCount": len(records)})


def configure_routes(router: respx.Router) -> None:
    """Register all ADME endpoint mocks on *router*."""
    router.post(url__regex=r"/api/search/v2/query").mock(side_effect=_search_side_effect)
    router.get(url__regex=r"/api/legal/v1/legaltags").mock(
        side_effect=lambda req: httpx.Response(200, json=_load("legal_tags.json"))
    )
    router.get(url__regex=r"/api/entitlements/v2/groups").mock(
        side_effect=lambda req: httpx.Response(200, json=_load("entitlements.json"))
    )


@contextmanager
def adme_simulator() -> Generator[respx.Router, None, None]:
    """Context manager: intercept all ADME HTTP calls and serve corpus data."""
    with respx.mock(assert_all_called=False) as router:
        configure_routes(router)
        yield router
