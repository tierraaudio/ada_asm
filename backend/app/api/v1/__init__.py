"""API version 1 — aggregates routers under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import auth, health

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
