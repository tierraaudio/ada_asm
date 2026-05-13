"""Email sender selection.

Returns ``SmtpEmailSender`` when ``SMTP_HOST`` is configured, otherwise
``ConsoleEmailSender``. The factory is intentionally a function (not a
module-level singleton) so tests can rebuild it after monkeypatching env.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.infrastructure.email.console import ConsoleEmailSender
from app.infrastructure.email.sender import EmailNotConfiguredError, EmailSender
from app.infrastructure.email.smtp import SmtpEmailSender


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.smtp_host:
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()


__all__ = [
    "ConsoleEmailSender",
    "EmailNotConfiguredError",
    "EmailSender",
    "SmtpEmailSender",
    "get_email_sender",
]
