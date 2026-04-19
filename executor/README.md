# JARVIS desktop executor (Phase 2)

Local FastAPI service that accepts the shared [`ActionCommand`](../shared/schema.py) shape (including `tasks`) and runs a small set of OS actions on this machine. It does **not** call an LLM.

## Requirements

- Python 3.12+
- Repo root on `PYTHONPATH` (see below)

Install dependencies:

```powershell
py -m pip install -r executor/requirements.txt
```

## Run the API

From the **repository root** (`jarvis/`):

```powershell
$env:PYTHONPATH = "$PWD"
py -m uvicorn executor.app.main:app --host 127.0.0.1 --port 8001
```

Or:

```powershell
$env:PYTHONPATH = "$PWD"
py executor/cli.py
```

Defaults: host `127.0.0.1`, port `8001`. Override with `EXECUTOR_API_HOST` and `EXECUTOR_API_PORT`.

## Endpoints

- `GET /health` — `{ "status": "ok", "schema_version": "..." }`
- `POST /api/run` — body: `RunCommandRequest` JSON (`{ "command": { ... } }`, see [`shared/schema.py`](../shared/schema.py)), response: `RunCommandResponse` with per-task `results`.

Optional auth (same pattern as the Phase 1 backend):

- `EXECUTOR_API_REQUIRE_AUTH=true`
- `EXECUTOR_API_DEV_TOKEN=<secret>`

Send header `X-API-Key: <secret>` on `/api/run`.

## Example request

```powershell
$body = @{
  command = @{
    intent = "OPEN_APP"
    target = "notepad"
    parameters = @{}
    tasks = $null
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri http://127.0.0.1:8001/api/run -Method Post -Body $body -ContentType "application/json"
```

With explicit tasks (multi-step):

```json
{
  "command": {
    "intent": "HANDLE_ASSIGNMENTS",
    "target": null,
    "parameters": {},
    "tasks": [
      { "action": "CREATE_FOLDER", "target": "assignments/latest" }
    ]
  }
}
```

If `tasks` is omitted or empty, a **single** task is synthesized from `intent` (e.g. `OPEN_WEBSITE` → `OPEN_URL`).

## Allowlist (YAML)

Set `EXECUTOR_ALLOWLIST_PATH` to a YAML file. Without it, the executor uses a single default root: `~/jarvis-executor-workspace` (created if missing).

```yaml
path_roots:
  - "C:/Users/you/Documents/jarvis-sandbox"
apps:
  chrome: "C:/Program Files/Google/Chrome/Application/chrome.exe"
url_aliases:
  gcr: "https://classroom.google.com"
```

- **`CREATE_FOLDER`**: relative targets are created under the **first** `path_root`; absolute paths must stay under one of the listed roots.
- **`OPEN_APP`**: optional `apps` map (lowercase keys); otherwise Windows uses `start`, macOS `open -a`, etc.
- **`OPEN_URL` / `OPEN_WEBSITE`**: full URLs, domains like `example.com`, or keys from `url_aliases`.

## Implemented actions

| Action | Behavior |
|--------|----------|
| `OPEN_APP` | Mapped exe, existing file, then `PATH` (`where`-style via `shutil.which`); on Windows, last resort is `ShellExecuteEx` with **no error popups** — failures return `START_FAILED` in JSON instead |
| `OPEN_URL`, `OPEN_WEBSITE` | `webbrowser.open` |
| `CREATE_FOLDER` | `mkdir -p` under allowlisted roots |

All other workflow actions return `success: false` with `error_code: NOT_IMPLEMENTED`.

## Security

This process can start programs and touch the filesystem. Treat it as **high privilege**. Use allowlists and enable API auth when exposed beyond localhost.

## Tests

From repo root:

```powershell
$env:PYTHONPATH = "$PWD"
py -m pytest executor/tests -q
```
