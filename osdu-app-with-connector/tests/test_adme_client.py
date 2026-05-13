import httpx
import pytest
import respx

from connector.auth.providers import AuthProvider
from connector.clients.adme_api import ADMEApiClient
from connector.config_loader import load_runtime_config
from connector.domains.registry import load_domain_config
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime():
    return load_runtime_config(ROOT / "conf" / "connector_runtime.example.yaml")


@pytest.fixture
def auth_provider(runtime):
    from connector.models.config import AuthMode

    runtime.auth.mode = AuthMode.static_token
    runtime.auth.static_access_token = "test-token"
    return AuthProvider(runtime.auth)


@respx.mock
def test_search_pagination(runtime, auth_provider):
    domain = load_domain_config(ROOT / "conf" / "domains" / "wellbore.yaml")
    base = runtime.api_base()
    respx.post(f"{base}/api/search/v2/query").mock(
        side_effect=[
            httpx.Response(200, json={"results": [{"id": "1"}], "cursor": "c2"}),
            httpx.Response(200, json={"results": [{"id": "2"}], "cursor": None}),
        ]
    )
    pages = []
    with ADMEApiClient(runtime, auth_provider) as c:
        for page in c.iter_domain_pages(domain, watermark=None, load_full=True):
            pages.append(page)
    assert len(pages) == 2
    assert [p.records[0]["id"] for p in pages] == ["1", "2"]
