from pathlib import Path
from typing import Optional

import yaml


def load_allowlist_config(path: Optional[Path]) -> tuple[list[Path], dict[str, str], dict[str, str]]:
    """
    Load path roots, app shortcuts, and URL aliases.
    Without a YAML file, uses ~/jarvis-executor-workspace as the only path root (created if missing).
    """
    default_root = Path.home() / "jarvis-executor-workspace"
    apps: dict[str, str] = {}
    url_aliases: dict[str, str] = {}

    if path and path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        roots = [Path(p).expanduser().resolve() for p in (raw.get("path_roots") or [])]
        if not roots:
            default_root.mkdir(parents=True, exist_ok=True)
            roots = [default_root.resolve()]
        for k, v in (raw.get("apps") or {}).items():
            apps[str(k).lower()] = str(v)
        for k, v in (raw.get("url_aliases") or {}).items():
            url_aliases[str(k).lower()] = str(v)
        return roots, apps, url_aliases

    default_root.mkdir(parents=True, exist_ok=True)
    return [default_root.resolve()], apps, url_aliases


def is_path_under_roots(resolved: Path, roots: list[Path]) -> bool:
    try:
        resolved = resolved.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False
