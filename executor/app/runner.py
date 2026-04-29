from pathlib import Path

from shared.schema import ActionCommand, RunCommandResponse, Task, TaskResult

from executor.app.allowlist import load_allowlist_config
from executor.app.config import settings
from executor.app.context import HandlerContext
from executor.app.handlers.apps import handle_open_app
from executor.app.handlers.assignment import handle_do_assignment
from executor.app.handlers.fs import handle_create_folder
from executor.app.handlers.music import handle_play_music
from executor.app.handlers.routine import handle_morning_ritual
from executor.app.handlers.video import handle_watch_video
from executor.app.handlers.web import handle_get_assignments, handle_get_highlights, handle_open_url

_HANDLERS = {
    "OPEN_APP": handle_open_app,
    "OPEN_URL": handle_open_url,
    "OPEN_WEBSITE": handle_open_url,
    "GET_HIGHLIGHTS": handle_get_highlights,
    "GET_ASSIGNMENTS": handle_get_assignments,
    "DO_ASSIGNMENT": handle_do_assignment,
    "CREATE_FOLDER": handle_create_folder,
    "PLAY_MUSIC": handle_play_music,
    "WATCH_VIDEO": handle_watch_video,
    "MORNING_RITUAL": handle_morning_ritual,
}
_allowlist_cache: dict[str, tuple[float, tuple[list[Path], dict[str, str], dict[str, str]]]] = {}


def normalize_tasks(cmd: ActionCommand) -> list[Task]:
    if cmd.tasks:
        return list(cmd.tasks)
    intent = (cmd.intent or "").strip()
    if intent == "OPEN_WEBSITE":
        return [Task(action="OPEN_URL", target=cmd.target)]
    if intent == "PLAY_MUSIC":
        return [Task(action="PLAY_MUSIC", target=cmd.target)]
    if intent == "FILE_OPERATION":
        return [Task(action="FILE_ACTION", target=cmd.target)]
    if intent == "SEARCH_WEB":
        return [Task(action="SEARCH", target=cmd.target)]
    if intent == "CLOSE_APP":
        return [Task(action="CLOSE_APP", target=cmd.target)]
    return [Task(action="OPEN_APP", target=cmd.target)]


def build_context(allowlist_file: Path | None) -> HandlerContext:
    cache_key = str(allowlist_file.resolve()) if allowlist_file else "__default__"
    mtime = allowlist_file.stat().st_mtime if allowlist_file and allowlist_file.exists() else 0.0
    cached = _allowlist_cache.get(cache_key)
    if cached and cached[0] == mtime:
        roots, apps, url_aliases = cached[1]
    else:
        roots, apps, url_aliases = load_allowlist_config(allowlist_file)
        _allowlist_cache[cache_key] = (mtime, (list(roots), dict(apps), dict(url_aliases)))
    
    # Add project and assignment locations as allowed roots
    for loc in [settings.assignment_location, settings.project_location]:
        if loc:
            cleaned = loc.strip().strip('"').strip("'")
            if cleaned:
                p = Path(cleaned).expanduser().resolve()
                if p not in roots:
                    roots.append(p)
    
    return HandlerContext(
        path_roots=roots,
        apps=apps,
        url_aliases=url_aliases,
        settings=settings,
    )


def run_command(cmd: ActionCommand, ctx: HandlerContext) -> RunCommandResponse:
    tasks = normalize_tasks(cmd)
    results: list[TaskResult] = []
    for task in tasks:
        handler = _HANDLERS.get(task.action)
        if handler is None:
            results.append(
                TaskResult(
                    action=task.action,
                    success=False,
                    error_code="NOT_IMPLEMENTED",
                    message=f"Action {task.action} is not implemented.",
                )
            )
        else:
            results.append(handler(task, ctx))
    overall = all(r.success for r in results)
    return RunCommandResponse(overall_success=overall, results=results)


def run_command_with_allowlist_path(cmd: ActionCommand, allowlist_path: str | None) -> RunCommandResponse:
    path = Path(allowlist_path).expanduser() if allowlist_path else None
    if path is not None and not path.is_file():
        path = None
    ctx = build_context(path)
    return run_command(cmd, ctx)
