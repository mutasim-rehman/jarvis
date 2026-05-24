"""SMTP send helper (reads SMTP_* from environment via backend config)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.app.config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return settings.resolved_smtp_user() != "" and settings.resolved_smtp_pass() != ""


def send_html_email(
    *,
    to_addr: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> bool:
    """Send HTML email. Returns True on success, False if SMTP not configured or send failed."""
    user = settings.resolved_smtp_user()
    password = settings.resolved_smtp_pass()
    if not user or not password:
        logger.info("Welcome email skipped: SMTP_USER/SMTP_PASS not configured")
        return False

    host = settings.smtp_host or "smtp.gmail.com"
    port = settings.smtp_port
    from_addr = (settings.smtp_from or user).strip()
    app_name = (settings.smtp_app_name or "JARVIS").strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f'"{app_name}" <{from_addr}>'
    msg["To"] = to_addr
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    use_ssl = settings.smtp_secure or port == 465
    try:
        if use_ssl and port != 587:
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                server.login(user, password)
                server.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, password)
                server.sendmail(from_addr, [to_addr], msg.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("SMTP send failed: %s", exc)
        return False
    return True
