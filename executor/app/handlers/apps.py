import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from shared.schema import Task, TaskResult

from executor.app.context import HandlerContext


def _windows_well_known_exe(canonical_name: str) -> Path | None:
    """Resolve common desktop apps that are rarely on PATH (e.g. Spotify installer build)."""
    name = canonical_name.lower().strip()
    if name not in ("spotify", "spotify.exe", "arc", "arc.exe"):
        return None
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    app_map = {
        "spotify": [
            Path(appdata) / "Spotify" / "Spotify.exe",
            Path(local) / "Microsoft" / "WindowsApps" / "Spotify.exe",
            Path(program_files) / "Spotify" / "Spotify.exe",
            Path(program_files_x86) / "Spotify" / "Spotify.exe",
        ],
        "arc": [
            Path(local) / "Microsoft" / "WindowsApps" / "Arc.exe",
            Path(local) / "Arc" / "Arc.exe",
            Path(program_files) / "Arc" / "Arc.exe",
        ]
    }
    
    # Handle both "app" and "app.exe"
    app_key = name.replace(".exe", "")
    candidates = app_map.get(app_key, [])
    
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def _windows_shell_open_no_ui(target: str) -> bool:
    """Launch via shell like Win+R / start, but without \"cannot find\" message boxes."""
    SEE_MASK_FLAG_NO_UI = 0x00000400
    SW_SHOWNORMAL = 1

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint32),
            ("fMask", ctypes.c_ulong),
            ("hwnd", ctypes.c_void_p),
            ("lpVerb", ctypes.c_wchar_p),
            ("lpFile", ctypes.c_wchar_p),
            ("lpParameters", ctypes.c_wchar_p),
            ("lpDirectory", ctypes.c_wchar_p),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.c_void_p),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", ctypes.c_wchar_p),
            ("hKeyClass", ctypes.c_void_p),
            ("dwHotKey", ctypes.c_uint32),
            ("hMonitor", ctypes.c_void_p),
            ("hProcess", ctypes.c_void_p),
        ]

    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    sei.fMask = SEE_MASK_FLAG_NO_UI
    sei.hwnd = None
    sei.lpVerb = "open"
    sei.lpFile = target
    sei.lpParameters = None
    sei.lpDirectory = None
    sei.nShow = SW_SHOWNORMAL
    return bool(ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)))


def handle_open_app(task: Task, ctx: HandlerContext) -> TaskResult:
    target = (task.target or "").strip()
    if not target:
        return TaskResult(
            action=task.action,
            success=False,
            error_code="MISSING_TARGET",
            message="OPEN_APP requires a target.",
        )

    key = target.lower()
    if key in ctx.apps:
        exe = ctx.apps[key]
        path = Path(exe)
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen([str(path)])
            return TaskResult(action=task.action, success=True, message=f"Started {exe}.")
        except OSError as e:
            return TaskResult(
                action=task.action,
                success=False,
                error_code="START_FAILED",
                message=str(e),
            )

    if sys.platform == "win32":
        well_known = _windows_well_known_exe(key)
        if well_known:
            try:
                os.startfile(str(well_known))  # type: ignore[attr-defined]
                return TaskResult(
                    action=task.action,
                    success=True,
                    message=f"Started {well_known}.",
                )
            except OSError as e:
                return TaskResult(
                    action=task.action,
                    success=False,
                    error_code="START_FAILED",
                    message=str(e),
                )

    p = Path(target)
    if p.is_file():
        try:
            if sys.platform == "win32":
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return TaskResult(action=task.action, success=True, message=f"Opened file {p}.")
        except OSError as e:
            return TaskResult(
                action=task.action,
                success=False,
                error_code="START_FAILED",
                message=str(e),
            )

    if sys.platform == "win32":
        for candidate in (target, f"{target}.exe"):
            exe = shutil.which(candidate)
            if exe:
                try:
                    subprocess.Popen([exe], close_fds=True)
                    return TaskResult(
                        action=task.action,
                        success=True,
                        message=f"Started {exe}.",
                    )
                except OSError as e:
                    return TaskResult(
                        action=task.action,
                        success=False,
                        error_code="START_FAILED",
                        message=str(e),
                    )
        if _windows_shell_open_no_ui(target):
            return TaskResult(
                action=task.action,
                success=True,
                message=f"Launched via shell: {target}.",
            )
        return TaskResult(
            action=task.action,
            success=False,
            error_code="START_FAILED",
            message=(
                "Windows could not find or open this program. "
                "Check the spelling, PATH, or add it under apps in the allowlist YAML."
            ),
        )

    if sys.platform == "darwin":
        try:
            subprocess.Popen(["open", "-a", target])
            return TaskResult(action=task.action, success=True, message=f"Opened app {target}.")
        except OSError as e:
            return TaskResult(
                action=task.action,
                success=False,
                error_code="START_FAILED",
                message=str(e),
            )

    exe = shutil.which(target)
    if exe:
        try:
            subprocess.Popen([exe])
            return TaskResult(action=task.action, success=True, message=f"Started {exe}.")
        except OSError as e:
            return TaskResult(
                action=task.action,
                success=False,
                error_code="START_FAILED",
                message=str(e),
            )

    return TaskResult(
        action=task.action,
        success=False,
        error_code="START_FAILED",
        message="Could not resolve app name to an executable on this platform.",
    )
