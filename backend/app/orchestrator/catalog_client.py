"""Fetch and cache the executor tool catalog."""

from __future__ import annotations

import logging
import time

import httpx

from backend.app.config import settings
from shared.schema import ToolCatalog

logger = logging.getLogger(__name__)

_cache: ToolCatalog | None = None
_cache_at: float = 0.0


async def _http_fetch_catalog(force: bool = False) -> ToolCatalog:
    url = f"{settings.executor_base_url.rstrip('/')}/api/capabilities"
    headers = {settings.api_key_header: settings.executor_api_key} if settings.executor_api_key else {}
    params = {"refresh": "true"} if force else {}
    async with httpx.AsyncClient(timeout=min(settings.executor_timeout_seconds, 30.0)) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return ToolCatalog.model_validate(response.json())


def _local_fallback_catalog() -> ToolCatalog:
    from executor.app.capabilities.discovery import build_tool_catalog

    return build_tool_catalog(force=True)


async def fetch_catalog(force: bool = False) -> ToolCatalog:
    global _cache, _cache_at
    now = time.monotonic()
    ttl = max(1.0, settings.orchestrator_catalog_ttl_seconds)
    if not force and _cache is not None and (now - _cache_at) < ttl:
        return _cache

    try:
        catalog = await _http_fetch_catalog(force=force)
    except Exception as exc:
        logger.warning("Failed to fetch tool catalog from executor: %s", exc)
        if _cache is not None:
            return _cache
        catalog = _local_fallback_catalog()
        logger.info("Using local fallback tool catalog (%d tools)", len(catalog.capabilities))

    _cache = catalog
    _cache_at = now
    return catalog


def invalidate_catalog_cache() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0
