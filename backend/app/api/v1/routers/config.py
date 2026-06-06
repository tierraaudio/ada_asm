"""Small config endpoint — exposes runtime values the FE needs (e.g. Holded base URL)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import require_user
from app.api.v1.schemas.projects import ConfigResponse
from app.core.config import get_settings
from app.domain.entities.user import User

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config(
    _user: Annotated[User, Depends(require_user)],
) -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(holded_base_url=settings.holded_base_url)
