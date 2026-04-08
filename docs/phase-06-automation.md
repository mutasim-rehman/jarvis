# Phase 6 — Automation & Multi-Step Workflows

**Objective:** Support **multi-step** tasks that chain executor actions with optional branching (e.g. *"do my assignment"* → open LMS → download → open folder → launch IDE).

## Tech stack

| Layer | Technology |
|--------|------------|
| **Workflow definitions** | YAML or JSON in `shared/` — validated by Pydantic models; version field per workflow |
| **Orchestration** | Python **async** step runner in `backend/` (or small dedicated worker process) — calls executor HTTP per step; state machine in code |
| **Planning / NL → workflow** | **Ollama** (`llama3.2` / `llama3.3`) to map user goal → workflow id + parameters; validated against allowed workflow catalog (guardrails) |
| **Browser automation** | [Playwright](https://playwright.dev/python/) in **executor** (Python) for reliable browser steps |
| **Streaming progress** | SSE ([FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)) or WebSocket to controllers |
| **Idempotency** | Step ids + optional checkpoint file in user data dir for resume (stretch) |

## Scope

- **Workflow representation:** DAG or ordered steps with conditions; store in `shared/` as a durable format.
- **Orchestration:** backend or a dedicated worker expands one high-level intent into steps; executor runs steps with checkpoints and failure handling.
- **Browser automation:** integrate with executor capabilities for web flows (login flows may need user assistance — document limitations).
- **Idempotency and resume:** optional partial resume after failure (stretch goal).

## Out of scope (initial cut)

- Fully unattended logins to arbitrary third-party sites (security and ToS constraints).

## Deliverables

1. **Workflow definition format** and at least one **reference workflow** implemented end-to-end.
2. **Executor extensions** for steps not covered in Phase 2 (e.g. scripted browser actions, chained `OPEN_APP`).
3. **Observability:** step-level status in API responses or streaming events for controllers.

## Success criteria

- One **moderate** demo from the product brief works reliably in a controlled environment: e.g. open a known folder and launch a configured IDE.
- Failures at step *n* produce a clear message and do not leave orphan processes without documentation.

## Dependencies

- Phase 2–3 (executor + integration); Phase 5 helps for “my assignment” style shortcuts.

## Risks / notes

- Fragile selectors for web automation — prefer stable hooks or user-configured bookmarks.
- Rate limits and CAPTCHAs: plan for human-in-the-loop when automation cannot proceed.
