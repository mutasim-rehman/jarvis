# Phase 3 — Integration (Backend ↔ Executor)

**Objective:** Connect the backend to the executor so that a single pipeline — text in → parse → execute → status out — works end-to-end on a local or staging network.

## Tech stack

| Layer | Technology |
|--------|------------|
| **Backend → executor** | [httpx](https://www.python-httpx.org/) async client from FastAPI routes; configurable `EXECUTOR_BASE_URL` |
| **Realtime (optional)** | [WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) for streaming status to clients later; Phase 3 can stay request/response |
| **Auth between services** | Shared secret in `Authorization: Bearer` or `X-API-Key`; rotate via env; document mTLS as upgrade path |
| **Session / correlation** | UUID (`uuid4`) per request; propagate in JSON body and logs |
| **Retries** | [tenacity](https://github.com/jd/tenacity) or httpx built-in retries for executor calls |
| **Container (optional)** | [Docker](https://www.docker.com/) Compose: services `backend`, `executor` (+ optional `ollama` for local fallback) |
| **Chat path** | Backend uses **Hugging Face Space API** for NL → intent; local Ollama can be selected as fallback when HF is unavailable |

## Scope

- **Wire protocol:** backend forwards structured commands to the executor; executor returns results to the backend (and optionally to the client in one response).
- **Identity / trust:** minimal auth between backend and executor (API keys, mTLS, or signed tokens); document threat model for LAN vs internet.
- **Session or job model:** correlate a user request with an execution id for logging and debugging.
- **Error propagation:** backend maps executor errors to API responses without leaking sensitive paths in production.
- **Configuration:** base URLs, timeouts, retries for flaky networks.

## Out of scope (this phase)

- Polished mobile/desktop apps (Phase 4) — a CLI or simple HTTP test client is enough to validate.
- Hub marketing site (Phase 7).

## Deliverables

1. **End-to-end path:** natural language → backend → executor → OS action → response to caller.
2. **Integration tests** or repeatable manual checklist for core flows.
3. **Deployment notes:** how to run backend + executor together (docker-compose or scripts optional).

## Success criteria

- Example: *"open chrome"* from an API client results in Chrome launching and a success payload returned.
- Timeouts and connection failures are handled without hanging the API.

## Dependencies

- Phase 1 (backend parsing and APIs).
- Phase 2 (executor implementing the schema).

## Risks / notes

- NAT/firewall: if executor is only on LAN, document discovery or pairing for mobile (Phase 4).
