# Phase 2 — Executor (Desktop)

**Objective:** Build the desktop agent that receives structured commands from the backend (or local test harness) and performs real actions on the OS, returning clear status and errors.

## Tech stack

| Layer | Technology |
|--------|------------|
| **Runtime** | Python 3.12+ (keeps parity with `backend/` and shared Pydantic types) |
| **Local API** | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn (HTTPS optional later) — accepts JSON commands from Phase 1 schema |
| **OS automation** | [PyAutoGUI](https://pyautogui.readthedocs.io/) or [pynput](https://pynput.readthedocs.io/) for mouse/keyboard; `subprocess` / `os.startfile` (Windows) / `open` (macOS) for launching apps |
| **Windows extras** | [pywin32](https://github.com/mhammond/pywin32) only if needed for shell verbs, window focus, or UAC-adjacent flows |
| **Paths & safety** | `pathlib`; allowlist config (YAML/TOML) for dev |
| **Browser (stub)** | Placeholder for Phase 6 — optional early hook: [Playwright](https://playwright.dev/python/) minimal install |
| **Packaging** | `requirements.txt` or [uv](https://github.com/astral-sh/uv) lockfile; optional PyInstaller later for a single `.exe` |

The executor does **not** run Ollama; it only executes structured commands. No LLM on this node unless you add a local helper later.

## Scope

- **Transport:** local API, WebSocket, or queue (exact choice TBD); must accept the shared command schema from Phase 1.
- **Actions (initial):**
  - Open applications by name or path where feasible.
  - Basic file/folder operations as defined by schema.
  - Hooks for browser automation and input simulation (can start minimal, expand in Phase 6).
- **Safety:** confirm destructive operations where needed; configurable allowlists for paths/apps in dev.
- **Feedback:** structured result payload (success, error code, message, optional artifacts).

## Out of scope (this phase)

- Full backend integration (Phase 3).
- Flutter and web controllers (Phase 4).
- Long-term memory (Phase 5).

## Deliverables

1. Runnable **executor** package with configuration for environment (OS paths, permissions).
2. **Action handlers** for the first supported intents (e.g. `OPEN_APP`, simple `OPEN_PATH`).
3. **Local tests** or manual test script proving commands work on a dev machine.
4. **Documentation** for running the executor and supported commands.

## Success criteria

- From a test client, a structured command reliably triggers the expected OS behavior on the target platform(s) you support first (e.g. Windows).
- Failures are reported in-band (no silent crashes) with actionable messages.

## Dependencies

- Phase 1 command schema stable enough to implement against.

## Risks / notes

- OS differences (Windows vs macOS vs Linux): pick one primary OS for v1 if needed.
- Security: executor is high-privilege; design for authentication with backend early in Phase 3.
