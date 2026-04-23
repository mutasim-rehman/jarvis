# JARVIS

JARVIS is a distributed AI system that turns natural language (voice or text) into structured intent and executes real tasks on a desktop. It is designed to go beyond chat: **understand → decide → execute** across mobile and desktop clients.

## Architecture

```
jarvis/
├── backend/     # AI brain + APIs (intent, routing, execution requests)
├── executor/    # Desktop agent (OS actions, automation)
├── controller/  # User interface — mobile + desktop subfolders
├── hub/         # Product website, demos, optional dashboard
├── shared/      # Schemas, intent formats, shared utilities
└── docs/        # Phase plans and technical notes
```

**Pipeline:** User → Controller → Backend → Executor → Action

Both mobile and desktop controllers use the same pipeline into the backend and executor.

## Components (summary)

| Area | Role |
|------|------|
| **Backend** | NLP → intent, command generation, routing, APIs (chat, execute, auth); memory later |
| **Executor** | Receives commands; opens apps, files, browser automation, input simulation; returns status |
| **Controller** | **Mobile (Flutter):** voice in/out, talks to backend. **Desktop:** chat, commands, monitoring |
| **Hub** | Landing, features, demos, optional dashboard |
| **Shared** | Command schemas, intent formats, constants |

Example flow: *"open chrome"* → `{ intent: OPEN_APP, target: chrome }` → executor launches Chrome.

## Phases

Work is staged in seven phases. Each phase has a dedicated plan under [`docs/`](docs/).

| Phase | Focus | Doc |
|-------|--------|-----|
| 1 | Backend core (NLP → intent, command structuring) | [phase-01-backend-core.md](docs/phase-01-backend-core.md) |
| 2 | Executor (actions, local testing) | [phase-02-executor.md](docs/phase-02-executor.md) |
| 3 | Integration (backend ↔ executor, end-to-end) | [phase-03-integration.md](docs/phase-03-integration.md) |
| 4 | Controller (mobile voice + desktop UI) | [phase-04-controller.md](docs/phase-04-controller.md) |
| 5 | Memory & context | [phase-05-memory-context.md](docs/phase-05-memory-context.md) |
| 6 | Multi-step automation & workflows | [phase-06-automation.md](docs/phase-06-automation.md) |
| 7 | Hub (website + demos) | [phase-07-hub.md](docs/phase-07-hub.md) |

## Example scenarios

- **Basic:** *"open chrome"* → app opens  
- **Moderate:** *"open DSA folder and code"* → folder + IDE  
- **Advanced:** *"start my assignment"* → LMS → download → setup → code  
- **Context-aware (later):** *"continue work"* → resumes last session  
- **Mobile control:** phone issues command → PC executes remotely  

## Goal

Build a system that **understands**, **decides**, **executes**, and **assists continuously** — an execution system, not a chatbot.

For scope, milestones, and deliverables per stage, see the phase documents in `docs/`.

## Model Attributions

- Voice model inspiration and local clone: [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
- Local path used in this project: `backend/models/Kokoro-82M`
- Runtime usage: desktop assistant voice is served via backend `/api/tts` using Kokoro-82M (with fallback voice if unavailable).
