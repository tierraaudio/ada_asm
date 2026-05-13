"""Console email sender — emits a structured log line; never dispatches a real email.

Used in development and tests so flows that "send an email" remain observable
without depending on any SMTP relay.
"""

from __future__ import annotations

import structlog


class ConsoleEmailSender:
    def __init__(self) -> None:
        self._log = structlog.get_logger(__name__)

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        self._log.info(
            "email.console.delivery",
            dev_only=True,
            to=to,
            subject=subject,
            body_text=body_text,
            body_html_present=bool(body_html),
        )
