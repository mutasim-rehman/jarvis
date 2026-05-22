# Phase 4.5 — User Accounts & Preference Initialization

**Objective:** Introduce a structured user account system and explicit preference capture so personalization and memory-driven intelligence (Phase 5) have a stable foundation from day one—not only from implicit learning over time.

## Vision

In Phase 4.5, JARVIS establishes the **identity and preference layer** that all later adaptive behavior depends on. Users sign in with familiar providers or a simple email account, complete onboarding, and shape how JARVIS should behave before the system relies on long-term habit inference alone.

This phase is designed to feed directly into **Phase 5 (Memory, Context Awareness & Adaptive Intelligence)**, enabling JARVIS to move from a generic assistant toward a deeply personalized, adaptive system from the very beginning.

## Tech stack

| Layer | Technology |
|--------|------------|
| **API** | Existing FastAPI backend; new routes under `/auth`, `/users`, `/preferences` |
| **ORM & DB** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (+ optional [SQLModel](https://sqlmodel.tiangolo.com/)) |
| **Database** | [SQLite](https://www.sqlite.org/) for dev/single-user; [PostgreSQL](https://www.postgresql.org/) for multi-user or hosted deploy |
| **Migrations** | [Alembic](https://alembic.sqlalchemy.org/) |
| **Sign-in** | OAuth 2.0 / OpenID Connect — [Google](https://developers.google.com/identity), [GitHub](https://docs.github.com/en/apps/oauth-apps); optional email/password or magic-link (product choice) |
| **Sessions** | Signed JWT or server-side sessions; secure HTTP-only cookies for web desktop |
| **Preference schema** | Pydantic models in `shared/` — personality sliders, content defaults, integration toggles |
| **External taste data (optional)** | Extend existing executor OAuth patterns ([Spotify](https://developer.spotify.com/documentation/web-api), YouTube Data API or export/import for watch history / watch-later) |
| **Secrets** | Env-based client IDs; tokens stored per-user via encrypted or filesystem-backed store (align with `executor/app/auth/token_store` patterns where integrations run on desktop) |

## Scope

### User accounts

- **Authentication:** sign in with Google, GitHub, and/or a simple email-based account.
- **User record:** stable user id linked to profile, preferences, and (later) Phase 5 memory entities.
- **Session management:** secure login/logout; token refresh where OAuth providers require it.
- **Device registry:** unique **device ID** per client (phone, Raspberry Pi, laptop); same user ID across devices. Pairing and remote-control authorization are specified in [phase-04-controller.md](phase-04-controller.md) and [controller/mobile/README.md](../controller/mobile/README.md).

### Onboarding & explicit preferences

During onboarding, users configure how they want JARVIS to behave, including:

- **Personality traits:** configurable levels such as honesty, humor, formality, and conversational style.
- **Assistant defaults:** tone, verbosity, and how aggressively to suggest actions vs. answer only.
- **Initial content hints:** optional genres, interests, or “do not suggest” categories to seed recommendations.

These explicit settings shape the assistant **intentionally from the start** rather than relying solely on implicit learning in Phase 5.

### Optional external data sources

Users may **opt in** to grant JARVIS access to external taste and history signals, for example:

- **Spotify:** liked songs, saved albums, or listening profile (read-only scopes).
- **YouTube:** watch history or watch-later lists (via API or user-export flow where API access is limited).

This integration is **optional** and helps build a more accurate understanding of taste, interests, and consumption patterns before adaptive memory fully matures.

### API & integration surface

- CRUD for user profile and preference documents.
- Endpoints or flows to connect/disconnect OAuth integrations per user.
- Backend passes preference summary into chat/orchestrator context blocks (compact system preamble).

## Out of scope (this phase)

- Full long-term habit learning and context detection (Phase 5).
- Intent-based interpretation of vague commands (Phase 5).
- Mobile app and Raspberry Pi controller UI for account management (deferred with Phase 4 mobile/Pi—desktop or web onboarding is sufficient initially).
- Storing third-party passwords; only OAuth or official APIs/exports.

## Deliverables

1. **User & preference schema** in `shared/` + persistence in `backend/`.
2. **Auth flows** for at least two providers (e.g. Google + GitHub) and a documented path for email-based sign-in if included.
3. **Onboarding API/UI (minimal):** capture personality and behavior preferences; persist per user.
4. **Optional integrations:** Spotify and/or YouTube connection flows with clear consent and disconnect.
5. **Context injection hook:** preference summary available to planner/chat paths before Phase 5 memory is live.
6. **Documentation:** env vars, OAuth app setup, and privacy notes (what is stored, retention, delete account).

## Success criteria

- A new user can **sign in**, complete **onboarding**, and have preferences affect at least one visible behavior (e.g. chat tone or default content bias).
- Optional Spotify/YouTube connection works in a controlled demo and can be revoked without orphan tokens.
- Preference and account data are **scoped per user** and ready to link to Phase 5 memory entities.

## Dependencies

- Phase 3 (stable integrated pipeline).
- Desktop controller (Phase 4 partial) or minimal web onboarding UI—mobile/Pi clients not required for this phase.

## Relationship to other phases

| Phase | Role |
|-------|------|
| **4 (partial)** | Desktop (or web) client for sign-in and onboarding UI |
| **4 (deferred)** | Mobile and Raspberry Pi account UX completed when those clients are finished |
| **5** | Consumes accounts + explicit preferences; adds long-term memory, context detection, and adaptive responses |

## Risks / notes

- OAuth redirect URLs differ per environment (local vs production)—document clearly.
- YouTube history access may be restricted; support export-based import as fallback.
- Keep personality and preference payloads **versioned** so Phase 5 can evolve fields without breaking existing users.
- Align desktop executor token storage with per-user identity when multiple users share one machine (future consideration).
