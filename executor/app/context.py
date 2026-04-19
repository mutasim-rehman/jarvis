from dataclasses import dataclass
from pathlib import Path


@dataclass
class HandlerContext:
    path_roots: list[Path]
    apps: dict[str, str]
    url_aliases: dict[str, str]
