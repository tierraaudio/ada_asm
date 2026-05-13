"""API version 1 — aggregates routers under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import health

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
