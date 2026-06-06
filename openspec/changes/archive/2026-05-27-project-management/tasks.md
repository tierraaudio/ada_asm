# Tasks — project-management

Order is suggested for incremental delivery. Each numbered section can be its own commit. The implementation can be fractioned, but the change is one.

## 0. Refactor — generalize `AddChildModal` (frontend only) `[FE]`

- [x] 0.1 Rename `AddChildModalProps.parentModuleId` → `parentId: string`; add optional `parentLabel?: string` prop. No other behaviour change. Update the type and the JSX header copy to use `parentLabel ?? "este elemento"`.
- [x] 0.2 Update the existing callsite in `frontend/src/features/modules/pages/ModuleEditPage.tsx` to pass `parentId={module.id}` + `parentLabel={module.name}`.
- [x] 0.3 Run typecheck + lint + existing tests — all green. No behaviour change for modules.

## 1. Backend — domain + DB `[BE]`

- [x] 1.1 Add domain entity `Customer` (frozen dataclass) at `backend/app/domain/entities/customer.py` matching `specs/data-model.md`.
- [x] 1.2 Add `Project`, `ProjectStatus` Literal, `ProjectAggregates` dataclass at `backend/app/domain/entities/project.py`.
- [x] 1.3 Add `ProjectChild` (frozen dataclass) at `backend/app/domain/entities/project_child.py`.
- [x] 1.4 Add repository Protocols `CustomerRepository` and `ProjectRepository` at `backend/app/domain/repositories/` (mirror `ModuleRepository` shape: `list`, `get`, `get_by_code`, `create`, `update`, `soft_delete`; for projects also `list_children`, `get_child`, `add_child`, `update_child`, `remove_child`, `list_for_component`, `list_for_module`).
- [x] 1.5 Add error classes to `backend/app/core/exceptions.py`: `ProjectNotFoundError`, `ProjectCodeAlreadyRegisteredError`, `CustomerNotFoundError`, `CustomerHoldedIdAlreadyRegisteredError`, `InvalidChildReferenceError` (if not already shared with modules), `ChildAlreadyPresentError` (likewise). RFC 7807 stable codes.
- [x] 1.6 Create SQLAlchemy models at `backend/app/infrastructure/db/models/customer.py`, `project.py`, `project_child.py` with all CHECK / UNIQUE / FK constraints from `specs/data-model.md`.
- [x] 1.7 Register the new models in `backend/app/infrastructure/db/models/__init__.py`.
- [x] 1.8 Generate an Alembic revision `project_management__customers_projects_children` that:
  1. Creates `customers`, `projects`, `project_children`.
  2. Adds `fk_stock_events_project` FK on the existing `stock_events.project_id` column.
  3. Creates functional indexes (`uq_customers_holded_id_lower`, `uq_projects_code_lower`, `ix_projects_name_lower`) via `op.execute(...)` (autogenerate skips functional indexes).
  4. `downgrade()` drops the FK first, then the three tables in reverse.
- [x] 1.9 Validate upgrade → downgrade → upgrade against the dev Postgres.

## 2. Backend — repositories + services `[BE]`

- [x] 2.1 Implement `SqlAlchemyCustomerRepository` against `AsyncSession` (`list`, `get`, `get_by_holded_id`, `create`, `update`, `delete`). Translate `IntegrityError` on `lower(holded_id)` to `CustomerHoldedIdAlreadyRegisteredError`.
- [x] 2.2 Implement `SqlAlchemyProjectRepository`: pagination + ILIKE search across `code`, `name`, `customer.name` (LEFT JOIN). Translate `IntegrityError` on `lower(code)` to `ProjectCodeAlreadyRegisteredError`. Implement `list_for_component(component_id)` and `list_for_module(module_id)` to feed the "projects-using" surfaces.
- [x] 2.3 Implement child CRUD on the project repo (`add_child`, `update_child`, `remove_child`, `list_children`). Translate the partial UNIQUE violations into `ChildAlreadyPresentError`. Validate that the referenced child entity actually exists (404 path) before insert.
- [x] 2.4 Implement `ProjectService.compute_aggregates(project_id, *, project_quantity_in_root=1)` reusing the `WITH RECURSIVE` walk already in `ModuleService`. Parameterize so the start node can be a project. Hydrate `current_price_per_100_eur` per leaf component using the existing `_hydrate_current_prices` helper. Same `MIN` semantics for nato_score (lexicographic `F<D<C<B<A<A+`), tier (numeric, Tier 1 worst), `aggregated_expires_at`. `buildable_stock` propagates the `floor(stock / qty_required)` minimum through the tree.
- [x] 2.5 Implement `ProjectService.list_price_history(project_id, period)` reusing the per-date supplier-price walk pattern from `ModuleService.list_price_history` (recursive descent + sum at each date).
- [x] 2.6 Implement `ProjectService.list_stock_events(project_id, page, page_size)` — paginate `stock_events WHERE project_id = ? ORDER BY occurred_at DESC` using the existing stock-event repo.
- [x] 2.7 Implement `ProjectService.soft_delete(project_id)` — sets `status='Archived'`, idempotent. PATCH transitions: when moving to `Delivered` and `fecha_entrega_real` not in body, auto-fill with `date.today()`.

## 3. Backend — schemas + routers `[BE]`

- [x] 3.1 Create `backend/app/api/v1/schemas/projects.py` with all schemas listed in `specs/api.md`: `ProjectStatus` Literal, `Customer*`, `Project*`, `ProjectChild*`, `Paginated*`, `AddProjectChildRequest`, `UpdateProjectChildRequest`, `ProjectPriceHistoryResponse`, `ConfigResponse`.
- [x] 3.2 Create `backend/app/api/v1/routers/projects.py` with the 9 project endpoints (list, create, get, patch, delete (soft), add-child, patch-child, delete-child, price-history, stock-events). All `Depends(require_user)`. Filter logic: list default excludes `Archived` unless `include_archived=true` or `status[]` is supplied without Archived being excluded.
- [x] 3.3 Create `backend/app/api/v1/routers/customers.py` with full CRUD.
- [x] 3.4 Add the cross-feature endpoints:
  - `GET /api/v1/components/{component_id}/projects-using` in the existing `components.py` router.
  - `GET /api/v1/modules/{module_id}/projects-using` in the existing `modules.py` router.
  Both reuse the `_project_summary` helper exposed from `projects.py` (same pattern used by `_module_summary` in module-management).
- [x] 3.5 Create `backend/app/api/v1/routers/config.py` with `GET /api/v1/config` returning `{holded_base_url}`. Register in the main API router.
- [x] 3.6 Add `HOLDED_BASE_URL: str = "https://app.holded.com"` to `backend/app/core/settings.py`.
- [x] 3.7 Wire all new routers into the main API include list and the OpenAPI doc.
- [x] 3.8 Verify RFC 7807 problem-detail rendering: every new error class maps to the right `type` URL + `code`.

## 4. Backend — seeds `[BE]`

- [x] 4.1 Create `backend/app/scripts/seed_projects.py` that:
  - Inserts 3 customers (`HLD-CUST-001`, `HLD-CUST-002`, `HLD-CUST-003`) per the seed dataset in `specs/data-model.md`.
  - Inserts 5 projects covering all 4 statuses + an empty-BOM Draft + a Delivered with `fecha_entrega_real`.
  - Builds the BOMs (mix of module + component edges, with quantities).
  - Inserts 4 consumption `stock_events` linking to the Active projects.
  - Refuses with exit 2 if `projects` is non-empty; `--reset` deletes `project_children`, `projects`, `customers` in that order before re-seeding (preserves modules + components + module-level stock_events).
  - Exits 3 if components or modules aren't seeded yet (helpful error pointing at the prior scripts).
- [x] 4.2 Add a sanity log line at the end: `Seeded N customers + M projects + K consumption stock_events.`.

## 5. Backend — tests `[BE]`

- [x] 5.1 Unit: `ProjectService.compute_aggregates` over synthetic DAGs — project→module→component, project→component direct, mixed, empty project. Assertions for each aggregate field.
- [x] 5.2 Unit: soft-delete behaviour (idempotency, status transition, list defaults).
- [x] 5.3 Unit: customer duplicate `holded_id` case-insensitive rejection.
- [x] 5.4 Unit: XOR validation on `AddProjectChildRequest` (Pydantic model_validator).
- [x] 5.5 Integration: every endpoint — happy + 401 + 404 + 422 + 409 paths.
- [x] 5.6 Integration: pagination boundaries on `GET /api/v1/projects`.
- [x] 5.7 Integration: search case-insensitive across `code`, `name`, `customer.name` (verify the LEFT JOIN works when customer is null).
- [x] 5.8 Integration: status filter — default excludes `Archived`; `include_archived=true` includes it; `status=Archived` alone returns only archived.
- [x] 5.9 Integration: `/components/{id}/projects-using` + `/modules/{id}/projects-using` — empty + populated paths.
- [x] 5.10 Integration: PATCH project to `Delivered` without `fecha_entrega_real` auto-fills with today.
- [x] 5.11 Integration: `seed_projects` happy + refusal + `--reset` flows.
- [x] 5.12 Coverage gate: backend stays at ≥ 80 %.

## 6. Frontend — types, api, hooks `[FE]`

- [x] 6.1 Create `frontend/src/features/projects/types.ts` mirroring `specs/api.md` schemas: `ProjectStatus`, `Customer`, `Project`, `ProjectSummary` (with aggregates), `ProjectChild`, `PaginatedProjects`, `ProjectFilters`, `ConfigResponse`.
- [x] 6.2 Create `frontend/src/features/projects/api/projects-api.ts` (typed axios methods for the 9 project endpoints + projects-using).
- [x] 6.3 Create `frontend/src/features/projects/api/customers-api.ts` (full CRUD).
- [x] 6.4 Create `frontend/src/features/projects/api/config-api.ts` (`getConfig()`).
- [x] 6.5 Create the TanStack Query hooks (one per endpoint as listed in `specs/frontend.md`).
- [x] 6.6 Add `useConfig()` with 10-minute `staleTime` and `["config"]` key.

## 7. Frontend — new components `[FE]`

- [x] 7.1 `features/projects/components/ProjectStatusBadge.tsx` (Figma colour mapping + hover tooltip listing all 4 statuses).
- [x] 7.2 `features/projects/components/CustomerLink.tsx` (renders `<a target="_blank" rel="noopener">` from `holded_url ?? config.holded_base_url + "/contact/" + holded_id`; disabled fallback when config is loading).
- [x] 7.3 `features/projects/components/ProjectHeaderCard.tsx` (left meta + right slot for `NatoScoringSummaryCard`).
- [x] 7.4 `features/projects/components/CreateCustomerModal.tsx` (inline modal called from the customer select).
- [x] 7.5 `features/shared/badges/ProjectsHierarchyRow.tsx` (shared compact one-line row used by the "Usado en proyectos" sections on Component + Module detail).

## 8. Frontend — pages `[FE]`

- [x] 8.1 `ProjectsListPage.tsx` per `specs/frontend.md`: header + search + FiltersDrawer (`status`, `customer_id`, `include_archived` toggle) + "+ Nuevo proyecto" + table + pagination + soft-delete from row action. Default rows exclude Archived. Empty/loading/error states.
- [x] 8.2 `ProjectDetailPage.tsx`: sticky `<DetailPageHeader>` + `<ProjectHeaderCard>` + "Contiene" via `<ModulesHierarchyTable directChildren expandable />` + "Histórico de precios" + "Histórico de eventos". Soft-delete dialog from the right-slot action.
- [x] 8.3 `ProjectEditPage.tsx`: same form shape as `ModuleEditPage` / `ComponentEditPage`. Fields per `specs/frontend.md`. Audit strip in edit. "Contiene" with `<ModulesHierarchyTable directChildren onRemoveChild />` + "+ Añadir hijo" → `<AddChildModal>`. Create-mode save-and-continue hand-off via `?add_child=1`.
- [x] 8.4 Register the 4 routes in `frontend/src/App.tsx` (replacing the placeholders).

## 9. Frontend — cross-feature additions `[FE]`

- [x] 9.1 Add the "Usado en proyectos" section to `ComponentDetailPage.tsx` below the existing "Pertenece a", fed by `useComponentProjectsUsing(id)`. Empty copy: "Este componente no se usa todavía en ningún proyecto.".
- [x] 9.2 Same on `ModuleDetailPage.tsx`, fed by `useModuleProjectsUsing(id)`. Empty copy: "Este módulo no se usa todavía en ningún proyecto.".
- [x] 9.3 Verify the nav stack `<` `>` correctly records jumps Component → Project and Module → Project.

## 10. Frontend — tests `[FE]`

- [x] 10.1 Component tests for `ProjectStatusBadge`, `CustomerLink`, `ProjectHeaderCard`, `ProjectsHierarchyRow` (cover empty/populated, URL build, tooltip, navigation click).
- [x] 10.2 Page test `ProjectsListPage`: default excludes Archived; toggling `include_archived` re-fetches with the param; search + URL sync; empty state.
- [x] 10.3 Page test `ProjectEditPage`: form validation (`code` required), create vs edit prefill, "+ Añadir hijo" save-and-continue hand-off (intercept POST, expect `navigate('/projects/{newId}/edit?add_child=1')`).
- [x] 10.4 Page test `ProjectDetailPage`: BOM renders rows; "Usado en proyectos" empty + populated; soft-delete dialog copy + invalidation.
- [x] 10.5 Hook test `useProjects` — filter + pagination state flows into the query key correctly.
- [x] 10.6 Coverage gate: frontend stays at ≥ 80 %.

## 11. E2E (Playwright `@smoke`) `[FE]`

- [x] 11.1 Authenticated user → `/projects` → opens seeded project → BOM visible → "Editar" → form pre-filled → change status to `Delivered` (assert `fecha_entrega_real` appears + auto-set) → save → returns to detail with updated badge.
- [x] 11.2 From a `ComponentDetailPage`, "Usado en proyectos" lists ≥ 1 project; clicking it navigates to the project; assert the `<` button on the project's header returns to the component (nav stack records the jump).
- [x] 11.3 Soft-delete: archive a project → it disappears from default list → toggle "Incluir archivados" → reappears with the Archived badge.
- [x] 11.4 Create-new flow including "+ Añadir hijo" via the finder (`AddChildModal` opens, picks an existing module, confirms, edge appears in the BOM).

## 12. Documentation `[BE+FE]`

- [x] 12.1 `ai-specs/specs/data-model.md`: add `Customer`, `Project`, `ProjectChild` sections (mirror Module / ModuleChild structure with all columns / constraints / indexes / migration reference). Update the existing high-level Project mention from "not yet implemented" to "✅ Implemented in `project-management`". Add a note to `StockEvent` section confirming the FK on `project_id` is now materialized.
- [x] 12.2 `ai-specs/specs/api-spec.yml`: add all new paths (`/api/v1/projects/*`, `/api/v1/customers/*`, `/projects-using` on components/modules, `/api/v1/config`) and the schemas (`Customer*`, `Project*`, `ProjectChild`, `PaginatedProjects`, `AddProjectChildRequest`, `UpdateProjectChildRequest`, `ProjectStatus`, `ConfigResponse`, `ProjectPriceHistoryResponse`). YAML must parse cleanly.
- [x] 12.3 `ai-specs/specs/development_guide.md`: new "Seed sample projects" subsection after the modules one (`python -m app.scripts.seed_projects`, `--reset` behaviour, dependency on prior seeds). Document `HOLDED_BASE_URL` env var (default + override).
- [x] 12.4 Run `/ai-specs:update-docs project-management` as the final check before archive.

## 13. Validation `[BE+FE]`

- [x] 13.1 BE: `ruff check` + `mypy` + full `pytest` green inside the dev container (DATABASE_URL pointing to Docker postgres).
- [x] 13.2 FE: `npx tsc --noEmit` + `eslint src` + `vitest run` all green.
- [x] 13.3 Docker stack: `docker compose build backend frontend && docker compose up -d` healthy. Seed in order: `seed_components` → `seed_modules` → `seed_projects`. Smoke check the 4 new routes and the cross-feature sections.
- [x] 13.4 Manual UX click-through against the live UI to validate the Figma frames at `lg`.
