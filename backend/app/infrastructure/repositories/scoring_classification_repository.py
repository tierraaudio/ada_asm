"""SQLAlchemy implementation of `ScoringClassificationRepository`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.component import NatoScoreValue
from app.domain.entities.scoring_classification import ScoringClassification
from app.infrastructure.db.models.scoring_classification import (
    ScoringClassificationModel,
)


def _to_entity(row: ScoringClassificationModel) -> ScoringClassification:
    return ScoringClassification(
        id=row.id,
        nato_scoring_id=row.nato_scoring_id,
        part_label=row.part_label,
        fabricante=row.fabricante,
        country_of_origin=row.country_of_origin,
        nato_score=cast(NatoScoreValue | None, row.nato_score),
        verificado=row.verificado,
        notas=row.notas,
        reference_component_id=row.reference_component_id,
        reference_url=row.reference_url,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyScoringClassificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_scoring(self, nato_scoring_id: UUID) -> list[ScoringClassification]:
        stmt = (
            select(ScoringClassificationModel)
            .where(ScoringClassificationModel.nato_scoring_id == nato_scoring_id)
            .order_by(ScoringClassificationModel.sort_order.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def replace_for_scoring(
        self,
        nato_scoring_id: UUID,
        classifications: Sequence[ScoringClassification],
    ) -> list[ScoringClassification]:
        await self._session.execute(
            delete(ScoringClassificationModel).where(
                ScoringClassificationModel.nato_scoring_id == nato_scoring_id
            )
        )
        saved: list[ScoringClassification] = []
        for index, c in enumerate(classifications):
            c.nato_scoring_id = nato_scoring_id
            c.sort_order = index
            saved.append(await self.save(c))
        return saved

    async def save(self, classification: ScoringClassification) -> ScoringClassification:
        row = ScoringClassificationModel(
            id=classification.id,
            nato_scoring_id=classification.nato_scoring_id,
            part_label=classification.part_label,
            fabricante=classification.fabricante,
            country_of_origin=classification.country_of_origin,
            nato_score=classification.nato_score,
            verificado=classification.verificado,
            notas=classification.notas,
            reference_component_id=classification.reference_component_id,
            reference_url=classification.reference_url,
            sort_order=classification.sort_order,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_entity(row)
