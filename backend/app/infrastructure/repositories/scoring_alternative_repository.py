"""SQLAlchemy implementation of `ScoringAlternativeRepository`."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.scoring_alternative import ScoringAlternative
from app.infrastructure.db.models.scoring_alternative import ScoringAlternativeModel


def _to_entity(row: ScoringAlternativeModel) -> ScoringAlternative:
    return ScoringAlternative(
        id=row.id,
        nato_scoring_id=row.nato_scoring_id,
        alternative_component_id=row.alternative_component_id,
        notes=row.notes,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyScoringAlternativeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_scoring(
        self, nato_scoring_id: UUID
    ) -> list[ScoringAlternative]:
        stmt = (
            select(ScoringAlternativeModel)
            .where(ScoringAlternativeModel.nato_scoring_id == nato_scoring_id)
            .order_by(ScoringAlternativeModel.sort_order.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def replace_for_scoring(
        self,
        nato_scoring_id: UUID,
        alternatives: Sequence[ScoringAlternative],
    ) -> list[ScoringAlternative]:
        await self._session.execute(
            delete(ScoringAlternativeModel).where(
                ScoringAlternativeModel.nato_scoring_id == nato_scoring_id
            )
        )
        saved: list[ScoringAlternative] = []
        for index, a in enumerate(alternatives):
            a.nato_scoring_id = nato_scoring_id
            a.sort_order = index
            saved.append(await self.save(a))
        return saved

    async def save(self, alternative: ScoringAlternative) -> ScoringAlternative:
        row = ScoringAlternativeModel(
            id=alternative.id,
            nato_scoring_id=alternative.nato_scoring_id,
            alternative_component_id=alternative.alternative_component_id,
            notes=alternative.notes,
            sort_order=alternative.sort_order,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
