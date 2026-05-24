"""SQLAlchemy implementation of `NatoScoringRepository`."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.component import NatoScoreValue, TierValue
from app.domain.entities.nato_scoring import ComponentNatoScoring, NatoScoringStatus
from app.infrastructure.db.models.nato_scoring import ComponentNatoScoringModel


def _to_entity(row: ComponentNatoScoringModel) -> ComponentNatoScoring:
    return ComponentNatoScoring(
        id=row.id,
        component_id=row.component_id,
        nato_score=cast(NatoScoreValue, row.nato_score),
        tier=cast(TierValue, row.tier),
        classified_at=row.classified_at,
        expires_at=row.expires_at,
        classified_by_user_id=row.classified_by_user_id,
        status=cast(NatoScoringStatus, row.status),
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyNatoScoringRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_component(
        self, component_id: UUID
    ) -> ComponentNatoScoring | None:
        stmt = select(ComponentNatoScoringModel).where(
            ComponentNatoScoringModel.component_id == component_id,
            ComponentNatoScoringModel.status == "active",
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_for_component(
        self, component_id: UUID
    ) -> list[ComponentNatoScoring]:
        stmt = (
            select(ComponentNatoScoringModel)
            .where(ComponentNatoScoringModel.component_id == component_id)
            .order_by(ComponentNatoScoringModel.classified_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def get_by_id(self, scoring_id: UUID) -> ComponentNatoScoring | None:
        row = await self._session.get(ComponentNatoScoringModel, scoring_id)
        return _to_entity(row) if row else None

    async def archive_active(self, component_id: UUID) -> None:
        stmt = (
            update(ComponentNatoScoringModel)
            .where(
                ComponentNatoScoringModel.component_id == component_id,
                ComponentNatoScoringModel.status == "active",
            )
            .values(status="archived")
        )
        await self._session.execute(stmt)

    async def save(self, scoring: ComponentNatoScoring) -> ComponentNatoScoring:
        row = ComponentNatoScoringModel(
            id=scoring.id,
            component_id=scoring.component_id,
            nato_score=scoring.nato_score,
            tier=scoring.tier,
            classified_at=scoring.classified_at,
            expires_at=scoring.expires_at,
            classified_by_user_id=scoring.classified_by_user_id,
            status=scoring.status,
            notes=scoring.notes,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
