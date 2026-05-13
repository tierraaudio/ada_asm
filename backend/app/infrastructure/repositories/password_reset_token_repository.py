"""SQLAlchemy-backed implementation of ``PasswordResetTokenRepository``."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.password_reset_token import PasswordResetToken
from app.infrastructure.db.models.password_reset_token import PasswordResetTokenModel


def _to_entity(row: PasswordResetTokenModel) -> PasswordResetToken:
    return PasswordResetToken(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
        created_at=row.created_at,
    )


class SqlAlchemyPasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, token: PasswordResetToken) -> PasswordResetToken:
        row = PasswordResetTokenModel(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            used_at=token.used_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)

    async def list_active(self) -> list[PasswordResetToken]:
        now = datetime.now(UTC)
        stmt = (
            select(PasswordResetTokenModel)
            .where(PasswordResetTokenModel.used_at.is_(None))
            .where(PasswordResetTokenModel.expires_at >= now)
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def mark_used(self, token: PasswordResetToken) -> None:
        row = await self._session.get(PasswordResetTokenModel, token.id)
        if row is None:
            return
        row.used_at = datetime.now(UTC)
        await self._session.flush()
