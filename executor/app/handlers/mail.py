"""Send email via SMTP credentials from .env."""

from __future__ import annotations

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from shared.schema import Task, TaskResult

from executor.app.context import HandlerContext


def _env(*keys: str) -> str:
    for key in keys:
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return ""


def _smtp_config() -> dict[str, Any] | None:
    user = _env("SMTP_USER", "EXECUTOR_SMTP_USER")
    password = _env("SMTP_PASS", "SMTP_PASSWORD", "EXECUTOR_SMTP_PASS")
    if not user or not password:
        return None
    host = _env("SMTP_HOST", "EXECUTOR_SMTP_HOST") or "smtp.gmail.com"
    port_raw = _env("SMTP_PORT", "EXECUTOR_SMTP_PORT") or "587"
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    secure = _env("SMTP_SECURE", "SMPT_SECURE", "EXECUTOR_SMTP_SECURE").lower() in (
        "1",
        "true",
        "yes",
        "tls",
    )
    if not secure and port == 465:
        secure = True
    from_addr = _env("SMTP_FROM", "EXECUTOR_SMTP_FROM") or user
    app_name = _env("SMTP_APP_NAME", "SMPT_APP_NAME", "EXECUTOR_SMTP_APP_NAME") or "JARVIS"
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "use_tls": secure or port == 587,
        "from_addr": from_addr,
        "from_display": app_name,
    }


def _task_parameters(task: Task) -> dict[str, Any]:
    raw = getattr(task, "parameters", None)
    if isinstance(raw, dict):
        return raw
    extra = getattr(task, "__pydantic_extra__", None) or {}
    if isinstance(extra.get("parameters"), dict):
        return extra["parameters"]
    return {}


def _extract_email(text: str) -> str | None:
    m = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", text)
    return m.group(0) if m else None


def handle_send_email(task: Task, ctx: HandlerContext) -> TaskResult:
    cfg = _smtp_config()
    if not cfg:
        return TaskResult(
            action="SEND_EMAIL",
            success=False,
            error_code="SMTP_NOT_CONFIGURED",
            message="SMTP is not configured. Set SMTP_USER and SMTP_PASS in .env.",
        )

    params = _task_parameters(task)
    to_addr = (task.target or params.get("to") or "").strip()
    if not to_addr:
        to_addr = _extract_email(str(params.get("recipient") or "")) or ""
    if not to_addr:
        return TaskResult(
            action="SEND_EMAIL",
            success=False,
            error_code="MISSING_RECIPIENT",
            message="Recipient required in target or parameters.to.",
        )

    subject = str(params.get("subject") or "Message from JARVIS").strip()
    body = str(params.get("body") or params.get("message") or "").strip()
    if not body:
        return TaskResult(
            action="SEND_EMAIL",
            success=False,
            error_code="MISSING_BODY",
            message="Email body required in parameters.body or parameters.message.",
        )

    from_display = cfg["from_display"]
    from_addr = cfg["from_addr"]
    msg = MIMEMultipart()
    msg["From"] = f"{from_display} <{from_addr}>"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    timeout = 12
    attempts: list[tuple[str, int, bool]] = []
    if cfg["use_tls"] and cfg["port"] != 465:
        attempts.append((cfg["host"], cfg["port"], False))
    attempts.append((cfg["host"], 465, True))
    if not attempts:
        attempts.append((cfg["host"], cfg["port"], cfg["port"] == 465))

    last_error: Exception | None = None
    for host, port, use_ssl in attempts:
        try:
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=timeout) as server:
                    server.login(cfg["user"], cfg["password"])
                    server.sendmail(from_addr, [to_addr], msg.as_string())
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(cfg["user"], cfg["password"])
                    server.sendmail(from_addr, [to_addr], msg.as_string())
            last_error = None
            break
        except (smtplib.SMTPException, OSError) as exc:
            last_error = exc
            continue

    if last_error is not None:
        if isinstance(last_error, smtplib.SMTPException):
            return TaskResult(
                action="SEND_EMAIL",
                success=False,
                error_code="SMTP_SEND_FAILED",
                message=f"Failed to send email: {last_error}",
            )
        return TaskResult(
            action="SEND_EMAIL",
            success=False,
            error_code="SMTP_CONNECTION_FAILED",
            message=(
                f"Could not reach mail server ({cfg['host']}). "
                f"Check SMTP_HOST/SMTP_PORT, firewall, and Gmail app password. Detail: {last_error}"
            ),
        )

    return TaskResult(
        action="SEND_EMAIL",
        success=True,
        message=f"Email sent to {to_addr}.",
        artifacts={"to": to_addr, "subject": subject},
    )
