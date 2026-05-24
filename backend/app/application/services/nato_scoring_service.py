"""NATO scoring orchestration — archive + create + replace lists + cache update."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ComponentNotFoundError
from app.domain.entities.component import NatoScoreValue, TierValue
from app.domain.entities.nato_scoring import ComponentNatoScoring
from app.domain.entities.scoring_alternative import ScoringAlternative
from app.domain.entities.scoring_classification import ScoringClassification
from app.domain.repositories.component_repository import ComponentRepository
from app.domain.repositories.nato_scoring_repository import NatoScoringRepository
from app.domain.repositories.scoring_alternative_repository import (
    ScoringAlternativeRepository,
)
from app.domain.repositories.scoring_classification_repository import (
    ScoringClassificationRepository,
)
from app.infrastructure.db.models.component import ComponentModel

logger = structlog.get_logger(__name__)

# Per project convention (user-confirmed 2026-05-24): scorings expire 6 months
# after they are classified unless the caller provides an explicit override.
DEFAULT_SCORING_TTL_DAYS = 30 * 6


@dataclass
class ClassificationInput:
    part_label: str
    fabricante: str | None = None
    country_of_origin: str | None = None
    nato_score: NatoScoreValue | None = None
    verificado: bool = False
    notas: str | None = None
    reference_component_id: UUID | None = None
    reference_url: str | None = None


@dataclass
class AlternativeInput:
    alternative_component_id: UUID
    notes: str | None = None


@dataclass
class CreateScoringInput:
    nato_score: NatoScoreValue
    tier: TierValue
    classified_by_user_id: UUID | None = None
    classified_at: date | None = None  # defaults to today
    expires_at: date | None = None  # defaults to classified_at + 6 months
    notes: str | None = None
    classifications: list[ClassificationInput] = field(default_factory=list)
    alternatives: list[AlternativeInput] = field(default_factory=list)


@dataclass
class ScoringBundle:
    """The active scoring + its current classifications + alternatives."""

    scoring: ComponentNatoScoring
    classifications: list[ScoringClassification]
    alternatives: list[ScoringAlternative]


class NatoScoringService:
    """Atomic create of a new active scoring with its breakdown."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        components: ComponentRepository,
        scorings: NatoScoringRepository,
        classifications: ScoringClassificationRepository,
        alternatives: ScoringAlternativeRepository,
    ) -> None:
        self._session = session
        self._components = components
        self._scorings = scorings
        self._classifications = classifications
        self._alternatives = alternatives

    async def get_active_bundle(self, component_id: UUID) -> ScoringBundle | None:
        scoring = await self._scorings.get_active_for_component(component_id)
        if scoring is None:
            return None
        return ScoringBundle(
            scoring=scoring,
            classifications=await self._classifications.list_for_scoring(scoring.id),
            alternatives=await self._alternatives.list_for_scoring(scoring.id),
        )

    async def list_history(self, component_id: UUID) -> list[ComponentNatoScoring]:
        return await self._scorings.list_for_component(component_id)

    async def create_scoring(
        self, *, component_id: UUID, payload: CreateScoringInput
    ) -> ScoringBundle:
        component = await self._components.get_by_id(component_id)
        if component is None:
            raise ComponentNotFoundError(f"Component {component_id} not found")

        classified_at = payload.classified_at or date.today()
        expires_at = payload.expires_at or (
            classified_at + timedelta(days=DEFAULT_SCORING_TTL_DAYS)
        )

        # 1. Archive the previous active scoring (no-op if none).
        await self._scorings.archive_active(component_id)

        # 2. Insert new active scoring.
        scoring = await self._scorings.save(
            ComponentNatoScoring(
                component_id=component_id,
                nato_score=payload.nato_score,
                tier=payload.tier,
                classified_at=classified_at,
                expires_at=expires_at,
                classified_by_user_id=payload.classified_by_user_id,
                status="active",
                notes=payload.notes,
            )
        )

        # 3. Replace classifications + alternatives for the new scoring.
        saved_classifications = await self._classifications.replace_for_scoring(
            scoring.id,
            [
                ScoringClassification(
                    part_label=c.part_label,
                    fabricante=c.fabricante,
                    country_of_origin=c.country_of_origin,
                    nato_score=c.nato_score,
                    verificado=c.verificado,
                    notas=c.notas,
                    reference_component_id=c.reference_component_id,
                    reference_url=c.reference_url,
                )
                for c in payload.classifications
            ],
        )
        saved_alternatives = await self._alternatives.replace_for_scoring(
            scoring.id,
            [
                ScoringAlternative(
                    alternative_component_id=a.alternative_component_id,
                    notes=a.notes,
                )
                for a in payload.alternatives
            ],
        )

        # 4. Update the cache on `components` so the list page reflects the new
        # score/tier without a JOIN.
        await self._session.execute(
            update(ComponentModel)
            .where(ComponentModel.id == component_id)
            .values(nato_score=payload.nato_score, tier=payload.tier)
        )

        logger.info(
            "nato_scoring.created",
            component_id=str(component_id),
            scoring_id=str(scoring.id),
            nato_score=payload.nato_score,
            tier=payload.tier,
        )

        return ScoringBundle(
            scoring=scoring,
            classifications=saved_classifications,
            alternatives=saved_alternatives,
        )
