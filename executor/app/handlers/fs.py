from pathlib import Path

from shared.schema import Task, TaskResult

from executor.app.allowlist import is_path_under_roots
from executor.app.config import settings
from executor.app.context import HandlerContext


def handle_create_folder(task: Task, ctx: HandlerContext) -> TaskResult:
    target = (task.target or "").strip()
    if not target:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="MISSING_TARGET",
            message="CREATE_FOLDER requires a target path.",
        )

    if not ctx.path_roots:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="NO_PATH_ROOT",
            message="No path roots configured.",
        )

    raw = Path(target)
    if raw.is_absolute():
        resolved = raw
    else:
        # Smart routing: 'assignments/...' -> Assignment_Location, 'projects/...' -> Project_Location
        parts = raw.parts
        if parts[0] == "assignments" and settings.assignment_location:
            base = Path(settings.assignment_location.strip().strip('"').strip("'")).expanduser().resolve()
            resolved = (base / Path(*parts[1:])).resolve()
        elif parts[0] == "projects" and settings.project_location:
            base = Path(settings.project_location.strip().strip('"').strip("'")).expanduser().resolve()
            resolved = (base / Path(*parts[1:])).resolve()
        else:
            resolved = (ctx.path_roots[0] / raw).resolve()

    if not is_path_under_roots(resolved, ctx.path_roots):
        return TaskResult(
            action=task.action,
            success=False,
            error_code="PATH_NOT_ALLOWED",
            message="Path is outside allowed roots.",
        )

    try:
        resolved.mkdir(parents=True, exist_ok=True)
        return TaskResult(
            action=task.action,
            success=True,
            message=f"Ensured directory {resolved}.",
            artifacts={"path": str(resolved)},
        )
    except OSError as e:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="FS_ERROR",
            message=str(e),
        )
