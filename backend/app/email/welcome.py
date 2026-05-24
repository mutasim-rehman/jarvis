"""Welcome email after onboarding completes."""

from __future__ import annotations

import html
import logging

from backend.app.email.smtp import send_html_email

logger = logging.getLogger(__name__)

WELCOME_SUBJECT = "Welcome to JARVIS"


def build_welcome_email_html(*, display_name: str | None, email: str) -> str:
    greeting_name = (display_name or "").strip() or email.split("@")[0] or "there"
    safe_name = html.escape(greeting_name)
    safe_email = html.escape(email)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Welcome to JARVIS</title>
</head>
<body style="margin:0;padding:0;background:#050505;font-family:'Segoe UI',system-ui,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#050505;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px;background:#0d0d0d;border:1px solid #2a1a10;border-radius:16px;overflow:hidden;">
          <tr>
            <td style="padding:28px 32px 8px;text-align:center;">
              <div style="display:inline-block;width:48px;height:48px;line-height:48px;border-radius:12px;background:linear-gradient(135deg,#f07a1f,#c85e0d);color:#050505;font-weight:800;font-size:22px;">J</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 0;text-align:center;">
              <h1 style="margin:0;color:#f7efe8;font-size:22px;font-weight:700;">You&apos;re all set, {safe_name}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px 0;color:#b39b86;font-size:15px;line-height:1.65;text-align:center;">
              Thanks for creating your JARVIS account. Your preferences are saved and ready
              on desktop, hub, and any device you sign in to next.
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px 8px;color:#b39b86;font-size:13px;line-height:1.6;">
              <p style="margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#f07a1f;">What you can do next</p>
              <p style="margin:0 0 8px;"><span style="color:#f07a1f;">→</span> Talk to JARVIS from the desktop app</p>
              <p style="margin:0 0 8px;"><span style="color:#f07a1f;">→</span> Tune personality sliders anytime in settings</p>
              <p style="margin:0 0 8px;"><span style="color:#f07a1f;">→</span> Connect Spotify or YouTube when you&apos;re ready</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 28px;color:#7a6a5c;font-size:12px;line-height:1.5;text-align:center;">
              Account: {safe_email}<br />
              If you didn&apos;t create this account, you can delete it from JARVIS settings.
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;color:#5c4f44;font-size:11px;">JARVIS · Advanced systems assistant</p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_welcome_email_text(*, display_name: str | None, email: str) -> str:
    greeting_name = (display_name or "").strip() or email.split("@")[0] or "there"
    return (
        f"Hi {greeting_name},\n\n"
        "Thanks for creating your JARVIS account. Your preferences are saved and ready "
        "on desktop, hub, and any device you sign in to next.\n\n"
        f"Account: {email}\n\n"
        "— JARVIS"
    )


def maybe_send_welcome_email(*, to_email: str, display_name: str | None = None) -> bool:
    """Send welcome email once when onboarding completes. Returns True if sent."""
    email = (to_email or "").strip()
    if not email or "@" not in email:
        logger.info("Welcome email skipped: no recipient email")
        return False

    html_body = build_welcome_email_html(display_name=display_name, email=email)
    text_body = build_welcome_email_text(display_name=display_name, email=email)
    sent = send_html_email(
        to_addr=email,
        subject=WELCOME_SUBJECT,
        html_body=html_body,
        text_body=text_body,
    )
    if sent:
        logger.info("Welcome email sent to %s", email)
    return sent
