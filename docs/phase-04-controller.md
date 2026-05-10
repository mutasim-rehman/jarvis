# Phase 4 — Controller (Mobile + Desktop + Raspberry Pi Zero 2W)

**Objective:** Provide user-facing clients that share the same backend → executor pipeline: **mobile** for voice-first control, **desktop** for chat/typed commands/monitoring, and **Raspberry Pi Zero 2W** as a phone-like edge controller.

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
- **Minimal UX:** connection settings (backend URL), execution feedback, permission handling for microphone.

### Raspberry Pi Zero 2W

- **Phone-like controller behavior:** same command flow and response handling as mobile.
- **Same backend integration:** uses the same APIs and payload formats as mobile.
- **Lightweight deployment:** designed for always-on edge usage with minimal UI requirements.

### Desktop (web and/or native app)

- **Chat-style UI** for commands and replies.
- **Command input** (direct structured or natural language — align with backend).
- **Monitoring:** recent commands, executor connectivity, optional logs view (read-only).

### Shared expectations

- Use **shared** schemas/types where possible (generated or hand-maintained).
- Consistent error and loading states.
- Keep mobile and Raspberry Pi request/response behavior equivalent.

## Out of scope (this phase)

- Full product polish of the hub website (Phase 7).
- Deep personalization (Phase 5).

## Deliverables

1. **Flutter app** in `controller/mobile/` with voice loop and backend integration.
2. **Desktop UI** in `controller/desktop/` wired to the same APIs as mobile.
3. **Raspberry Pi Zero 2W controller layer** in `controller/pi/` following mobile behavior and backend contract.
4. **README** per subfolder: build, run, env vars.
5. **Demo path:** voice or text → same backend behavior as Phase 3.

## Success criteria

- A user can trigger at least one real executor action from **mobile**, **desktop**, and **Raspberry Pi Zero 2W** without code changes on backend/executor for each client.
- Configuration (backend base URL) is documented and not hardcoded for production.

## Dependencies

- Phase 3 (stable integrated pipeline).

## Risks / notes

- App store policies and mic permissions on mobile; desktop may be easier for first user tests.
- Latency: show optimistic UI or progress for long-running executor steps.
