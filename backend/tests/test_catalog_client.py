import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.orchestrator import catalog_client
from shared.schema import ToolCatalog, ToolCapability, ToolDefinition


@pytest.fixture(autouse=True)
def clear_cache():
    catalog_client.invalidate_catalog_cache()
    yield
    catalog_client.invalidate_catalog_cache()


def _mock_catalog() -> ToolCatalog:
    return ToolCatalog(
        capabilities=[
            ToolCapability(
                tool=ToolDefinition(name="OPEN_APP", category="app", description="open"),
                available=True,
            )
        ],
        discovered_apps=["cursor"],
        capability_tags=["test"],
    )


@pytest.mark.asyncio
async def test_fetch_catalog_caches(monkeypatch):
    calls = {"n": 0}

    async def fake_http(force: bool = False):
        calls["n"] += 1
        return _mock_catalog()

    monkeypatch.setattr(catalog_client, "_http_fetch_catalog", fake_http)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_catalog_ttl_seconds", 60.0)

    c1 = await catalog_client.fetch_catalog()
    c2 = await catalog_client.fetch_catalog()
    assert c1.discovered_apps == ["cursor"]
    assert calls["n"] == 1
    assert c2.discovered_apps == ["cursor"]


@pytest.mark.asyncio
async def test_fetch_catalog_force_refresh(monkeypatch):
    calls = {"n": 0}

    async def fake_http(force: bool = False):
        calls["n"] += 1
        return _mock_catalog()

    monkeypatch.setattr(catalog_client, "_http_fetch_catalog", fake_http)
    monkeypatch.setattr("backend.app.config.settings.orchestrator_catalog_ttl_seconds", 60.0)

    await catalog_client.fetch_catalog()
    await catalog_client.fetch_catalog(force=True)
    assert calls["n"] == 2
