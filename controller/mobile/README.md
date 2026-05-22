# Jarvis Mobile Controller (Phone)

Flutter voice-first client for JARVIS. Planned for **Phase 4b** (after desktop, Phase 4.5 accounts, and Phase 5 memory work).

See also: [Phase 4 controller plan](../../docs/phase-04-controller.md), [Phase 4.5 accounts](../../docs/phase-04.5-accounts-preferences.md).

## Role

- Primary **remote control** surface: voice and text commands sent to the backend.
- Targets a **paired laptop** (desktop JARVIS + executor) when the user wants the PC to run actions (e.g. *"open Cursor"*).
- Uses the **same user account** as the laptop (Google, GitHub, email, etc.).

## Account & device identity

Users log into **phone** and **laptop** JARVIS with the same account (Google, GitHub, email, etc.). The server:

1. Creates **one user ID** per account.
2. Assigns a **unique device ID** per physical client (phone and laptop are separate devices).

All authenticated API calls include the user session/token and the **calling device’s ID**.

## Pairing phone ↔ laptop

Remote control requires an explicit **device link** between the phone and the laptop the user wants to command.

### 1. Laptop displays pairing QR

On the laptop, JARVIS generates a **temporary QR code** containing:

- A **short-lived pairing token**
- The **laptop device ID**

The token expires after a short window to limit exposure if the QR is photographed or left on screen.

### 2. Phone scans and registers the link

The phone JARVIS app **scans** the QR and sends the token and laptop device ID to the server (authenticated as the same logged-in user).

The server:

1. Verifies both devices belong to the **same logged-in user**.
2. Creates a **secure device link** in the database (phone ↔ laptop).

### 3. Remote commands

After pairing, when the phone sends a command (e.g. *"open Cursor"*), the request includes:

- The phone’s **authenticated session/token**
- The **target laptop device ID**

The server:

1. Checks whether this phone is **authorized** to control that laptop using the stored device link.
2. If valid and the laptop agent is **online**, securely **routes the task** to the correct laptop JARVIS executor path.
3. If invalid or laptop offline, returns a clear error (re-pair or pick another device).

## Planned tech stack

| Layer | Technology |
|--------|------------|
| **Framework** | [Flutter](https://flutter.dev/) 3.x (Dart 3) |
| **Speech → text** | [speech_to_text](https://pub.dev/packages/speech_to_text) |
| **Text → speech** | [flutter_tts](https://pub.dev/packages/flutter_tts) |
| **QR scan** | e.g. [mobile_scanner](https://pub.dev/packages/mobile_scanner) for pairing |
| **HTTP** | [dio](https://pub.dev/packages/dio) or [http](https://pub.dev/packages/http) |
| **Config** | `BACKEND_BASE_URL`, OAuth client ids via env / build flavors |

## UX expectations (Phase 4b)

- Sign in with the same providers as desktop (Phase 4.5).
- **Pair device** flow: scan laptop QR, show linked laptop name/status.
- Voice loop, execution feedback, microphone permissions.
- Settings: backend URL (dev), linked devices, unlink/re-pair.

## Status

Not implemented yet. Repository folder reserved for the Flutter app scaffold.
