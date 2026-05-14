# Jarvis Desktop Controller

Electron + React desktop app that hides manual terminal setup and runs Jarvis services from one UI.

## What it does

- Starts and stops the API services plus the optional CLI tester:
  - `py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
  - `py -m uvicorn executor.app.main:app --host 127.0.0.1 --port 8001`
  - `py backend/cli.py` (interactive REPL; not required for chat or health badges)
- Sets `PYTHONPATH` to the repository root for each launched process.
- Streams process logs into the app (service log panel).
- Shows backend and executor health checks.
- Provides a chat console that calls backend `/api/interact`.
- Uses backend `/api/tts` (Piper) for speak-mode assistant playback.

## Prerequisites

- Node.js 20+
- Python launcher `py` on PATH
- Backend and executor Python dependencies already installed from repo root:

```powershell
py -m pip install -r backend/requirements.txt
py -m pip install -r executor/requirements.txt
```

### Offline speech-to-text (faster-whisper)

The desktop app records microphone audio locally and sends WAV to backend `/api/transcribe`. The backend uses **faster-whisper**; the first run downloads the configured model (default size `small`). Override with `STT_WHISPER_MODEL_SIZE` or `STT_WHISPER_MODEL_PATH` in `.env`.

### Text-to-speech (Piper)

Place a Piper `.onnx` voice and optional `.onnx.json` next to each other. Default path in backend config:

`backend/models/piper/en_US-lessac-medium.onnx`

Override with `TTS_PIPER_MODEL_PATH` / `TTS_PIPER_CONFIG_PATH` in `.env` if needed.

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
