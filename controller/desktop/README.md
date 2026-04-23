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
- Uses backend `/api/tts` for Kokoro-82M voice output (with browser TTS fallback if unavailable).

## Prerequisites

- Node.js 20+
- Python launcher `py` on PATH
- Backend and executor Python dependencies already installed from repo root:

```powershell
py -m pip install -r backend/requirements.txt
py -m pip install -r executor/requirements.txt
```

### Offline speech-to-text model (Vosk)

The desktop app records microphone audio locally and sends WAV to backend `/api/transcribe`.
For offline transcription, download and extract an English Vosk model to:

`backend/models/vosk-model-small-en-us-0.15`

You can change this path with `STT_MODEL_PATH` in `.env`.

### Voice model attribution

- Selected Jarvis voice model source: [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
- Local clone path: `backend/models/Kokoro-82M`
- Credit: thanks to the Kokoro model authors/maintainers for the open release.

### Kokoro setup notes

- Install backend dependencies (includes `kokoro`):

```powershell
py -m pip install -r backend/requirements.txt
```

- Ensure model weights are present in your local clone:

```powershell
cd backend/models/Kokoro-82M
git lfs pull
```

- On Windows/Linux, Kokoro may require `espeak-ng` to be installed and available on PATH.
- Kokoro runtime currently requires **Python 3.12 or lower**. If your main env is Python 3.13, run backend in a Python 3.12 environment for Kokoro voice.

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
