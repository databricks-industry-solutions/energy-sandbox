"""Pytest fixtures for AdmeOsduLakeflowConnect tests.

Modes (set CONNECTOR_TEST_MODE env var):
  simulate (default) — offline: serves pre-recorded corpus JSON via respx mock
  record              — hits real ADME, writes responses to corpus/ for future simulate runs
  live                — hits real ADME, no corpus writes

Live / record modes require credentials via one of:
  CONNECTOR_TEST_CONFIG_JSON  — inline JSON string
  CONNECTOR_TEST_CONFIG_PATH  — path to JSON file
  tests/unit/adme_osdu/dev_config.json — local file (gitignored)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

CORPUS_DIR = Path(__file__).resolve().parents[3] / "connector" / "simulator" / "corpus"
CONNECTOR_TEST_MODE = os.environ.get("CONNECTOR_TEST_MODE", "simulate")

_KIND_CORPUS_MAP = [
    (re.compile(r"Wellbore",       re.IGNORECASE), "wellbore.json"),
    (re.compile(r"ReservoirZone",  re.IGNORECASE), "reservoir.json"),
    (re.compile(r"Rock|RockAndFluidSample", re.IGNORECASE), "rock_and_fluid.json"),
]


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
        "Live/record mode requires credentials via CONNECTOR_TEST_CONFIG_JSON, "
        "CONNECTOR_TEST_CONFIG_PATH, or tests/unit/adme_osdu/dev_config.json"
    )


@pytest.fixture(scope="module")
def connector_options() -> dict[str, str]:
    if CONNECTOR_TEST_MODE in ("live", "record"):
        return _load_live_config()
    return {
        "base_url":          "https://adme-simulator.example.com",
        "data_partition_id": "opendes",
        "access_token":      "simulator-fake-token",
    }


@pytest.fixture(autouse=True, scope="module")
def adme_http_mock():
    """Auto-apply ADME HTTP mock for simulate mode; record mode captures + saves."""
    if CONNECTOR_TEST_MODE == "live":
        yield None
        return

    if CONNECTOR_TEST_MODE == "record":
        yield from _record_mode_fixture()
        return

    # ── simulate mode ──────────────────────────────────────────────────────────
    import httpx
    import respx

    def _load(name: str) -> Any:
        p = CORPUS_DIR / name
        return json.loads(p.read_text()) if p.exists() else {}

    def _search_handler(request: httpx.Request) -> httpx.Response:
        try:
            body = json.loads(request.content)
        except Exception:
            body = {}
        # Cursor page or incremental watermark query → empty, signals pagination done
        if body.get("cursor") or body.get("query"):
            return httpx.Response(200, json={"results": [], "cursor": None, "totalCount": 0})
        kind = body.get("kind", "")
        corpus_file = "wellbore.json"
        for pattern, fname in _KIND_CORPUS_MAP:
            if pattern.search(kind):
                corpus_file = fname
                break
        records = _load(corpus_file)
        if not isinstance(records, list):
            records = []
        return httpx.Response(200, json={"results": records, "cursor": None, "totalCount": len(records)})

    # assert_all_called=True validates every registered route is exercised by the suite
    with respx.mock(assert_all_called=True) as mock:
        mock.post(url__regex=r"/api/search/v2/query").mock(side_effect=_search_handler)
        mock.get(url__regex=r"/api/legal/v1/legaltags").mock(
            side_effect=lambda req: httpx.Response(200, json=_load("legal_tags.json"))
        )
        mock.get(url__regex=r"/api/entitlements/v2/groups").mock(
            side_effect=lambda req: httpx.Response(200, json=_load("entitlements.json"))
        )
        yield mock


def _record_mode_fixture():
    """Make real ADME calls, capture responses, and overwrite corpus files.

    Requires live credentials (see module docstring).
    After recording completes, re-run with CONNECTOR_TEST_MODE=simulate to verify.
    """
    import httpx as _httpx

    _captured: dict[str, Any] = {
        "wellbore":       [],
        "reservoir":      [],
        "rock_and_fluid": [],
        "legal_tags":     None,
        "entitlements":   None,
    }
    _original_send = _httpx.Client.send

    def _recording_send(client_self, request, *, stream=False, follow_redirects=False, **kwargs):
        response = _original_send(client_self, request, stream=stream, follow_redirects=follow_redirects, **kwargs)
        url = str(request.url)
        try:
            body = json.loads(response.content)
        except Exception:
            return response

        if "/api/search/v2/query" in url:
            try:
                req_body = json.loads(request.content)
            except Exception:
                req_body = {}
            kind = req_body.get("kind", "")
            results = body.get("results", [])
            if results:
                for pattern, key in [
                    (re.compile(r"Wellbore",      re.IGNORECASE), "wellbore"),
                    (re.compile(r"ReservoirZone", re.IGNORECASE), "reservoir"),
                    (re.compile(r"Rock|RockAndFluidSample", re.IGNORECASE), "rock_and_fluid"),
                ]:
                    if pattern.search(kind):
                        _captured[key].extend(results)
                        break
        elif "/api/legal/v1/legaltags" in url:
            _captured["legal_tags"] = body
        elif "/api/entitlements/v2/groups" in url:
            _captured["entitlements"] = body

        return response

    from unittest.mock import patch as _patch
    with _patch.object(_httpx.Client, "send", _recording_send):
        yield None

    # Write captured responses to corpus
    for key in ("wellbore", "reservoir", "rock_and_fluid"):
        if _captured[key]:
            out = CORPUS_DIR / f"{key}.json"
            out.write_text(json.dumps(_captured[key], indent=2, default=str), encoding="utf-8")
            print(f"\n[record] wrote {len(_captured[key])} records → {out}")

    for key, filename in (("legal_tags", "legal_tags.json"), ("entitlements", "entitlements.json")):
        if _captured[key] is not None:
            out = CORPUS_DIR / filename
            out.write_text(json.dumps(_captured[key], indent=2, default=str), encoding="utf-8")
            print(f"\n[record] wrote {filename} → {out}")
