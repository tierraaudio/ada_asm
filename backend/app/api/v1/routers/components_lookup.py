"""HTTP route for `GET /api/v1/components/lookup`.

Pre-fills the "Nuevo componente" form by walking the enabled suppliers
in priority order, merging their quotes progressively, and returning a
single payload.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.dependencies import require_user
from app.api.v1.schemas.lookup import LookupResponse
from app.application.services.component_lookup_service import lookup_by_mpn
from app.domain.entities.user import User

router = APIRouter(prefix="/components", tags=["components"])


@router.get(
    "/lookup",
    response_model=LookupResponse,
    summary="Look up a component by MPN across all enabled suppliers",
)
async def get_component_lookup(
    _user: Annotated[User, Depends(require_user)],
    mpn: Annotated[
        str,
        Query(
            ...,
            min_length=3,
            max_length=60,
            description=(
                "Manufacturer part number. Case-insensitive; trimmed. "
                "Walks suppliers in `SUPPLIER_LOOKUP_PRIORITY` order."
            ),
        ),
    ],
    force_refresh: Annotated[
        bool,
        Query(
            description=(
                "Bypass the 15-minute Redis cache and re-query every "
                "enabled supplier. Use when the operator just edited "
                "data upstream and wants the fresh state."
            ),
        ),
    ] = False,
) -> LookupResponse:
    return await lookup_by_mpn(mpn.strip(), force_refresh=force_refresh)
