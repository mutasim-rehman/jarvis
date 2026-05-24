# Supabase HTML email templates (JARVIS)

Paste each file into **Supabase Dashboard → Authentication → Email Templates**.

Use **Custom SMTP** (optional) from your `.env` (`SMTP_*`) for sending; templates below control HTML body either way.

## Variables (Supabase Go templates)

| Variable | Description |
|----------|-------------|
| `{{ .ConfirmationURL }}` | Confirm / magic link URL |
| `{{ .SiteURL }}` | Site URL from Auth settings |
| `{{ .Email }}` | User email |
| `{{ .Token }}` | OTP token (if enabled) |
| `{{ .RedirectTo }}` | Redirect after confirm |

## Which template to paste where

| Supabase template name | File |
|------------------------|------|
| Confirm signup | `confirm-signup.html` |
| Magic Link | `magic-link.html` |
| Invite user | `invite-user.html` |
| Reset password | `reset-password.html` |
| Change email | `change-email.html` |

## Subject lines (suggested)

- Confirm signup: `Confirm your JARVIS account`
- Magic Link: `Your JARVIS sign-in link`
- Invite user: `You're invited to JARVIS`
- Reset password: `Reset your JARVIS password`
- Change email: `Confirm your new JARVIS email`

After pasting, send a test signup from Authentication → Users or trigger email auth once.

## Welcome email (onboarding complete)

When a user finishes onboarding on **desktop** or **hub**, the backend sends a branded HTML thank-you email via `SMTP_*` in root `.env` (same credentials as the executor `SEND_EMAIL` tool).

- Trigger: first `PATCH /preferences` with `onboarding_completed: true`
- Subject: `Welcome to JARVIS`
- Reference HTML: `welcome-account.html` (live template is built in `backend/app/email/welcome.py`)
- Skipped if `SMTP_USER` / `SMTP_PASS` are unset, or the user has no email (some OAuth edge cases)
- Not sent again (`welcome_email_sent` flag in `preferences.settings`)

OAuth sign-up still uses Supabase **Confirm signup** template above for email verification; the welcome email is separate and fires after onboarding.
