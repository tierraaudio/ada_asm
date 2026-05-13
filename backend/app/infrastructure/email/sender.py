"""Email sender Protocol."""

from __future__ import annotations

from typing import Protocol


class EmailSender(Protocol):
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None: ...


class EmailNotConfiguredError(RuntimeError):
    """Raised when an SMTP sender is invoked but ``SMTP_HOST`` is not set."""
