"""Domain entity for a family-mapping rule.

One rule translates a single supplier category signal (a stable
`category_id`, an HS `tariff_prefix`, or a localized `name_keyword`) into
one internal family. `FamilyInferenceService` evaluates these by signal
strength. See change `ingest-component-from-mpn` (family-inference).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

MatchType = Literal["category_id", "tariff_prefix", "name_keyword"]


@dataclass
class ComponentFamilyRule:
    supplier: str
    match_type: MatchType
    match_value: str
    family: str
    confidence: int = 0
    priority: int = 0
    enabled: bool = True
    notes: str | None = None
    id: UUID = field(default_factory=uuid4)
