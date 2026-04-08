# Phase 5 — Memory & Context

**Objective:** Let JARVIS remember projects, habits, and recent sessions so commands become **context-aware** (e.g. *"continue project"* opens the last workspace).

## Tech stack

| Layer | Technology |
|--------|------------|
| **API** | Existing FastAPI backend; new routes under `/memory` or `/context` |
| **ORM & DB** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [SQLModel](https://sqlmodel.tiangolo.com/) (optional) or raw SQLAlchemy |
| **Database** | [SQLite](https://www.sqlite.org/) for single-user/dev; [PostgreSQL](https://www.postgresql.org/) for multi-user or hosted deploy |
| **Migrations** | [Alembic](https://alembic.sqlalchemy.org/) |
| **Context injection** | Before Ollama call: fetch relevant rows (last project, paths) and prepend a compact system/context block; still **Ollama** `llama3.2` / `llama3.3` for decoding |
| **Embeddings (optional later)** | [Ollama embeddings API](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings) with `nomic-embed-text` or similar for RAG over notes |
| **Encryption** | [cryptography](https://cryptography.io/) (Fernet) for sensitive fields at rest if needed |

## Scope

- **Storage model:** per-user (or per-device) entities such as projects, last-opened paths, preferred apps, and session summaries.
- **Retrieval:** backend merges stored context with the current utterance before intent resolution (RAG, simple key-value, or hybrid — choose based on stack).
- **Privacy:** encryption at rest where appropriate; clear retention and delete flows.
- **APIs:** CRUD or sync endpoints for “memory” items the user allows.

## Out of scope (this phase)

- Fully autonomous multi-step workflows (Phase 6) — but memory should make those easier later.

## Deliverables

1. **Schema** for memory objects in `shared/` + persistence layer in `backend/`.
2. **Integration** with intent parsing so short prompts resolve using context (documented examples).
3. **User controls:** view/clear relevant memory from desktop or mobile (minimal UI acceptable).

## Success criteria

- At least one **context-aware** scenario works: e.g. *"continue work"* resolves to a stored project path and executor opens it.
- No unbounded growth of silent state: user can see or reset what is remembered.

## Dependencies

- Phase 3 or 4 (depending on whether you expose memory UI only on desktop first).

## Risks / notes

- Avoid storing secrets in plain text; separate secrets from “memory” blobs.
- Conflicts when multiple devices update context — define a simple conflict policy (last-write-wins vs merge).
