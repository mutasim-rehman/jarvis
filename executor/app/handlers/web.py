import webbrowser

from shared.schema import Task, TaskResult

from executor.app.context import HandlerContext


def handle_open_url(task: Task, ctx: HandlerContext) -> TaskResult:
    target = (task.target or "").strip()
    if not target:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="MISSING_TARGET",
            message="OPEN_URL requires a target.",
        )

    url = target
    key = target.lower()
    if key in ctx.url_aliases:
        url = ctx.url_aliases[key]
    elif "://" not in url:
        if "." in url:
            url = "https://" + url.lstrip("/")
        else:
            return TaskResult(
                action=task.action,
                success=False,
                error_code="INVALID_URL",
                message="Use a full URL, a domain (e.g. example.com), or configure url_aliases in the allowlist.",
            )

    try:
        webbrowser.open(url)
        return TaskResult(
            action=task.action,
            success=True,
            message=f"Opened {url}.",
            artifacts={"url": url},
        )
    except Exception as e:  # noqa: BLE001 — surface any browser backend failure
        return TaskResult(
            action=task.action,
            success=False,
            error_code="BROWSER_FAILED",
            message=str(e),
        )
