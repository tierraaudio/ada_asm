"""SQLAlchemy-backed implementation of ``UserRepository``."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EmailAlreadyRegisteredError
from app.domain.entities.user import GlobalRole, User
from app.infrastructure.db.models.user import UserModel


def _to_entity(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        full_name=row.full_name,
        global_role=cast(GlobalRole, row.global_role),
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return _to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, user: User) -> User:
        row = UserModel(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            full_name=user.full_name,
            global_role=user.global_role,
            is_active=user.is_active,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if (
                "uq_users_email" in str(exc.orig).lower()
                or "users_email_key" in str(exc.orig).lower()
            ):
                raise EmailAlreadyRegisteredError("Email is already registered") from exc
            raise
        await self._session.refresh(row)
        return _to_entity(row)

    async def update_password(self, user_id: UUID, password_hash: str) -> None:
        row = await self._session.get(UserModel, user_id)
        if row is None:
            return
        row.password_hash = password_hash
        await self._session.flush()

    async def count_admins(self) -> int:
        stmt = select(func.count()).select_from(UserModel).where(UserModel.global_role == "admin")
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_admins(self) -> list[User]:
        stmt = select(UserModel).where(UserModel.global_role == "admin")
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]
