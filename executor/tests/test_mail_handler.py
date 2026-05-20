import os
from unittest.mock import MagicMock, patch

import pytest

from executor.app.handlers.mail import handle_send_email
from shared.schema import Task


@pytest.fixture
def smtp_env(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "jarvis@test.com")
    monkeypatch.setenv("SMTP_PASS", "app-password")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SECURE", "true")


def test_send_email_missing_config(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    result = handle_send_email(
        Task(action="SEND_EMAIL", target="a@b.com", parameters={"subject": "Hi", "body": "Test"}),
        None,
    )
    assert result.success is False
    assert result.error_code == "SMTP_NOT_CONFIGURED"


@patch("executor.app.handlers.mail.smtplib.SMTP")
def test_send_email_success(mock_smtp_cls, smtp_env):
    server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = server

    result = handle_send_email(
        Task(
            action="SEND_EMAIL",
            target="motasim@example.com",
            parameters={
                "subject": "Test from JARVIS",
                "body": "This is a test mail from jarvis",
            },
        ),
        None,
    )
    assert result.success is True
    assert "motasim@example.com" in result.message
    server.login.assert_called_once()
    server.sendmail.assert_called_once()
