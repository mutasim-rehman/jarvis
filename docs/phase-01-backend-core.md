# Phase 1 — Backend Core

**Objective:** Establish the AI “brain”: turn natural language into structured intents and commands, with a clear API surface for later executor and controller integration.

## Tech stack

| Layer | Technology |
|--------|------------|
| **Runtime** | Python 3.12+ |
| **API** | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| **Validation / shared models** | [Pydantic v2](https://docs.pydantic.dev/) (aligned with `shared/` schemas; OpenAPI export for clients) |
| **Chat & NLP (primary)** | [Hugging Face Spaces](https://huggingface.co/spaces) (API-first chatbot provider; configurable Space ID and endpoint) |
| **HF Space client** | [gradio_client](https://www.gradio.app/docs/python-client/introduction) (calls Space APIs such as `/respond`) |
| **Local fallback (optional)** | [Ollama](https://ollama.com/) for explicit local fallback when remote provider is unavailable |
| **Prompting** | Structured-output prompts (JSON in response) + optional few-shot examples; fallback regex/heuristics for critical intents if the model fails validation |
| **Config** | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — `OLLAMA_BASE_URL`, model name, API host/port |
| **Testing** | [pytest](https://pytest.org/) + [httpx ASGI](https://www.python-httpx.org/advanced/#asgi-application) for API tests |

Primary chatbot runs via Hugging Face Space API; Ollama can remain available locally as an explicit fallback path.

## Scope

- Natural language → structured **intent** (e.g. `OPEN_APP`, `OPEN_PATH`, extensible enum or string taxonomy).
- **Command generation:** map intent + slots (targets, modifiers) into a stable JSON schema (aligned with `shared/`).
- **Routing logic (stub):** decide *what kind* of downstream action is needed (e.g. “desktop execution” vs “informational only”) even before a real executor exists.
- **APIs (minimal):** e.g. health, chat or “parse” endpoint that accepts text and returns structured command preview (execution can be mocked).
- **Auth:** optional stub or “dev mode” token; full auth can harden in Phase 3+.

## Out of scope (this phase)

- Real OS execution (Phase 2).
- Persistent user memory (Phase 5).
- Mobile/desktop UI (Phase 4).

## Deliverables

1. **Intent model** documented and implemented (types in `shared/`, consumed by `backend/`).
2. **Parser path:** string in → intent + normalized targets (e.g. app name, path hints).
3. **REST (or equivalent) API** returning structured commands suitable for a future executor.
4. **Examples** in code or tests: e.g. *"open chrome"* → `{ intent: OPEN_APP, target: "chrome" }`.

## Success criteria

- Given a small set of test phrases, the backend returns consistent, valid structured output.
- Schema is versioned or namespaced so executor and controllers can depend on it safely.

## Dependencies

- None (foundation phase).

## Risks / notes

- Prefer a small, extensible intent set over premature coverage of every command type.
- Keep latency and error shapes predictable for voice and chat clients later.
