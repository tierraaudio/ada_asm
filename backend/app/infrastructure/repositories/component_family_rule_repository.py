"""Repository for `component_family_rules`.

Loads the editable family-mapping rules used by `FamilyInferenceService`.
The rule set is small (the slice of categories we actually stock), so
`list_enabled()` loads them all for in-process evaluation.
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.component_family_rule import ComponentFamilyRule, MatchType
from app.infrastructure.db.models.component_family_rule import (
    ComponentFamilyRuleModel,
)


def _to_entity(row: ComponentFamilyRuleModel) -> ComponentFamilyRule:
    return ComponentFamilyRule(
        id=row.id,
        supplier=row.supplier,
        match_type=cast(MatchType, row.match_type),
        match_value=row.match_value,
        family=row.family,
        confidence=row.confidence,
        priority=row.priority,
        enabled=row.enabled,
        notes=row.notes,
    )


class SqlAlchemyComponentFamilyRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled(self) -> list[ComponentFamilyRule]:
        stmt = select(ComponentFamilyRuleModel).where(
            ComponentFamilyRuleModel.enabled.is_(True)
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]
