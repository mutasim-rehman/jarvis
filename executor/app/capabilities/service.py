"""Cached capability catalog service for executor API."""

from __future__ import annotations

from shared.schema import ToolCatalog

from .discovery import build_tool_catalog


class CapabilitiesService:
    def __init__(self) -> None:
        self._catalog: ToolCatalog | None = None

    def get(self, refresh: bool = False) -> ToolCatalog:
        if refresh or self._catalog is None:
            self._catalog = build_tool_catalog(force=refresh)
        return self._catalog


capabilities_service = CapabilitiesService()
