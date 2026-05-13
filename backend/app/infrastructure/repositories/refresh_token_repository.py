"""SQLAlchemy-backed implementation of ``RefreshTokenRepository``."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.refresh_token import RefreshToken
from app.infrastructure.db.models.refresh_token import RefreshTokenModel


def _to_entity(row: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=row.id,
        user_id=row.user_id,
        jti_hash=row.jti_hash,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
        created_from_ip=str(row.created_from_ip) if row.created_from_ip else None,
        user_agent=row.user_agent,
    )


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, token: RefreshToken) -> RefreshToken:
        row = RefreshTokenModel(
            id=token.id,
            user_id=token.user_id,
            jti_hash=token.jti_hash,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
            created_from_ip=token.created_from_ip,
            user_agent=token.user_agent,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)

    async def get_by_jti_hash(self, jti_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.jti_hash == jti_hash)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def revoke(self, jti_hash: str) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.jti_hash == jti_hash)
            .where(RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id)
            .where(RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)
