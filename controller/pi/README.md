# Jarvis Raspberry Pi Controller (Zero 2W)

Edge controller with the **same interaction model and backend contract as the mobile phone app**. Planned for **Phase 4b** alongside the Flutter client.

See also: [Phase 4 controller plan](../../docs/phase-04-controller.md), [mobile controller README](../mobile/README.md).

## Role

- **Phone-like controller** on Raspberry Pi Zero 2W: voice/text in, backend response out.
- Can act as a **remote control** for a paired laptop using the **same account, device IDs, and pairing flow as mobile**.
- Lightweight, always-on option for a dedicated room or desk mic without carrying a phone.

## Account & device identity

Users log into **Pi** and **laptop** JARVIS with the same account (Google, GitHub, email, etc.). The server:

1. Creates **one user ID** per account.
2. Assigns a **unique device ID** for the Pi (separate from phone and laptop).

The Pi is a first-class **device** in the account model, not a shared anonymous client.

## Pairing Pi ↔ laptop

Pairing matches the **mobile phone** flow so one mental model covers all remote controllers.

### 1. Laptop displays pairing QR

On the laptop, JARVIS generates a **temporary QR code** containing:

- A **short-lived pairing token**
- The **laptop device ID**

### 2. Pi scans and registers the link

The Pi JARVIS UI **scans** the QR (camera module or USB webcam as hardware allows) and sends the token and laptop device ID to the server.

The server:

1. Verifies both devices belong to the **same logged-in user**.
2. Creates a **secure device link** in the database (Pi ↔ laptop).

A user may link **multiple** controllers (phone + Pi) to the same laptop if each completes pairing while logged into the same account.

### 3. Remote commands

After pairing, when the Pi sends a command (e.g. *"open Cursor"*), the request includes:

- The Pi’s **authenticated session/token**
- The **target laptop device ID**

The server:

1. Checks authorization via the stored **device link**.
2. If valid and the laptop is **online**, routes the task to that laptop’s JARVIS agent.
3. Otherwise returns an actionable error (re-pair, check network, laptop offline).

## Planned tech stack

| Layer | Technology |
|--------|------------|
| **Runtime** | Linux on Raspberry Pi Zero 2W |
| **UI** | Minimal local UI (same flows as mobile: sign-in, pair, voice/status) |
| **HTTP** | Same REST (and optional WebSocket) endpoints as mobile |
| **QR scan** | Platform-appropriate scanner on Pi when pairing |
| **Config** | Backend base URL and credentials (env or local config file) |

## Parity with mobile

- **Same APIs and payload shapes** as `controller/mobile/`.
- **Same pairing and authorization rules** (user ID, device ID, device link, target laptop ID on commands).
- Differences are only **hardware/deployment** (GPIO, audio device, headless vs small display).

## Status

Not implemented yet. Repository folder reserved for the Pi controller layer.
