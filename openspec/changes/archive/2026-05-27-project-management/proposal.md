# Project management — top-layer entity + customers id-link + BOM via finder

design-linked: true
scope:
  backend: true
  frontend: true
source: Manual
reference: drafts/enriched/project-management-20260525-1800.md (canonical), Figma 46:3 · 46:878 · 46:4038 · 1:3128

## Why

`Project` is the **top** of the asset tree (Proyecto → Módulo → Componente). Today the entity is referenced in `ai-specs/specs/data-model.md` as "not yet implemented", `stock_events.project_id` is nullable with the FK pending, and the `/projects` route in the SPA renders a placeholder. With `component-management` and `module-management` shipped, this is the missing layer that lets the team model real-world deliveries (BOM = Project containing modules + components), surface aggregated cost / NATO scoring at the deliverable level, and connect every project to its Holded customer for the upcoming sync US. The Figma is locked on four screens (list · detail · edit · soft-delete dialog) and we have the design system ready to reuse — `<ModulesHierarchyTable>`, `<DetailPageHeader>`, `<AddChildModal>`, badges and the filters drawer — so this US closes the hierarchy in a single change without re-inventing surfaces.

## What changes

### Backend

- Three new tables: `customers`, `projects`, `project_children`. The latter mirrors `module_children` exactly (XOR CHECK `child_module_id` / `child_component_id`, partial UNIQUE indexes, CASCADE on parent delete). No cycle detection is needed (projects are never hijos).
- `customers`: minimal id-link entity for the Holded sync surface. `holded_id` case-insensitive UNIQUE; `name` denormalised so the UI doesn't depend on Holded availability.
- `projects.status` is a DB-CHECK enum `Draft | Active | Delivered | Archived`. Soft-delete = transition to `Archived` (hard delete is never a user action).
- Materialize the previously-deferred FK `stock_events.project_id → projects.id ON DELETE SET NULL`. `stock_events.project_name_snapshot` (and any future customer denormalised columns) stay — append-only ledger.
- New domain entities (`Project`, `ProjectChild`, `Customer`) + repository Protocols + SQLAlchemy implementations.
- `ProjectService.compute_aggregates(project_id)` reuses the same `WITH RECURSIVE` walk shipped in `module-management`, parameterized so the start node is a project. Aggregates: `precio_total`, `aggregated_nato_score`, `aggregated_tier`, `aggregated_expires_at`, `buildable_stock`.
- Pydantic schemas under `app/api/v1/schemas/projects.py`.
- New REST surface (all `require_user`-protected, all errors RFC 7807):
  - `GET/POST /api/v1/projects`, `GET/PATCH/DELETE /api/v1/projects/{id}` (DELETE = soft-delete to `Archived`).
  - `POST/PATCH/DELETE /api/v1/projects/{id}/children` (add/patch/remove edges).
  - `GET /api/v1/projects/{id}/price-history`, `GET /api/v1/projects/{id}/stock-events`.
  - `GET/POST /api/v1/customers`, `GET/PATCH/DELETE /api/v1/customers/{id}`.
  - `GET /api/v1/components/{id}/projects-using`, `GET /api/v1/modules/{id}/projects-using` — drive the new "Usado en proyectos" sections.
  - `GET /api/v1/config` returning `{holded_base_url}` so the FE can build the customer URL.
- `app/core/settings.py` gains `HOLDED_BASE_URL` (default `"https://app.holded.com"`).
- New `seed_projects` script (~3 customers + ~5 projects covering all 4 statuses + a handful of consumption stock_events).

### Frontend

- Routes `/projects`, `/projects/new`, `/projects/:id`, `/projects/:id/edit` replace the placeholder. Same layout shell (`DashboardLayout`, sticky `DetailPageHeader` with `<` `>` nav-stack controls and the X close).
- **Maximum reuse, zero new variants** for everything already shipped:
  - `<ModulesHierarchyTable>` — direct reuse for the BOM. Generalize `<AddChildModal>` to accept `parentId` + `parentKind: 'module' | 'project'` so the same finder serves modules and projects. Update the existing `module-management` callsite in the same change.
  - `<FiltersDrawer>` for `status[]` + `customer_id[]` + an `include_archived` toggle.
  - `<DataTablePagination>`, `<ConfirmDeleteDialog>`, all badges, `<HistoricoPreciosChart>`, `<NatoScoringSummaryCard>` — all reused as-is.
- New components (all under `features/projects/components/` unless noted):
  - `ProjectHeaderCard` (metadata + aggregates side panel).
  - `ProjectStatusBadge` (4-colour pill + hover tooltip explaining the lifecycle).
  - `CustomerLink` (renders the Holded URL with `target=_blank rel=noopener`).
  - `CreateCustomerModal` (tiny inline modal called from the customer select in edit).
  - `features/shared/badges/ProjectsHierarchyRow.tsx` — compact one-line row for the "Usado en proyectos" sections (flat, no expand).
- New TanStack Query hooks under `features/projects/hooks/` mirroring the modules hooks shape. Plus `useCustomers`, `useCreateCustomer`, `useComponentProjectsUsing`, `useModuleProjectsUsing`, `useConfig`.
- **Cross-feature edits**: `ComponentDetailPage` and `ModuleDetailPage` gain a new section "Usado en proyectos" (below the existing "Pertenece a") fed by the new endpoints.

### Tests

- BE pytest (80 % gate): unit on aggregates over synthetic DAGs (project→module→component, project→component direct, mixed), soft-delete behaviour, customer duplicate `holded_id` rejection; integration for every endpoint (happy + 401 + 404 + 422 + 409), pagination boundaries, search across `code`/`name`/`customer.name`, status default-excludes-archived, XOR validation on add-child; seed script flows.
- FE Vitest (80 % gate): component tests for `ProjectStatusBadge`, `CustomerLink`, `ProjectHeaderCard`, `ProjectsHierarchyRow`; page tests for list/detail/edit (filters, validation, save-and-add-child hand-off); hook tests for `useProjects`.
- E2E Playwright `@smoke`: full create flow (incl. "+ Añadir hijo" finder); navigate from component detail → project via "Usado en proyectos" with the nav stack; soft-delete + include-archived toggle round-trip.

### Documentation

- `ai-specs/specs/data-model.md`: add `Customer`, `Project`, `ProjectChild` sections; update existing Project mention from "not yet implemented" to "✅ Implemented in `project-management`"; note that `stock_events.project_id` FK is now materialized.
- `ai-specs/specs/api-spec.yml`: extend with all new paths + schemas (`Customer`, `Project`, `ProjectSummary`, `ProjectChild`, `PaginatedProjects`, `ProjectCreate`, `ProjectUpdate`, `AddProjectChildRequest`, `UpdateProjectChildRequest`, `ProjectStatus`, `ConfigResponse`).
- `ai-specs/specs/development_guide.md`: new "Seed sample projects" subsection after the modules one; document `HOLDED_BASE_URL`.

## Capabilities

### New Capabilities

- `project-management`: top-layer entity (BOM, status lifecycle, soft-delete, customer link to Holded) closing the Project → Módulo → Componente hierarchy.

### Modified Capabilities

- None at the spec-level. Cross-feature touches (the new "Usado en proyectos" section on component / module detail; the generalization of `<AddChildModal>` to accept a project parent) are described in this change's `specs/frontend.md` and don't change the existing capability requirements.

## Impact

- **DB**: 3 new tables + 1 FK materialization on `stock_events`. All forward-only; reversible Alembic migrations.
- **API**: 15 new endpoints (10 project, 5 customer, 2 "projects-using", 1 config). No breaking changes to existing surfaces.
- **FE**: 1 new feature folder (`features/projects/`) + 2 cross-feature additions (Component/Module detail "Usado en proyectos") + 1 small refactor (`<AddChildModal>` parent generalization with the modules callsite updated in the same change). No new runtime deps.
- **Docs**: `data-model.md`, `api-spec.yml`, `development_guide.md` extended.
- **Env**: new `HOLDED_BASE_URL` setting (sensible default).
- **Seeds**: new `seed_projects` script; `seed_modules` and `seed_components` unchanged.
