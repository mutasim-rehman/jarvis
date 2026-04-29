from __future__ import annotations

from shared.schema import Task, TaskResult
from executor.app.context import HandlerContext
from executor.app.handlers.music import handle_play_music
from executor.app.handlers.web import handle_get_highlights

_TECH_NEWS_URL = "https://tech.worldmonitor.app"


def _top_lines(text: str, limit: int = 3) -> list[str]:
    rows: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(line)
        if len(rows) >= limit:
            break
    return rows


def handle_morning_ritual(task: Task, ctx: HandlerContext) -> TaskResult:
    del task

    music_result = handle_play_music(Task(action="PLAY_MUSIC", target=None), ctx)
    news_result = handle_get_highlights(Task(action="GET_HIGHLIGHTS", target=_TECH_NEWS_URL), ctx)

    greeting = "Good morning. Systems are online."
    music_line = music_result.message if music_result.message else "Music command sent."

    if news_result.success and news_result.message.strip():
        preview = _top_lines(news_result.message, limit=3)
        if preview:
            news_section = "Latest tech highlights:\n- " + "\n- ".join(preview)
        else:
            news_section = "I fetched the latest tech news."
    else:
        news_section = "I couldn't fetch tech highlights just now, but I can retry on command."

    message = (
        f"{greeting}\n"
        f"{music_line}\n\n"
        f"{news_section}\n\n"
        "What should we start building today?"
    )

    return TaskResult(
        action="MORNING_RITUAL",
        success=bool(music_result.success or news_result.success),
        message=message,
        artifacts={
            "music": music_result.model_dump(),
            "news": news_result.model_dump(),
            "news_url": _TECH_NEWS_URL,
        },
    )
