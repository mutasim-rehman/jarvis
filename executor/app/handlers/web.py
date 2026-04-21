import ctypes
import re
import subprocess
import time
import webbrowser

import httpx
from shared.schema import Task, TaskResult

from executor.app.context import HandlerContext


def _switch_arc_space(index: int) -> bool:
    """Focuses Arc, hovers left edge to trigger sidebar, and switches Space/Profile."""
    ps_cmd = f"""
    $wshell = New-Object -ComObject WScript.Shell;
    $procs = Get-Process Arc -ErrorAction SilentlyContinue;
    $success = $false;
    if ($procs) {{
        foreach ($p in $procs) {{
            if ($p.MainWindowTitle) {{
                if ($wshell.AppActivate($p.Id)) {{
                    Write-Output "ACTIVATED"
                    break;
                }}
            }}
        }}
    }}
    """
    try:
        # 1. Activate/Focus Arc
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        if "ACTIVATED" not in res.stdout.upper():
            return False

        # 2. Hover extreme left edge to trigger sidebar pop-up
        # We use relative mouse_event moves because some apps (Electron) 
        # ignore sudden SetCursorPos jumps but listen to relative movement events.
        try:
            # First, ensure we are around the middle of the screen horizontally
            # but reasonably far from the left edge so we can 'move into' it.
            # 150 pixels from left is a good start.
            ctypes.windll.user32.SetCursorPos(150, 500)
            time.sleep(0.1)

            # Move relatively to the left in small steps (5 pixels each)
            # 40 steps * 5 pixels = 200 pixels total movement (overshooting 150 to hit the wall)
            for _ in range(40): 
                # 0x0001 = MOUSEEVENTF_MOVE
                ctypes.windll.user32.mouse_event(0x0001, -5, 0, 0, 0)
                time.sleep(0.01)

            # 1. Wait a quarter second after hitting the edge
            time.sleep(0.25)

            # 2. Move a bit right (10 pixels) as requested
            for _ in range(2):
                ctypes.windll.user32.mouse_event(0x0001, 5, 0, 0, 0)
                time.sleep(0.01)

            # 3. Wait for the sidebar animation to stabilize
            time.sleep(0.8)
        except Exception:
            pass

        # 4. Use low-level keyboard events to trigger the switch (Ctrl + Index)
        # keybd_event is more reliable than WScript.Shell.SendKeys for modern apps
        try:
            # VK Codes
            VK_CONTROL = 0x11
            # VK_1 is 0x31, VK_2 is 0x32, etc.
            VK_KEY = 0x30 + int(index)
            KEYUP = 0x0002

            # Press Ctrl
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
            time.sleep(0.05)
            # Press Index Key
            ctypes.windll.user32.keybd_event(VK_KEY, 0, 0, 0)
            time.sleep(0.05)
            # Release Index Key
            ctypes.windll.user32.keybd_event(VK_KEY, 0, KEYUP, 0)
            time.sleep(0.05)
            # Release Ctrl
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)
            
            # Wait a bit for the space switch to occur before opening the URL
            time.sleep(0.5)
            return True
        except Exception:
            return False
    except Exception:
        return False


def handle_open_url(task: Task, ctx: HandlerContext) -> TaskResult:
    target = (task.target or "").strip()
    if not target:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="MISSING_TARGET",
            message="OPEN_URL requires a target.",
        )

    # Check for profile_index in task parameters (from workflows.py)
    profile_index = getattr(task, "profile_index", None)
    # If not on task, check task.model_extra
    if profile_index is None and hasattr(task, "model_extra") and task.model_extra:
        profile_index = task.model_extra.get("profile_index")

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
        switched_msg = ""
        if profile_index is not None:
            # 1. Try to switch first (if already open)
            if _switch_arc_space(profile_index):
                switched_msg = f" (switched to Arc space {profile_index})"
            
            # 2. Open the URL
            webbrowser.open(url)

            # 3. If we didn't switch yet (maybe Arc was closed), wait and try again
            if not switched_msg:
                time.sleep(3.0)  # wait for Arc to launch and window to appear
                if _switch_arc_space(profile_index):
                    switched_msg = f" (switched to Arc space {profile_index} after launch)"
        else:
            webbrowser.open(url)

        return TaskResult(
            action=task.action,
            success=True,
            message=f"Opened {url}{switched_msg}.",
            artifacts={"url": url, "profile_index": profile_index},
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
                error_code="SCRAPE_FAILED",
                message=f"Failed to fetch news highlights: {e}",
                artifacts={"url": url},
            )


def handle_get_assignments(task: Task, ctx: HandlerContext) -> TaskResult:
    """Fetch assignments from Google Classroom REST API — no browser, no clipboard."""
    del ctx

    try:
        from executor.app.config import settings
        from executor.app.auth.google import get_access_token, CLASSROOM_SCOPES

        token = get_access_token(CLASSROOM_SCOPES)
        headers = {"Authorization": f"Bearer {token}"}
        api = "https://classroom.googleapis.com/v1"

        with httpx.Client(timeout=30.0) as client:
            # 1. List active courses
            courses_resp = client.get(f"{api}/courses", headers=headers, params={"courseStates": "ACTIVE"})
            courses_resp.raise_for_status()
            courses: list[dict] = courses_resp.json().get("courses", [])

            if not courses:
                return TaskResult(
                    action=task.action,
                    success=True,
                    message="No active courses found in Google Classroom.",
                )

            # 2. For each course, fetch coursework and filter for incomplete submissions
            pending: list[dict] = []
            for course in courses:
                cid = course["id"]
                cname = course.get("name", cid)

                # Get all coursework (assignments)
                cw_resp = client.get(
                    f"{api}/courses/{cid}/courseWork",
                    headers=headers,
                    params={"courseWorkStates": "PUBLISHED", "orderBy": "dueDate asc"},
                )
                if cw_resp.status_code != 200:
                    continue
                coursework: list[dict] = cw_resp.json().get("courseWork", [])

                for cw in coursework:
                    cwid = cw["id"]
                    # Get my submission status for this assignment
                    sub_resp = client.get(
                        f"{api}/courses/{cid}/courseWork/{cwid}/studentSubmissions",
                        headers=headers,
                        params={"userId": "me"},
                    )
                    if sub_resp.status_code != 200:
                        continue
                    subs: list[dict] = sub_resp.json().get("studentSubmissions", [])
                    for sub in subs:
                        state = sub.get("state", "")
                        # Only include not yet turned in
                        if state not in ("TURNED_IN", "RETURNED"):
                            due = cw.get("dueDate")
                            due_str = ""
                            if due:
                                due_str = f"{due.get('year', '?')}-{due.get('month', '?'):02}-{due.get('day', '?'):02}"
                                if cw.get("dueTime"):
                                    t = cw["dueTime"]
                                    due_str += f" {t.get('hours', 0):02}:{t.get('minutes', 0):02}"
                            pending.append({
                                "course": cname,
                                "title": cw.get("title", "Untitled"),
                                "due": due_str or "No due date",
                                "state": state,
                                "link": cw.get("alternateLink", ""),
                            })

        if not pending:
            return TaskResult(
                action=task.action,
                success=True,
                message="You have no pending assignments in Google Classroom. You're all caught up! 🎉",
            )

        # 3. Format the list
        lines = ["Here are your pending assignments:\n"]
        for i, a in enumerate(pending, 1):
            lines.append(f"{i}. [{a['course']}] {a['title']}")
            lines.append(f"   Due: {a['due']}  |  Status: {a['state']}")
            if a["link"]:
                lines.append(f"   Link: {a['link']}")
        lines.append("\nWhich one would you like to start with?")
        msg = "\n".join(lines)

        return TaskResult(
            action=task.action,
            success=True,
            message=msg,
            artifacts={"pending_count": len(pending), "assignments": pending},
        )

    except Exception as e:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="CLASSROOM_ERROR",
            message=f"Failed to fetch assignments from Google Classroom API: {e}",
        )
