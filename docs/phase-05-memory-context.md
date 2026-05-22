# Phase 5 — Memory, Context Awareness & Adaptive Intelligence

**Objective:** Evolve JARVIS from a purely command-based system into a **context-aware assistant** that understands intent, learns user preferences, and adapts its behavior over time—moving beyond literal command execution toward responses aligned with meaning, environment, and user habits.

## Vision

In this phase, JARVIS begins to **interpret meaning, environment, and user habits** to decide the most appropriate response. Instead of executing fixed mappings, the system uses stored context, real-time signals, and preference data (including explicit settings from **Phase 4.5**) to behave like an assistant that understands context, intention, and personal preference in a meaningful way.

Overall, Phase 5 transforms JARVIS into a **learning, adaptive assistant** that gradually develops interaction modes (e.g. focus, curiosity, entertainment) shaped by the user’s working style, interests, and habits.

## Core capabilities

### Intent-based interpretation

JARVIS no longer treats inputs like *"play something interesting"* or *"play music"* as fixed search queries. It analyzes the **meaning** behind the request and maps it to a relevant **category of content** or action.

| Example utterance | Interpretation | Likely outcome |
|-------------------|----------------|----------------|
| *"Play something interesting"* | Curiosity-driven | Trending trailers, mystery content, educational videos |
| *"Play music while I debug"* | Focus-oriented scenario | Ambient, lo-fi, or cinematic music—not random tracks |
| *"Continue work"* | Session continuity | Last project path, IDE, or workspace from memory |

### Long-term preference memory

JARVIS stores and continuously updates information about user habits, for example:

- Preferred music genres during different activities
- Types of videos the user tends to engage with
- Behavioral patterns in work vs. relaxation contexts

Over time, the system builds a **dynamic profile** that improves content and action recommendations. Explicit onboarding preferences from Phase 4.5 seed this profile; Phase 5 refines it from behavior.

### Context detection

Real-time signals inform the user’s current state, such as:

- **Current activity** (e.g. coding, idle, browsing)
- **Time of day**
- **Recent interaction history**

Examples: late-night sessions may favor calm or low-energy content; daytime productivity sessions may prioritize focus-enhancing outputs.

### Adaptive response engine

Outputs are selected based on **relevance** and **suitability** for the current state:

- Balance **familiarity** with **novelty**—avoid repetition while respecting preferences
- Align vague or ambiguous commands with the best mode for the moment

### Behavioral evolution

Over time, JARVIS develops distinct **interaction modes** (e.g. focus mode, curiosity mode, entertainment mode). Each mode influences how the assistant responds to vague commands, gradually forming a personality that adapts to the user’s style.

## Tech stack

| Layer | Technology |
|--------|------------|
| **API** | Existing FastAPI backend; routes under `/memory`, `/context`, and planner hooks |
| **ORM & DB** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (+ optional [SQLModel](https://sqlmodel.tiangolo.com/)) |
| **Database** | [SQLite](https://www.sqlite.org/) for single-user/dev; [PostgreSQL](https://www.postgresql.org/) for multi-user or hosted deploy |
| **Migrations** | [Alembic](https://alembic.sqlalchemy.org/) |
| **User identity** | Phase 4.5 user accounts and preference records |
| **Context injection** | Before planner/LLM call: merge user profile, activity signals, and recent session summary into a compact context block |
| **Intent & slots** | Extend orchestrator/planner to support semantic categories (focus, curiosity, entertainment) not only literal targets |
| **Activity signals** | Desktop executor or controller hooks (active window, idle time); optional calendar/time rules |
| **Embeddings (optional later)** | [Ollama embeddings API](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings) or remote embeddings for RAG over notes and history |
| **Encryption** | [cryptography](https://cryptography.io/) (Fernet) for sensitive memory fields at rest |

## Scope

- **Storage model:** per-user entities—projects, last-opened paths, preferred apps, session summaries, taste vectors, and mode/state (focus vs. curiosity).
- **Retrieval:** backend merges stored context, Phase 4.5 preferences, and current utterance before intent resolution (key-value + rules first; optional RAG later).
- **Semantic routing:** map vague media/work commands to categories and executor/catalog actions using profile + context.
- **Mode selection:** lightweight state machine or tagged “current mode” influenced by activity and history.
- **Privacy:** encryption at rest where appropriate; clear retention, export, and delete flows tied to user account.
- **APIs:** CRUD or sync for memory items the user allows; context snapshot for debugging (dev).

## Out of scope (this phase)

- Fully autonomous multi-step workflows (Phase 6)—memory and modes should make those easier later.
- Mobile and Raspberry Pi–specific context UX (complete when Phase 4 mobile/Pi clients are finished).
- Replacing all rule-based safety guardrails with pure LLM judgment.

## Deliverables

1. **Schema** for memory, context signals, and interaction modes in `shared/` + persistence in `backend/`.
2. **Intent-based interpretation path** in planner/orchestrator with documented examples (music, video, continue-work).
3. **Context detection** pipeline (minimal viable signals: time of day + recent commands + optional desktop activity).
4. **Adaptive response rules** (or model-guided policy) balancing novelty vs. preference.
5. **Integration** with Phase 4.5 user id and preference summary on every relevant request.
6. **User controls:** view/clear relevant memory and reset learned taste (desktop UI acceptable).

## Success criteria

- At least **three** context-aware scenarios work end-to-end, e.g.:
  - *"Continue work"* → stored project path opened via executor
  - *"Play music while I debug"* → focus-biased music selection
  - *"Play something interesting"* → curiosity-biased content category
- User can **inspect and reset** remembered state; no unbounded silent growth.
- Behavior measurably shifts when explicit Phase 4.5 preferences or learned habits change.

## Dependencies

- Phase 3 (integrated pipeline).
- **Phase 4.5** (user accounts and explicit preferences)—required for per-user memory and onboarding seed data.
- Phase 4 **desktop** (or equivalent client) for memory controls; mobile/Pi not blocking.

## Execution order (project plan)

Phase 5 is **in progress next** after Phase 4.5. Phase 4 **mobile (Flutter)** and **Raspberry Pi Zero 2W** clients are **deferred to the end** of Phase 4; desktop controller and backend work proceed first. See [phase-04-controller.md](phase-04-controller.md).

## Risks / notes

- Avoid storing secrets in plain text; separate secrets from “memory” blobs.
- Conflicts when multiple devices update context—define a simple policy (e.g. last-write-wins with timestamps).
- Cold-start quality depends on Phase 4.5 onboarding and optional Spotify/YouTube import.
- Guard against over-personalization loops (echo chamber)—explicit novelty factor in adaptive engine.
