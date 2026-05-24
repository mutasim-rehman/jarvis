"""Welcome email tests."""

from unittest.mock import patch

from backend.app.email.welcome import build_welcome_email_html, maybe_send_welcome_email


def test_build_welcome_email_html_escapes_name():
    html = build_welcome_email_html(display_name="<script>", email="user@example.com")
    assert "<script>" not in html
    assert "user@example.com" in html


def test_maybe_send_welcome_email_calls_smtp():
    with patch("backend.app.email.welcome.send_html_email", return_value=True) as send:
        assert maybe_send_welcome_email(to_email="user@example.com", display_name="Ada") is True
        send.assert_called_once()
        assert send.call_args.kwargs["subject"] == "Welcome to JARVIS"


def test_maybe_send_welcome_email_skips_without_address():
    with patch("backend.app.email.welcome.send_html_email") as send:
        assert maybe_send_welcome_email(to_email="") is False
        send.assert_not_called()
