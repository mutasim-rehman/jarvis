import re
import webbrowser

import httpx
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


def handle_get_highlights(task: Task, ctx: HandlerContext) -> TaskResult:
    """Fetch URL content, extract all text, and use Ollama to clean and summarize."""
    del ctx  # no allowlist needed for public news URLs
    url = (task.target or "").strip()
    if not url:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="MISSING_TARGET",
            message="GET_HIGHLIGHTS requires a target URL.",
        )

    try:
        from executor.app.config import settings

        # Use Jina Reader API to get clean Markdown from dynamic JS sites
        # This avoids needing a local Playwright installation while still reaching JS-rendered content.
        jina_url = f"https://r.jina.ai/{url}"
        
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            # Use a simpler User-Agent which often works better with proxy services
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/plain"
            }
            resp = client.get(jina_url, headers=headers)
            
            if resp.status_code == 403:
                return TaskResult(
                    action=task.action,
                    success=False,
                    error_code="SCRAPE_FORBIDDEN",
                    message=f"Access denied by Jina Reader (403). The site might be blocking automated access. Content: {resp.text[:100]}",
                    artifacts={"url": url}
                )
            
            resp.raise_for_status()
            raw_text = resp.text

            # 2. Limit context for the LLM
            text_context = raw_text[:8000]

            if len(text_context) < 100:
                return TaskResult(
                    action=task.action,
                    success=True,
                    message="The page content seems empty or restricted, but I've opened it for you.",
                    artifacts={"url": url},
                )

            # 3. Call Ollama to "clean" and summarize the text
            prompt = (
                "You are JARVIS, a professional intelligence assistant. Below is a markdown representation of a news dashboard. "
                "Extract the top 5 most important news highlights or headlines from this text. "
                "Ignore navigation links, button labels, and map coordinates. "
                "Format as a clean bulleted list. Be concise.\n\n"
                f"SOURCE URL: {url}\n"
                "CONTENT:\n"
                f"{text_context}"
            )

            try:
                chat_payload = {
                    "model": settings.ollama_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "num_ctx": 4096
                    }
                }
                ollama_resp = client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json=chat_payload,
                    timeout=60.0,
                )
                if ollama_resp.status_code == 200:
                    summary = (
                        ollama_resp.json()
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                    msg = summary
                else:
                    msg = f"Scraped text via Jina, but LLM cleaning failed (HTTP {ollama_resp.status_code})."
            except Exception as e:
                msg = f"I fetched the page content, but failed to clean it with LLM: {e}"

            return TaskResult(
                action=task.action,
                success=True,
                message=msg,
                artifacts={"url": url, "text_length": len(raw_text)},
            )

    except Exception as e:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="SCRAPE_FAILED",
            message=f"Failed to fetch news highlights: {e}",
            artifacts={"url": url},
        )
