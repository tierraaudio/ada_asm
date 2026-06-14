"""Bootstrap the first administrator on a fresh database.

Usage:
    python -m app.scripts.seed_admin --email <e> --password <p> [--full-name "..."]

Exits 0 on success, non-zero if an admin already exists or any input is
invalid. Idempotent re-runs are explicitly disabled so re-seeding is a
conscious operator action.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.core.exceptions import PasswordTooLongError, PasswordTooShortError
from app.domain.entities.user import User
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.security import hash_password


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the first administrator user.")
    # CLI args are optional in the cloud invocation path — the Container
    # App Job (`caj-ada-asm-seed-admin-<env>`) sources email + password
    # from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` env vars (mapped
    # from Key Vault). Local CLI usage still requires both.
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--full-name", default="Admin User")
    return parser


def _resolve_credentials(cli_email: str | None, cli_password: str | None) -> tuple[str, str]:
    """CLI args win over env. Env-only path supports the cloud Job."""
    import os

    email = cli_email or os.environ.get("SEED_ADMIN_EMAIL")
    password = cli_password or os.environ.get("SEED_ADMIN_PASSWORD")
    if not email or not password:
        msg = (
            "seed_admin: email and password are required. "
            "Pass --email/--password OR set "
            "SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD env vars."
        )
        raise SystemExit(msg)
    return email, password


def _validate_password(password: str) -> None:
    settings = get_settings()
    if len(password) < settings.password_min_length:
        raise PasswordTooShortError(
            f"Password must be at least {settings.password_min_length} characters"
        )
    if len(password) > settings.password_max_length:
        raise PasswordTooLongError(
            f"Password must be at most {settings.password_max_length} characters"
        )


async def _seed(email: str, password: str, full_name: str) -> int:
    _validate_password(password)
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        existing_admins = await repo.list_admins()
        if existing_admins:
            print(
                "Refusing to seed: an administrator already exists "
                f"({', '.join(u.email for u in existing_admins)}).",
                file=sys.stderr,
            )
            return 2

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            global_role="admin",
            is_active=True,
        )
        await repo.save(user)
        await session.commit()
        print(f"Seeded admin: {email}")
        return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    email, password = _resolve_credentials(args.email, args.password)
    return asyncio.run(_seed(email, password, args.full_name))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
