"""SMTP email sender — disabled unless ``SMTP_HOST`` is configured.

Not exercised end-to-end in tests of the bootstrap login change; the
``ConsoleEmailSender`` is the default in development and CI. Provided here so
the contract is in place when a real SMTP provider is wired in production.
"""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from app.core.config import Settings
from app.infrastructure.email.sender import EmailNotConfiguredError


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host or not settings.smtp_from:
            raise EmailNotConfiguredError(
                "SMTP_HOST and SMTP_FROM must be set to use SmtpEmailSender"
            )
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = settings.smtp_password
        self._from = settings.smtp_from
        self._use_tls = settings.smtp_use_tls

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)
        if body_html:
            message.add_alternative(body_html, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            use_tls=self._use_tls,
        )
