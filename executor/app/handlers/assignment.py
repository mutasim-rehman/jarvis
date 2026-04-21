"""DO_ASSIGNMENT handler.

Pipeline:
  1. Parse target → assignment ref (number or title) + ai_tool ('gemini'|'antigravity')
  2. Re-fetch pending assignments from Classroom API (cached token — instant)
  3. Match by index or fuzzy title
  4. Create workspace folder at Assignment_Location/<course>/<assignment>/
  5a. ai_tool='gemini'    → call Gemini API → write starter files → open VS Code
  5b. ai_tool='antigravity' → write README skeleton → open Antigravity IDE
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv as _ld
    _ld(override=False)
except ImportError:
    pass

import httpx

from shared.schema import Task, TaskResult
from executor.app.config import settings
from executor.app.context import HandlerContext

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ANTIGRAVITY_EXE = Path(settings.assignment_location or "").parent / "Programs" / "Antigravity" / "Antigravity.exe"
# We'll use a better way to find Antigravity below
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-2.0-flash:generateContent"
)
_CLASSROOM_API = "https://classroom.googleapis.com/v1"


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------

def _assignment_root() -> Path:
    raw = settings.assignment_location.strip().strip('"').strip("'")
    if not raw:
        raise RuntimeError("Assignment_Location not set in .env")
    return Path(raw)


def _project_root() -> Path:
    raw = settings.project_location.strip().strip('"').strip("'")
    if not raw:
        raise RuntimeError("Project_Location not set in .env")
    return Path(raw)


def _gemini_key() -> str:
    k = os.environ.get("Google_Gemini_Key", "").strip()
    if not k:
        raise RuntimeError("Google_Gemini_Key not set in .env")
    return k


# ---------------------------------------------------------------------------
# Target parser: "17|gemini" → (ref="17", tool="gemini")
# ---------------------------------------------------------------------------

def _parse_target(raw: str | None) -> tuple[str | None, str | None]:
    """
    Split target string of format "<ref>|<tool>".
    Returns (reference, ai_tool). ai_tool is None if not specified.
    """
    if not raw:
        return None, None
    parts = raw.split("|", 1)
    ref = parts[0].strip() or None
    tool = parts[1].strip().lower() if len(parts) > 1 else None
    if tool and tool not in ("gemini", "antigravity"):
        tool = None
    return ref, tool


# ---------------------------------------------------------------------------
# Classroom: fetch pending assignments (reuses cached Google token)
# ---------------------------------------------------------------------------

def _fetch_pending_assignments(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    pending: list[dict] = []

    with httpx.Client(timeout=30.0) as client:
        cr = client.get(f"{_CLASSROOM_API}/courses", headers=headers, params={"courseStates": "ACTIVE"})
        cr.raise_for_status()
        courses: list[dict] = cr.json().get("courses", [])

        for course in courses:
            cid = course["id"]
            cname = course.get("name", cid)
            cwr = client.get(
                f"{_CLASSROOM_API}/courses/{cid}/courseWork",
                headers=headers,
                params={"courseWorkStates": "PUBLISHED", "orderBy": "dueDate asc"},
            )
            if cwr.status_code != 200:
                continue
            for cw in cwr.json().get("courseWork", []):
                cwid = cw["id"]
                sr = client.get(
                    f"{_CLASSROOM_API}/courses/{cid}/courseWork/{cwid}/studentSubmissions",
                    headers=headers,
                    params={"userId": "me"},
                )
                if sr.status_code != 200:
                    continue
                for sub in sr.json().get("studentSubmissions", []):
                    if sub.get("state") not in ("TURNED_IN", "RETURNED"):
                        due = cw.get("dueDate")
                        due_str = ""
                        if due:
                            due_str = f"{due.get('year')}-{due.get('month', 0):02}-{due.get('day', 0):02}"
                        pending.append({
                            "course": cname,
                            "title": cw.get("title", "Untitled"),
                            "due": due_str or "No due date",
                            "link": cw.get("alternateLink", ""),
                            "description": cw.get("description", ""),
                        })
    return pending


def _resolve_assignment(ref: str | None, pending: list[dict]) -> dict | None:
    """
    Match ref (could be a 1-based number or title fragment) to a pending assignment.
    """
    if not ref:
        return pending[0] if pending else None

    # Try numeric index first
    if re.fullmatch(r"\d+", ref.strip()):
        idx = int(ref.strip()) - 1  # user says "17" → list index 16
        if 0 <= idx < len(pending):
            return pending[idx]

    # Fuzzy title match
    titles = [a["title"] for a in pending]
    matches = difflib.get_close_matches(ref, titles, n=1, cutoff=0.35)
    if matches:
        for a in pending:
            if a["title"] == matches[0]:
                return a

    # Contains match
    ref_lower = ref.lower()
    for a in pending:
        if ref_lower in a["title"].lower() or ref_lower in a["course"].lower():
            return a

    return None


# ---------------------------------------------------------------------------
# Folder creation
# ---------------------------------------------------------------------------

def _slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s).strip("_")
    return s[:maxlen].lower()


def _create_workspace(assignment: dict) -> Path:
    root = _assignment_root()
    course_slug = _slugify(assignment["course"])
    title_slug = _slugify(assignment["title"])
    folder = root / course_slug / title_slug
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ---------------------------------------------------------------------------
# Gemini code generation
# ---------------------------------------------------------------------------

_GEMINI_PROMPT = """\
You are a university-level expert programmer helping a student get started on an assignment.

Assignment Title: {title}
Course: {course}
Due Date: {due}
Description: {description}

Generate starter files for this assignment. Return ONLY a valid JSON array with no markdown, \
no explanation outside the JSON. Each element must have "filename" and "content" keys.

Include at minimum:
- README.md (title, task description, how to run)
- main source file (appropriate language based on course: Python for AI/DS/algorithms, Java for general CS)
- Any helper files that make sense

Example format:
[
  {{"filename": "README.md", "content": "# Assignment\\n..."}},
  {{"filename": "main.py", "content": "# Starter code\\n..."}}
]
"""


def _call_gemini(assignment: dict) -> list[dict]:
    """Call Gemini and return list of {filename, content} dicts."""
    key = _gemini_key()
    prompt = _GEMINI_PROMPT.format(
        title=assignment["title"],
        course=assignment["course"],
        due=assignment["due"],
        description=assignment.get("description", "No description provided."),
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }
    url = f"{_GEMINI_ENDPOINT}?key={key}"

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()

    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    # Extract JSON array from possible markdown fences
    json_match = re.search(r"\[[\s\S]*\]", text)
    if not json_match:
        raise ValueError(f"Gemini returned no JSON array. Response: {text[:300]}")
    return json.loads(json_match.group(0))


def _write_files(folder: Path, files: list[dict]) -> list[str]:
    written: list[str] = []
    for f in files:
        name = f.get("filename", "").strip()
        content = f.get("content", "")
        if not name:
            continue
        # Prevent path traversal
        target = folder / Path(name).name
        target.write_text(content, encoding="utf-8")
        written.append(name)
    return written


# ---------------------------------------------------------------------------
# IDE launchers
# ---------------------------------------------------------------------------

def _open_vscode(folder: Path) -> None:
    try:
        subprocess.Popen(["code", str(folder)], close_fds=True)
        return
    except FileNotFoundError:
        pass
    # Try common VS Code paths on Windows
    for candidate in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
        Path(r"C:\Program Files\Microsoft VS Code\Code.exe"),
    ]:
        if candidate.is_file():
            subprocess.Popen([str(candidate), str(folder)], close_fds=True)
            return


def _open_antigravity(folder: Path) -> None:
    # Use the found path from earlier research
    local = os.environ.get("LOCALAPPDATA", "")
    exe = Path(local) / "Programs" / "Antigravity" / "Antigravity.exe"
    
    if exe.is_file():
        subprocess.Popen([str(exe), str(folder)], close_fds=True)
    else:
        # Fallback: try PATH
        try:
            subprocess.Popen(["antigravity", str(folder)], close_fds=True)
        except FileNotFoundError:
            raise RuntimeError(f"Antigravity IDE not found at {exe}. Please install it.")


# ---------------------------------------------------------------------------
# Public handler
# ---------------------------------------------------------------------------

def handle_do_assignment(task: Task, ctx: HandlerContext) -> TaskResult:
    """
    Resolve assignment → create folder → generate with Gemini or open in Antigravity.
    target format: "<ref>|<tool>"  e.g. "17|gemini" or "CS2001-Project|antigravity"
    """
    del ctx

    ref, ai_tool = _parse_target(task.target)

    try:
        # 1. Authenticate with Google Classroom
        from executor.app.auth.google import get_access_token, CLASSROOM_SCOPES
        token = get_access_token(CLASSROOM_SCOPES)

        # 2. Fetch pending assignments
        print(f"[JARVIS] Fetching pending assignments from Classroom...")
        pending = _fetch_pending_assignments(token)

        if not pending:
            return TaskResult(
                action=task.action,
                success=True,
                message="You have no pending assignments in Google Classroom. You're all caught up!",
            )

        # 3. Resolve which assignment
        assignment = _resolve_assignment(ref, pending)
        if not assignment:
            options = "\n".join(f"  {i+1}. {a['title']} ({a['course']})" for i, a in enumerate(pending[:10]))
            return TaskResult(
                action=task.action,
                success=False,
                error_code="NOT_FOUND",
                message=(
                    f"Could not find assignment matching '{ref or '?'}'.\n"
                    f"Which one would you like to start? Here are your options:\n{options}\n\n"
                    "Tell me 'do number 1' or 'start the data structures project'."
                ),
            )

        print(f"[JARVIS] Resolved: [{assignment['course']}] {assignment['title']}")

        # 3b. Ask for AI Tool if not specified
        if not ai_tool:
            return TaskResult(
                action=task.action,
                success=True,
                message=(
                    f"Alright, I've found [{assignment['course']}] {assignment['title']}.\n"
                    "Should I use **Gemini** to generate starter code for you in VS Code, "
                    "or should I open the project in the **Antigravity IDE** so you can work with its AI directly?"
                ),
                artifacts={
                    "assignment_title": assignment['title'],
                    "needs_choice": True
                }
            )

        # 4. Create workspace folder
        folder = _create_workspace(assignment)
        print(f"[JARVIS] Workspace: {folder}")

        # 5. Generate or open
        if ai_tool == "gemini":
            print(f"[JARVIS] Calling Gemini to generate starter files...")
            files = _call_gemini(assignment)
            written = _write_files(folder, files)
            _open_vscode(folder)

            file_list = "\n".join(f"  - {f}" for f in written)
            return TaskResult(
                action=task.action,
                success=True,
                message=(
                    f"Ready! Here's what I set up for [{assignment['course']}] {assignment['title']}:\n\n"
                    f"Folder: {folder}\n"
                    f"Files generated by Gemini:\n{file_list}\n\n"
                    f"VS Code is opening now. Good luck!"
                ),
                artifacts={
                    "folder": str(folder),
                    "assignment": assignment,
                    "files_created": written,
                    "ai_tool": "gemini",
                },
            )

        else:  # antigravity
            # Write a minimal README so the folder isn't empty
            readme = folder / "README.md"
            if not readme.exists():
                readme.write_text(
                    f"# {assignment['title']}\n\n"
                    f"**Course:** {assignment['course']}\n"
                    f"**Due:** {assignment['due']}\n\n"
                    f"## Assignment Link\n{assignment['link']}\n\n"
                    f"## Description\n{assignment.get('description', 'See the Classroom link above.')}\n\n"
                    f"## Notes\n_Start coding here. Antigravity AI is ready to assist._\n",
                    encoding="utf-8",
                )
            _open_antigravity(folder)

            return TaskResult(
                action=task.action,
                success=True,
                message=(
                    f"Opened [{assignment['course']}] {assignment['title']} in Antigravity.\n\n"
                    f"Folder: {folder}\n"
                    f"A README.md has been created with the assignment details.\n"
                    f"Antigravity's AI is ready — describe what you need and it will help you code it."
                ),
                artifacts={
                    "folder": str(folder),
                    "assignment": assignment,
                    "ai_tool": "antigravity",
                },
            )

    except Exception as e:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="ASSIGNMENT_ERROR",
            message=f"Failed to set up assignment: {e}",
        )
