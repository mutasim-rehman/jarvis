from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings

@dataclass
class HandlerContext:
    path_roots: list[Path]
    apps: dict[str, str]
    url_aliases: dict[str, str]
    settings: 'Settings'
