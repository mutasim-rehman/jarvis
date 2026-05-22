# JARVIS

JARVIS is a distributed AI system that turns natural language (voice or text) into structured intent and executes real tasks on a desktop. It is designed to go beyond chat: **understand → decide → execute** across mobile, desktop, and Raspberry Pi Zero 2W clients.

## Architecture

```
jarvis/
├── backend/     # AI brain + APIs (intent, routing, execution requests)
├── executor/    # Desktop agent (OS actions, automation)
├── controller/  # User interface — mobile + desktop + Raspberry Pi subfolders
├── hub/         # Product website, demos, optional dashboard
├── shared/      # Schemas, intent formats, shared utilities
└── docs/        # Phase plans and technical notes
```

**Pipeline:** User → Controller → Backend → Executor → Action

Mobile, desktop, and Raspberry Pi controllers use the same pipeline into the backend and executor.

## Components (summary)

| Area | Role |
|------|------|
| **Backend** | NLP → intent, command generation, routing, APIs (chat via Hugging Face Space, execute, auth); memory later |
| **Executor** | Receives commands; opens apps, files, browser automation, input simulation; returns status |
| **Controller** | **Mobile (Flutter):** voice in/out, talks to backend. **Desktop:** chat, commands, monitoring. **Raspberry Pi Zero 2W:** same behavior and backend contract as mobile |
| **Hub** | Landing, features, demos, optional dashboard |
| **Shared** | Command schemas, intent formats, constants |

Example flow: *"open chrome"* → `{ intent: OPEN_APP, target: chrome }` → executor launches Chrome.

## Phases

Work is staged in phases (including 4.5). Each phase has a dedicated plan under [`docs/`](docs/).

**Current focus:** Phase 4 **desktop** controller, then **Phase 4.5** (accounts & preferences) and **Phase 5** (memory & adaptive intelligence). Phase 4 **mobile** and **Raspberry Pi** clients are deferred to the end of Phase 4.

| Phase | Focus | Doc |
|-------|--------|-----|
| 1 | Backend core (NLP → intent, command structuring) | [phase-01-backend-core.md](docs/phase-01-backend-core.md) |
| 2 | Executor (actions, local testing) | [phase-02-executor.md](docs/phase-02-executor.md) |
| 3 | Integration (backend ↔ executor, end-to-end) | [phase-03-integration.md](docs/phase-03-integration.md) |
| 4 | Controller (desktop now; mobile + Pi later) | [phase-04-controller.md](docs/phase-04-controller.md) |
| 4.5 | User accounts & preference initialization | [phase-04.5-accounts-preferences.md](docs/phase-04.5-accounts-preferences.md) |
| 5 | Memory, context awareness & adaptive intelligence | [phase-05-memory-context.md](docs/phase-05-memory-context.md) |
| 6 | Multi-step automation & workflows | [phase-06-automation.md](docs/phase-06-automation.md) |
| 7 | Hub (website + demos) | [phase-07-hub.md](docs/phase-07-hub.md) |

## Example scenarios

- **Basic:** *"open chrome"* → app opens  
- **Moderate:** *"open DSA folder and code"* → folder + IDE  
- **Advanced:** *"start my assignment"* → LMS → download → setup → code  
- **Context-aware (later):** *"continue work"* → resumes last session  
- **Mobile / Pi control (Phase 4b):** same account on phone and laptop → QR pairing → phone sends command with target laptop ID → server verifies device link → PC executes remotely  

## Goal

Build a system that **understands**, **decides**, **executes**, and **assists continuously** — an execution system, not a chatbot.

For scope, milestones, and deliverables per stage, see the phase documents in `docs/`.

## Chat Provider Configuration

The backend chatbot provider is Hugging Face Space by default, with local Ollama available as an explicit fallback when selected by the user.

Environment variables (backend):

- `CHAT_PRIMARY_PROVIDER` (`huggingface` by default; can be `ollama`)
- `HF_SPACE_ID` (default: `mutasim-rehman/jarvis`)
- `HF_API_NAME` (default: `/respond`)
- `HF_TOKEN` (optional; only needed for private Spaces)
- `HF_MAX_TOKENS`, `HF_TEMPERATURE`, `HF_TOP_P`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (used for local fallback)

## Model Attributions

- **Speech-to-text:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper weights).
- **Speech synthesis:** [Piper](https://github.com/rhasspy/piper) neural voices; default voice path is under `backend/models/piper/` in backend settings.
