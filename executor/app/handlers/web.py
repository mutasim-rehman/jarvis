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
            success=False,
            error_code="SCRAPE_FAILED",
            message=f"Failed to fetch news highlights: {e}",
            artifacts={"url": url},
        )


def handle_get_assignments(task: Task, ctx: HandlerContext) -> TaskResult:
    """Fetch Classroom content locally by copying text from the open browser."""
    del ctx
    url = (task.target or "").strip()
    
    # We wait for the browser to actually load the page after OPEN_URL
    # 5 seconds is usually enough, but let's be generous
    time.sleep(6.0)

    try:
        from executor.app.config import settings

        # 1. Focus Arc and copy all text to clipboard
        # We also click in the center to ensure the webpage content has focus
        try:
             # Click roughly in the middle of the browser
             ctypes.windll.user32.SetCursorPos(600, 500)
             time.sleep(0.1)
             # MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004
             ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
             time.sleep(0.05)
             ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
             time.sleep(0.2)
        except Exception:
             pass

        ps_copy = """
        $wshell = New-Object -ComObject WScript.Shell;
        $procs = Get-Process Arc -ErrorAction SilentlyContinue;
        if ($procs) {
            foreach ($p in $procs) {
                if ($p.MainWindowTitle) {
                    if ($wshell.AppActivate($p.Id)) {
                        Start-Sleep -m 800
                        $wshell.SendKeys("^a") # Ctrl+A
                        Start-Sleep -m 400
                        $wshell.SendKeys("^c") # Ctrl+C
                        Start-Sleep -m 400
                        Write-Output "COPIED"
                        return
                    }
                }
            }
        }
        """
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_copy], capture_output=True, text=True)
        
        if "COPIED" not in res.stdout.upper():
             return TaskResult(
                action=task.action,
                success=True,
                message="I've opened the page. (Note: I couldn't focus the Arc window to read the assignments automatically).",
                artifacts={"url": url}
            )

        # 2. Get the content from the clipboard
        # We use -Raw to get everything exactly as is
        clip_res = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], capture_output=True, text=True, encoding="utf-8")
        raw_text = clip_res.stdout.strip()

        # If it's very short, it's likely just a few characters or UI junk
        if len(raw_text) < 20:
            return TaskResult(
                action=task.action,
                success=True,
                message="I've opened the page, but I couldn't find any assignment text. Please check if you are logged in!",
                artifacts={"url": url, "captured_length": len(raw_text)}
            )

        # 3. Process with Ollama
        text_context = raw_text[:4000] # Reduced context to avoid out-of-memory 500 errors
        prompt = (
            "You are JARVIS, a professional assistant. Below is the text content copied from a Google Classroom 'To-do' page. "
            "Extract the names of all pending assignments and their due dates. "
            "If it says 'CL2001-Lab' or similar, include it. "
            "Format them as a clean numbered list. "
            "At the end, ask the user: 'Which one would you like to start with?'\n\n"
            "CONTENT:\n"
            f"{text_context}"
        )

        try:
            with httpx.Client(timeout=120.0) as client:
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
                )
                if ollama_resp.status_code == 200:
                    msg = ollama_resp.json().get("message", {}).get("content", "").strip()
                else:
                    msg = f"I've opened the assignments. (Summarization failed with status {ollama_resp.status_code}, but the page is ready in your browser)."
        except Exception as e:
            msg = f"I've opened the assignments. (Summarization error: {e})"

        return TaskResult(
            action=task.action,
            success=True,
            message=msg,
            artifacts={"url": url, "text_length": len(raw_text), "clipboard_snippet": raw_text[:200]},
        )

    except Exception as e:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="SCRAPE_FAILED",
            message=f"Failed to process assignments locally: {e}",
            artifacts={"url": url},
        )
