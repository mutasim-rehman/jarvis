# Supabase setup — Phase 4.5

## Environment variables

### Backend (`.env` at repo root)

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_ANON_KEY` | Public anon key (optional on backend) |
| `SUPABASE_JWT_SECRET` | JWT secret from **Project Settings → API** (verify Bearer tokens) |
| `DATABASE_URL` | Postgres URI — prefer **Session pooler** (`postgresql://...@aws-0-...pooler.supabase.com:5432/postgres`) if direct `db.<project>.supabase.co` fails on your network |
| `API_AUTH_MODE` | `optional` (default) or `required` for account routes |

### Desktop (`controller/desktop/.env` or Vite env)

| Variable | Purpose |
|----------|---------|
| `VITE_SUPABASE_URL` | Same as `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | Anon key for OAuth in Electron |

### Hub (`hub/.env`)

| Variable | Purpose |
|----------|---------|
| `PUBLIC_SUPABASE_URL` | Project URL |
| `PUBLIC_SUPABASE_ANON_KEY` | Anon key |
| `PUBLIC_BACKEND_URL` | FastAPI base (e.g. `http://127.0.0.1:8000`) |

## OAuth redirect URLs

Add to **Authentication → URL configuration** in Supabase:

- Desktop Electron (system browser): `http://127.0.0.1:52847/auth/callback`
- Desktop Vite-only dev: `http://127.0.0.1:5173/auth/callback`
- Hub production: `https://<your-domain>/auth/callback`
- Hub local: `http://localhost:4321/auth/callback`

Google/GitHub OAuth apps here are **login only**. Executor Gmail/Spotify OAuth (`GCR_*`, `Spotify_*`) remains separate.

## `preferences.settings` JSON shape

```json
{
  "version": 1,
  "onboarding_completed": false,
  "sliders": {
    "honesty": 0.7,
    "humor": 0.4,
    "formality": 0.6,
    "verbosity": 0.5,
    "proactivity": 0.5
  },
  "assistant_defaults": {
    "tone": "calm",
    "verbosity": "moderate",
    "suggest_actions": true
  },
  "content_hints": {
    "genres": [],
    "interests": [],
    "do_not_suggest": []
  },
  "integrations": {
    "spotify": false,
    "youtube": false
  },
  "personality_profile_v1": null,
  "devices": []
}
```

## RLS checklist

- `profiles`, `preferences`: user can CRUD own rows (`auth.uid() = id` / `user_id`)
- `pairing_sessions`, `device_links`, `tasks`: scoped by `user_id`
- Backend uses `DATABASE_URL` with DB user that can write after JWT verification

## Signup trigger

On `auth.users` insert, create `profiles` and `preferences` rows.

**Run in Supabase Dashboard → SQL Editor** (full script, safe to re-run):

[`docs/supabase/phase-4.5-schema.sql`](supabase/phase-4.5-schema.sql)

That file creates tables (if missing), the signup trigger, **backfills existing users** who signed up before the trigger existed, and RLS policies.

Quick check after running (replace email):

```sql
select u.id, u.email,
       p.id is not null as has_profile,
       pref.user_id is not null as has_preferences
from auth.users u
left join public.profiles p on p.id = u.id
left join public.preferences pref on pref.user_id = u.id
where u.email = 'your-email@example.com';
```

Both `has_profile` and `has_preferences` should be `true`.

## API routes (authenticated)

- `GET /auth/me`
- `GET|PATCH /users/profile`, `GET|PATCH /preferences`
- `GET /preferences/personality/template`, `POST /preferences/personality`
- `POST /devices/register`
- `POST /pairing/sessions`, `POST /pairing/claim`, `GET /pairing/links`
- `POST|GET /tasks`

Send `Authorization: Bearer <supabase_access_token>` and optional `X-Device-Id`.

## HTML email templates

Black/orange branded templates for Supabase Auth emails: [supabase/email-templates/README.md](supabase/email-templates/README.md). Paste each HTML file into **Authentication → Email Templates** in the dashboard.

**Welcome email (post-onboarding):** configure `SMTP_*` in root `.env`. When the user finishes onboarding on desktop or hub, the backend sends `Welcome to JARVIS` once (see README in `email-templates/`).
