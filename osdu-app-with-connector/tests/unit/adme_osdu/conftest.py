"""Pytest fixtures for AdmeOsduLakeflowConnect tests.

In simulate mode (default): activates respx HTTP mock serving corpus JSON.
In live mode (CONNECTOR_TEST_MODE=live): no mock; uses real credentials from
  CONNECTOR_TEST_CONFIG_JSON or CONNECTOR_TEST_CONFIG_PATH env vars.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

CORPUS_DIR = Path(__file__).resolve().parents[3] / "connector" / "simulator" / "corpus"
CONNECTOR_TEST_MODE = os.environ.get("CONNECTOR_TEST_MODE", "simulate")


def _load_live_config() -> dict[str, str]:
    inline = os.environ.get("CONNECTOR_TEST_CONFIG_JSON", "").strip()
    if inline:
        return json.loads(inline)
    path_env = os.environ.get("CONNECTOR_TEST_CONFIG_PATH", "").strip()
    if path_env:
        return json.loads(Path(path_env).read_text(encoding="utf-8"))
    local = Path(__file__).parent / "dev_config.json"
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    raise RuntimeError(
        "Live mode requires credentials via CONNECTOR_TEST_CONFIG_JSON, "
        "CONNECTOR_TEST_CONFIG_PATH, or tests/unit/adme_osdu/dev_config.json"
    )


@pytest.fixture(scope="module")
def connector_options() -> dict[str, str]:
    """Return options dict — simulator credentials in simulate mode, real creds in live mode."""
    if CONNECTOR_TEST_MODE == "live":
        return _load_live_config()
    return {
        "base_url": "https://adme-simulator.example.com",
        "data_partition_id": "opendes",
        "access_token": "simulator-fake-token",
    }


@pytest.fixture(autouse=True, scope="module")
def adme_http_mock():
    """Auto-apply ADME HTTP mock for all tests in simulate mode."""
    if CONNECTOR_TEST_MODE == "live":
        yield None
        return

    import httpx
    import respx

    import json as _json

    def _load(name: str) -> Any:
        p = CORPUS_DIR / name
        return _json.loads(p.read_text()) if p.exists() else {}

    def _search_handler(request: httpx.Request) -> httpx.Response:
        try:
            body = _json.loads(request.content)
        except Exception:
            body = {}
        # Subsequent page (cursor) or incremental query (watermark filter) → empty
        if body.get("cursor") or body.get("query"):
            return httpx.Response(200, json={"results": [], "cursor": None, "totalCount": 0})
        kind = body.get("kind", "")
        import re
        corpus_file = "wellbore.json"
        if re.search(r"Reservoir", kind, re.IGNORECASE):
            corpus_file = "reservoir.json"
        elif re.search(r"Rock|Fluid|RockAndFluid", kind, re.IGNORECASE):
            corpus_file = "rock_and_fluid.json"
        records = _load(corpus_file)
        if not isinstance(records, list):
            records = []
        return httpx.Response(200, json={"results": records, "cursor": None, "totalCount": len(records)})

    with respx.mock(assert_all_called=False) as mock:
        mock.post(url__regex=r"/api/search/v2/query").mock(side_effect=_search_handler)
        mock.get(url__regex=r"/api/legal/v1/legaltags").mock(
            side_effect=lambda req: httpx.Response(200, json=_load("legal_tags.json"))
        )
        mock.get(url__regex=r"/api/entitlements/v2/groups").mock(
            side_effect=lambda req: httpx.Response(200, json=_load("entitlements.json"))
        )
        yield mock
