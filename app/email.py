"""Pluggable email sender.

- console backend (default, dev): logs the message so you can see verification/reset links
  without an SMTP server.
- smtp backend (prod): sends via SMTP using the SMTP_* settings.

Swap in a transactional-email provider (SendGrid/SES/Postmark) by adding a backend here."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import settings
from .logging_config import get_logger

log = get_logger("lexa.email")


def send_email(to: str, subject: str, body: str) -> None:
    if settings.email_backend == "smtp" and settings.smtp_host:
        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as srv:
            if settings.smtp_starttls:
                srv.starttls()
            if settings.smtp_user:
                srv.login(settings.smtp_user, settings.smtp_password)
            srv.send_message(msg)
        log.info("email sent", extra={"extra_fields": {"to": to, "subject": subject}})
    else:
        # Dev/console backend: don't actually send; log it so links are visible.
        log.info("email (console)", extra={"extra_fields": {
            "to": to, "subject": subject, "body": body}})
