# Phase 4 — Controller (Mobile + Desktop + Raspberry Pi Zero 2W)

**Objective:** Provide user-facing clients that share the same backend → executor pipeline: **desktop** for chat/typed commands/monitoring (priority), **mobile** for voice-first control, and **Raspberry Pi Zero 2W** as a phone-like edge controller.

## Execution order (updated)

| Priority | Client | Status |
|----------|--------|--------|
| **Now** | Desktop (web/native) | Primary focus for Phase 4 work |
| **Next (parallel track)** | — | [Phase 4.5 — Accounts & preferences](phase-04.5-accounts-preferences.md), then [Phase 5 — Memory & context](phase-05-memory-context.md) |
| **Last** | Mobile (Flutter), Raspberry Pi Zero 2W | Deferred until desktop + Phase 4.5/5 foundations are in place |

Mobile and Pi deliver the same API contract as desktop; they are **not** blockers for Phase 4.5 or Phase 5.

Detailed client notes: [controller/mobile/README.md](../controller/mobile/README.md), [controller/pi/README.md](../controller/pi/README.md).

## Account, devices & pairing (phone + Pi ↔ laptop)

Users log into **phone**, **Raspberry Pi**, and **laptop** JARVIS with the **same account** (Google, GitHub, email, etc.). The server creates **one user ID** per account and a **unique device ID** for each client (phone, Pi, and laptop are separate devices).

### Pairing flow

1. **Laptop** — JARVIS generates a temporary **QR code** containing a **short-lived pairing token** and the **laptop device ID**.
2. **Phone or Pi** — The mobile/Pi app scans the QR and sends the token and laptop device ID to the server (authenticated as the logged-in user).
3. **Server** — Verifies both devices belong to the **same user**, then creates a **secure device link** in the database (controller ↔ laptop).
4. **Remote commands** — When the phone or Pi sends a command (e.g. *"open Cursor"*), the request includes its **auth token** and the **target laptop device ID**. The server checks the stored device link; if authorized and the laptop agent is **online**, it routes the task to that laptop’s JARVIS executor path.

### Authorization model

| Concept | Description |
|---------|-------------|
| **User ID** | One per account across all clients |
| **Device ID** | Unique per phone, Pi, or laptop install |
| **Device link** | Explicit pairing record (controller device ↔ laptop device) |
| **Command routing** | Server enforces link + laptop online before forwarding to executor |

Phase 4.5 implements accounts and tokens; Phase 4b mobile/Pi and desktop QR UX implement this pairing end-to-end.

## Tech stack

### Mobile (`controller/mobile/`)

| Layer | Technology |
|--------|------------|
| **Framework** | [Flutter](https://flutter.dev/) 3.x (Dart 3) |
| **Speech → text** | [speech_to_text](https://pub.dev/packages/speech_to_text) |
| **Text → speech** | [flutter_tts](https://pub.dev/packages/flutter_tts) |
| **HTTP** | [dio](https://pub.dev/packages/dio) or [http](https://pub.dev/packages/http) — REST to FastAPI backend |
| **Realtime (optional)** | [web_socket_channel](https://pub.dev/packages/web_socket_channel) if backend exposes WS |
| **Config** | [flutter_dotenv](https://pub.dev/packages/flutter_dotenv) — `BACKEND_BASE_URL`, etc. |
| **JSON models** | [json_serializable](https://pub.dev/packages/json_serializable) / manual maps aligned with OpenAPI from backend |

### Raspberry Pi Zero 2W (`controller/pi/`)

| Layer | Technology |
|--------|------------|
| **Runtime** | Linux on Raspberry Pi Zero 2W |
| **Controller behavior** | Same interaction model and API contract as mobile (voice/text in, backend response out) |
| **HTTP** | Same backend REST endpoints used by mobile |
| **Realtime (optional)** | Same WebSocket support used by mobile when enabled |
| **Config** | Backend base URL and credentials handled similarly to mobile environment config |

### Desktop (`controller/desktop/`)

| Layer | Technology |
|--------|------------|
| **Stack** | [TypeScript](https://www.typescriptlang.org/) + [Vite](https://vitejs.dev/) + [React](https://react.dev/) 18 |
| **UI** | [Tailwind CSS](https://tailwindcss.com/) (or CSS modules — match one system project-wide) |
| **HTTP** | [ky](https://github.com/sindresorhus/ky) or [axios](https://axios-http.com/) |
| **Chat UI** | Custom panels or [shadcn/ui](https://ui.shadcn.com/)-style components on React |
| **Types** | Generate from backend OpenAPI with [openapi-typescript](https://openapi-ts.dev/) (optional) |

### Shared note

Backend **chat** still uses **Ollama** with **`llama3.2`** or **`llama3.3`**; controllers only send/receive HTTP JSON and never embed the LLM. The Raspberry Pi layer follows the same backend contract as mobile.

## Scope

### Mobile (Flutter)

- **Speech → text** input; **text → speech** for responses (where useful).
- **HTTP/WebSocket client** to backend: send utterances or text, display status and errors.
- **Same-account sign-in** and **QR pairing** to a laptop (see [Account, devices & pairing](#account-devices--pairing-phone--pi--laptop)).
- **Remote commands** include auth token + target laptop device ID; server enforces device link before routing.
- **Minimal UX:** connection settings (backend URL), pair/unpair laptop, execution feedback, microphone permissions.

### Raspberry Pi Zero 2W

- **Phone-like controller behavior:** same command flow, pairing, and authorization as mobile.
- **Same backend integration:** identical APIs, device IDs, device links, and payload formats as mobile.
- **Lightweight deployment:** designed for always-on edge usage with minimal UI (scan QR, voice/status).

### Desktop (web and/or native app)

- **Chat-style UI** for commands and replies.
- **Command input** (direct structured or natural language — align with backend).
- **Monitoring:** recent commands, executor connectivity, optional logs view (read-only).
- **Pairing host:** display **QR code** (short-lived token + laptop device ID) for phone/Pi to scan and establish device link.

### Shared expectations

- Use **shared** schemas/types where possible (generated or hand-maintained).
- Consistent error and loading states.
- Keep mobile and Raspberry Pi request/response behavior equivalent.

## Out of scope (this phase)

- Full product polish of the hub website (Phase 7).
- User accounts, onboarding, and explicit preference capture ([Phase 4.5](phase-04.5-accounts-preferences.md)).
- Long-term memory, context detection, and adaptive intelligence ([Phase 5](phase-05-memory-context.md)).

## Deliverables

### Phase 4a (now — desktop)

1. **Desktop UI** in `controller/desktop/` wired to backend APIs (chat, commands, monitoring).
2. **README** in `controller/desktop/`: build, run, env vars.
3. **Demo path:** text (and optional voice on desktop) → same backend behavior as Phase 3.

### Phase 4b (deferred — mobile + Pi)

4. **Flutter app** in `controller/mobile/` with voice loop and backend integration.
5. **Raspberry Pi Zero 2W controller layer** in `controller/pi/` following mobile behavior and backend contract.
6. **README** per subfolder: build, run, env vars.

## Success criteria

### Phase 4a (required before 4.5/5 UI dependency)

- A user can trigger at least one real executor action from **desktop** without backend/executor changes per client.
- Configuration (backend base URL) is documented and not hardcoded for production.

### Phase 4b (when mobile/Pi resume)

- Same success path from **mobile** and **Raspberry Pi Zero 2W** with equivalent request/response behavior to desktop.

## Dependencies

- Phase 3 (stable integrated pipeline).

## Risks / notes

- App store policies and mic permissions on mobile; desktop may be easier for first user tests.
- Latency: show optimistic UI or progress for long-running executor steps.
