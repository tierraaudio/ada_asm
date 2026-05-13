"""Integration tests for password recovery + reset."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from app.domain.entities.user import User

pytestmark = pytest.mark.integration


def _capture_console_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    def _capture(self, event_dict):  # type: ignore[no-untyped-def]
        if event_dict.get("event") == "email.console.delivery":
            captured.append(event_dict)
        return event_dict

    # Wrap structlog's processor pipeline by adding our capture as the final
    # processor before render. Cleanest approach: monkeypatch the console
    # sender's send method.
    from app.infrastructure.email import console as console_module

    async def fake_send(  # type: ignore[no-untyped-def]
        self,
        *,
        to,
        subject,
        body_text,
        body_html=None,
    ):
        captured.append(
            {
                "to": to,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
            }
        )

    monkeypatch.setattr(console_module.ConsoleEmailSender, "send", fake_send)
    return captured


def _extract_reset_token(body_text: str) -> str:
    # The body contains the URL; parse out the ?token=...
    for line in body_text.splitlines():
        if "token=" in line:
            url = line.strip()
            qs = parse_qs(urlparse(url).query)
            tokens = qs.get("token") or []
            if tokens:
                return tokens[0]
    raise AssertionError(f"Could not find reset token in body:\n{body_text}")


async def test_recovery_for_registered_email_dispatches(
    api_client: AsyncClient,
    seeded_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_console_emails(monkeypatch)

    response = await api_client.post(
        "/api/v1/auth/password-recovery",
        json={"email": seeded_user.email},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert len(captured) == 1
    assert captured[0]["to"] == seeded_user.email
    assert "/reset-password?token=" in captured[0]["body_text"]


async def test_recovery_for_unknown_email_does_not_send(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_console_emails(monkeypatch)

    response = await api_client.post(
        "/api/v1/auth/password-recovery",
        json={"email": "nobody@nowhere.example"},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert captured == []


async def test_response_bodies_are_identical_regardless_of_email_existence(
    api_client: AsyncClient,
    seeded_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_console_emails(monkeypatch)

    a = await api_client.post(
        "/api/v1/auth/password-recovery",
        json={"email": seeded_user.email},
    )
    b = await api_client.post(
        "/api/v1/auth/password-recovery",
        json={"email": "another-unknown@nowhere.example"},
    )
    assert a.json() == b.json()


async def test_reset_with_valid_token_succeeds_and_revokes_sessions(
    api_client: AsyncClient,
    seeded_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_console_emails(monkeypatch)

    # Log in so the user has an active refresh token to be revoked.
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "long-enough-passphrase"},
    )
    refresh_token = login.json()["refresh_token"]

    # Request recovery → capture the issued token from the captured email.
    await api_client.post(
        "/api/v1/auth/password-recovery",
        json={"email": seeded_user.email},
    )
    raw_reset = _extract_reset_token(captured[0]["body_text"])

    # Reset.
    response = await api_client.post(
        "/api/v1/auth/password-reset",
        json={"token": raw_reset, "new_password": "brand-new-strong-passphrase"},
    )
    assert response.status_code == 204, response.text

    # The OLD refresh token must no longer work.
    refresh_after = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_after.status_code == 401
    assert refresh_after.json()["code"] == "REFRESH_TOKEN_REVOKED"

    # New password works for login.
    new_login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "brand-new-strong-passphrase"},
    )
    assert new_login.status_code == 200


async def test_reset_with_used_token_is_rejected(
    api_client: AsyncClient,
    seeded_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_console_emails(monkeypatch)
    await api_client.post(
        "/api/v1/auth/password-recovery",
        json={"email": seeded_user.email},
    )
    raw = _extract_reset_token(captured[0]["body_text"])

    first = await api_client.post(
        "/api/v1/auth/password-reset",
        json={"token": raw, "new_password": "first-new-password-here"},
    )
    assert first.status_code == 204

    second = await api_client.post(
        "/api/v1/auth/password-reset",
        json={"token": raw, "new_password": "second-new-password-different"},
    )
    assert second.status_code == 400
    assert second.json()["code"] in {"RESET_TOKEN_ALREADY_USED", "RESET_TOKEN_INVALID"}


async def test_reset_with_short_password_returns_422(
    api_client: AsyncClient,
    seeded_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_console_emails(monkeypatch)
    await api_client.post(
        "/api/v1/auth/password-recovery",
        json={"email": seeded_user.email},
    )
    raw = _extract_reset_token(captured[0]["body_text"])

    response = await api_client.post(
        "/api/v1/auth/password-reset",
        json={"token": raw, "new_password": "tooShort"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_TOO_SHORT"
