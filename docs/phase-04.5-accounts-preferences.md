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
| **Database** | [Supabase](https://supabase.com/) Postgres (`profiles`, `preferences`, `pairing_sessions`, `device_links`, `tasks`) via `DATABASE_URL` |
| **Auth** | Supabase Auth (Google, GitHub); backend verifies `Authorization: Bearer` with `SUPABASE_JWT_SECRET` |
| **Sign-in UI** | Desktop Electron (`controller/desktop`) and hub (`hub/`) |
| **Sessions** | Supabase access JWT; optional `X-Device-Id` header per client |
| **Preference schema** | Pydantic models in `shared/` — personality sliders, content defaults, integration toggles |
| **Personality profile (optional import)** | Versioned `PersonalityProfileV1` JSON — user-filled via external LLM (ChatGPT, Gemini, etc.) and pasted/uploaded at onboarding |
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
- **Optional personality import:** structured JSON filled by the user’s usual LLM (ChatGPT, Gemini, etc.)—see [Optional enrichment steps](#optional-enrichment-steps-all-skippable).

These explicit settings shape the assistant **intentionally from the start** rather than relying solely on implicit learning in Phase 5.

### Optional enrichment steps (all skippable)

Onboarding may offer several **optional** steps. Users can skip any of them and still complete sign-in; each step only improves the initial personalization seed.

#### External taste & history (OAuth / import)

Users may **opt in** to grant JARVIS access to external taste and history signals, for example:

- **Spotify:** liked songs, saved albums, or listening profile (read-only scopes).
- **YouTube:** watch history or watch-later lists (via API or user-export flow where API access is limited).

These integrations help build a more accurate understanding of taste, interests, and consumption patterns before adaptive memory fully matures.

#### AI-assisted personality profile (import)

Users who want a **richer, more accurate personality baseline** than sliders alone can complete an optional import step:

1. During onboarding, JARVIS presents a **personality profile JSON template** (schema below).
2. The user copies the template into **ChatGPT, Gemini, or whichever LLM they use most**—the model that already knows them from prior conversations.
3. The user asks that model to **fill every field** based on what it knows about them (values, tone, contradictions, social style, etc.).
4. The user pastes the completed JSON back into JARVIS (file upload or paste field); the backend validates, normalizes, and stores it as the user’s **personality document** alongside explicit slider preferences.

This step is **optional**, same as Spotify likes and YouTube watch history / watch-later. It does not replace onboarding sliders; it **supplements** them with a structured, LLM-inferred portrait that Phase 5 memory can refine over time.

**UX copy (guidance for users):**

> “For the most accurate personality, copy this template into the AI chat you use most (ChatGPT, Gemini, etc.) and ask: *Fill this JSON about me based on everything you know about me. Be specific and honest, including contradictions.* Then paste the result here.”

**Privacy:** Treat imported personality JSON like other preference data—per-user, revocable, deletable with account; never send the raw document to third parties except the user’s own chosen LLM during this step.

##### Personality profile schema (import template)

Stored in `shared/` as a versioned Pydantic model (e.g. `PersonalityProfileV1`). Empty strings and empty arrays are valid on import; backend may reject malformed JSON or unknown top-level keys depending on validation policy.

```json
{
  "name": "",
  "profile": "",
  "personality": "",
  "archetype": "",

  "philosophy": {
    "worldview": "",
    "view_on_meaning": "",
    "view_on_success": "",
    "view_on_failure": "",
    "view_on_relationships": "",
    "view_on_self": "",
    "view_on_growth": "",
    "contradictory_beliefs": []
  },

  "beliefs": [],
  "values": [],
  "fears": [],
  "desires": [],

  "emotional_baseline": "",
  "emotional_tendencies": [],
  "triggers": [],

  "communication": {
    "tone": "",
    "style": "",
    "verbosity": "",
    "formality": "",
    "emotional_expression": "",
    "humor": "",
    "quirks": [],
    "speech_patterns": [],
    "conversation_habits": []
  },

  "thinking": {
    "decision_style": "",
    "openness": "",
    "reactivity": "",
    "conflict_handling": "",
    "persuasion_style": "",
    "overthinking": "",
    "risk_tolerance": ""
  },

  "social_behavior": {
    "towards_strangers": "",
    "towards_friends": "",
    "towards_authority": "",
    "towards_conflict": "",
    "trust_building": "",
    "attachment_style": ""
  },

  "behavioral_patterns": [],
  "contradictions": [],
  "biases": [],
  "hidden_traits": []
}
```

**Context injection:** When present, a **compressed summary** of this document (not the full JSON on every turn) is merged into the planner/chat system preamble with explicit slider preferences and optional taste signals.

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
5. **Optional personality import:** onboarding step to download/copy schema, instructions for ChatGPT/Gemini fill, paste/upload + validate + persist.
6. **Context injection hook:** preference summary (sliders + optional personality summary + taste signals) available to planner/chat paths before Phase 5 memory is live.
7. **Documentation:** env vars, OAuth app setup, personality-import instructions, and privacy notes (what is stored, retention, delete account).

## Success criteria

- A new user can **sign in**, complete **onboarding**, and have preferences affect at least one visible behavior (e.g. chat tone or default content bias).
- Optional Spotify/YouTube connection works in a controlled demo and can be revoked without orphan tokens.
- Optional personality import: user can skip; if completed, valid JSON is stored and influences at least one visible behavior (e.g. tone or phrasing in chat).
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
- Keep personality and preference payloads **versioned** so Phase 5 can evolve fields without breaking existing users (including `PersonalityProfileV1` import schema).
- AI-filled personality JSON may be verbose—store full document but inject **summaries** into the planner to control token cost.
- Users may paste over-generated or hallucinated traits from external LLMs; onboarding should allow **review/edit** or re-import before locking.
- Align desktop executor token storage with per-user identity when multiple users share one machine (future consideration).

## Implementation (repo)

- Shared models: [`shared/preferences.py`](../shared/preferences.py)
- Backend: [`backend/app/routes/`](../backend/app/routes/), [`backend/app/db/`](../backend/app/db/), [`backend/app/auth/`](../backend/app/auth/)
- Preference context injection: [`backend/app/preferences_context.py`](../backend/app/preferences_context.py), orchestrator + chat paths
- Setup guide: [supabase-phase-4.5.md](supabase-phase-4.5.md)
- Env template: [`.env.example`](../.env.example) (`SUPABASE_*`, `DATABASE_URL`, `API_AUTH_MODE`)
