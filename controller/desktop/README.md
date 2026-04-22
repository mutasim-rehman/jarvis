# Jarvis Desktop Controller

Electron + React desktop app that hides manual terminal setup and runs Jarvis services from one UI.

## What it does

- Starts and stops the three core processes:
  - `py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
  - `py -m uvicorn executor.app.main:app --host 127.0.0.1 --port 8001`
  - `py backend/cli.py`
- Sets `PYTHONPATH` to the repository root for each launched process.
- Streams process logs into the app.
- Shows backend and executor health checks.
- Provides a chat console that calls backend `/api/interact`.

## Prerequisites

- Node.js 20+
- Python launcher `py` on PATH
- Backend and executor Python dependencies already installed from repo root:

```powershell
py -m pip install -r backend/requirements.txt
py -m pip install -r executor/requirements.txt
```

## Run in development

From `controller/desktop`:

```powershell
npm install
npm run dev
```

This starts Vite and Electron together, then opens the desktop UI.

## Build UI bundle

```powershell
npm run build
```

Note: packaging installers is not added yet in this first scaffold; this phase focuses on local desktop control workflow.
