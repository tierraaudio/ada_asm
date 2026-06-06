"""API version 1 — aggregates routers under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    auth,
    components,
    components_lookup,
    config,
    customers,
    health,
    modules,
    projects,
    supplier_sync,
    suppliers,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
# `components_lookup.router` MUST be registered BEFORE `components.router`
# so `GET /components/lookup` is matched literally instead of being routed
# into the `/components/{component_id}` UUID-typed path (which would 422).
api_v1_router.include_router(components_lookup.router)
api_v1_router.include_router(components.router)
api_v1_router.include_router(modules.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(customers.router)
api_v1_router.include_router(suppliers.router)
api_v1_router.include_router(supplier_sync.router)
api_v1_router.include_router(config.router)
