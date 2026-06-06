<!-- BEGIN_ENRICHED_USER_STORY -->
# Enriched User Story

design-linked: true
scope:
  backend: true
  frontend: true
source: Manual
reference: N/A — backlog US 8 ("Gestión de Proyectos" — top layer of asset hierarchy)

## Title

Project management — top-layer entity (CRUD + list + detail + edit + soft-delete + BOM via finder) + customers id-link to Holded + pixel-perfect UI

## Problem / Context

`Project` is the top of the asset tree (Proyecto → Módulo → Componente). Today the entity is referenced in `ai-specs/specs/data-model.md` as "not yet implemented", `stock_events.project_id` is nullable with the FK pending the entity, and the `/projects` route in the SPA renders a placeholder shell.

The Figma file has four locked screens covering the full project lifecycle:

- List with search + status/customer filters + pagination.
- Detail with the project card, BOM tree, "Histórico" surfaces, and aggregated NATO score.
- Create / edit form with all editable fields.
- Delete dialog — soft-delete (status → Archived).

There is also an obsolete "Añadir módulo" inline-form screen in Figma that we are NOT building. The "+ Añadir hijo" affordance in the project edit/detail reuses the existing `<AddChildModal>` finder pattern already shipped by `module-management`. Creating a brand-new module/component is done from `/modules/new` or `/components/new` — never inlined inside a project.

The US closes the gap end-to-end: domain entity + persistence + REST API + protected SPA pages, all pixel-faithful to those frames at the `lg` breakpoint, with **maximum reuse of existing primitives** (`ModulesHierarchyTable`, `DetailPageHeader`, `DetailNavStack`, `AddChildModal`, `FiltersDrawer`, badges, charts).

## Desired Outcome

An authenticated user can:

1. Open `/projects` and see the catalogue table.
2. Search by `code` / `name` / customer name; filter by `status` and `customer_id`.
3. Open a project detail and see its BOM as the canonical `<ModulesHierarchyTable>` (modules + components, expandable).
4. Add an existing module or component to the project via `<AddChildModal>` (no inline create form).
5. Remove a child — removes the edge, never the underlying entity.
6. Edit project metadata via the form (same shape as ModuleEditPage / ComponentEditPage).
7. "Delete" a project — soft → `Archived`, hidden from default list views (opt-in toggle to include them).
8. Click the project's Holded customer id and land on the customer's Holded page in a new tab.
9. From any component / module detail, see a new "Usado en proyectos" section listing the projects that reference it.

## Acceptance Criteria

### Backend

#### Schema

- New table `customers`:
  - `id` UUIDv4, PK, default `gen_random_uuid()`.
  - `holded_id` `varchar(64)`, NOT NULL — case-insensitive UNIQUE via functional index `uq_customers_holded_id_lower (lower(holded_id))`.
  - `name` `varchar(200)`, NOT NULL.
  - `holded_url` `varchar(500)`, nullable — explicit override; if null, the FE builds the URL from `HOLDED_BASE_URL + /contact/ + holded_id`.
  - `notas` `text`, nullable.
  - `created_at` / `updated_at` `timestamptz`.

- New table `projects`:
  - `id` UUIDv4, PK, default `gen_random_uuid()`.
  - `code` `varchar(40)`, NOT NULL — case-insensitive UNIQUE via `uq_projects_code_lower (lower(code))`; user-typed, no auto-generation.
  - `name` `varchar(200)`, NOT NULL.
  - `description` `text`, nullable.
  - `status` `varchar(20)`, NOT NULL, default `'Draft'` — CHECK in `('Draft', 'Active', 'Delivered', 'Archived')`.
  - `customer_id` UUIDv4, nullable, FK → `customers.id` ON DELETE SET NULL.
  - `fecha_inicio` `date`, nullable.
  - `fecha_entrega_estimada` `date`, nullable.
  - `fecha_entrega_real` `date`, nullable — set when status transitions to `Delivered`.
  - `notas` `text`, nullable.
  - `created_at` / `updated_at` `timestamptz`.
  - **Indexes**: `uq_projects_code_lower`, `ix_projects_name_lower`, `ix_projects_status`, `ix_projects_customer_id`.

- New table `project_children` (mirrors `module_children` exactly; no cycle detection because projects can't be hijos):
  - `id` UUIDv4, PK.
  - `parent_project_id` UUIDv4, NOT NULL, FK → `projects.id` ON DELETE CASCADE.
  - `child_module_id` UUIDv4, nullable, FK → `modules.id` ON DELETE CASCADE.
  - `child_component_id` UUIDv4, nullable, FK → `components.id` ON DELETE CASCADE.
  - `quantity` `smallint`, NOT NULL, CHECK `> 0`.
  - `sort_order` `integer`, NOT NULL, default 0.
  - `notes` `text`, nullable.
  - `created_at` / `updated_at` `timestamptz`.
  - CHECK XOR: `(child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1`.
  - Partial UNIQUE `uq_project_children_parent_child_module (parent_project_id, child_module_id) WHERE child_module_id IS NOT NULL`.
  - Partial UNIQUE `uq_project_children_parent_child_component (parent_project_id, child_component_id) WHERE child_component_id IS NOT NULL`.
  - Non-unique indexes: `(parent_project_id, sort_order)`, `(child_module_id)`, `(child_component_id)`.

- Migration on `stock_events`: materialize the previously-deferred FK:
  - `ALTER TABLE stock_events ADD CONSTRAINT fk_stock_events_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL`.
  - `stock_events.project_name_snapshot` and the existing customer denormalised pair remain unchanged (append-only ledger semantics).

- All migrations apply + reverse cleanly.

#### Domain & repositories

- New domain entities under `app/domain/entities/`: `Project`, `ProjectChild`, `Customer` (dataclasses with explicit types).
- New repository Protocols under `app/domain/repositories/`: `ProjectRepository`, `CustomerRepository`.
- SQLAlchemy implementations under `app/infrastructure/repositories/` mirroring the modules repo shape (filters, pagination, child CRUD, parents/users-of lookups).

#### Aggregates (server-computed at read time)

- New `ProjectService.compute_aggregates(project_id)` returns `precio_total`, `aggregated_nato_score`, `aggregated_tier`, `aggregated_expires_at`, `buildable_stock` using the same `WITH RECURSIVE` walk that `ModuleService` uses, parameterized so the start node is a project. Recursion descends through `project_children → module_children` until reaching component leaves.
- Empty project returns `precio_total=null`, `aggregated_*=null`, `buildable_stock=0`.

#### Pydantic schemas

- Under `app/api/v1/schemas/projects.py`:
  - `CustomerResponse`.
  - `ProjectStatus` literal `Draft | Active | Delivered | Archived`.
  - `ProjectBase`, `ProjectAggregatesPayload`, `ProjectSummaryResponse` (project + aggregates + embedded customer summary), `ProjectResponse` (Summary + hydrated children), `ProjectChildResponse`, `PaginatedProjects`.
  - `ProjectCreateRequest`, `ProjectUpdateRequest`, `AddProjectChildRequest`, `UpdateProjectChildRequest`, `CustomerCreateRequest`, `CustomerUpdateRequest`.

#### Endpoints — all protected by `require_user`, all errors RFC 7807

##### Projects

- `GET /api/v1/projects` — paginated catalogue with aggregates hydrated server-side.
  - Query params: `q` (case-insensitive over `code`, `name`, `customer.name`); `status` (repeatable; default = all statuses **except** `Archived`); `include_archived` (bool, default false; when true, lifts the Archived exclusion); `customer_id` (repeatable, UUID); `page` (default 1); `page_size` (default 25, max 100).
  - Returns `PaginatedProjects`.
- `POST /api/v1/projects` — create. `409 PROJECT_CODE_ALREADY_REGISTERED` on duplicate (case-insensitive).
- `GET /api/v1/projects/{id}` — detail (project + aggregates + children hydrated + customer summary).
- `PATCH /api/v1/projects/{id}` — partial update. Immutable: `id`, `created_at`, `updated_at`. `code` IS mutable. Transitioning to `Delivered` requires (or auto-sets) `fecha_entrega_real = today()`.
- `DELETE /api/v1/projects/{id}` — **soft-delete**: sets `status='Archived'`, returns 204. Idempotent on missing (404). Never hard-deletes; preserves `project_children` so historical stock_events remain traceable.
- `POST /api/v1/projects/{id}/children` — add edge. Payload `{child_module_id XOR child_component_id, quantity, notes?, sort_order?}`. 422 on XOR violation, 409 on duplicate edge.
- `PATCH /api/v1/projects/{id}/children/{child_id}` — patch `quantity` / `notes` / `sort_order`.
- `DELETE /api/v1/projects/{id}/children/{child_id}` — remove the edge (the referenced module/component is NOT touched). 204; idempotent.
- `GET /api/v1/projects/{id}/price-history` — same shape as `/modules/{id}/price-history`: `{period: 'week'|'month'|'year', points: [{date, price}]}`.
- `GET /api/v1/projects/{id}/stock-events` — paginated `stock_events` filtered by `project_id`, ordered by `occurred_at DESC`.

##### Customers

- `GET /api/v1/customers` — list all (no pagination yet; small dataset until Holded sync ships). Returns `CustomerResponse[]`.
- `POST /api/v1/customers` — create with `{holded_id, name, holded_url?, notas?}`. 409 on duplicate `holded_id` (case-insensitive).
- `GET /api/v1/customers/{id}` — single.
- `PATCH /api/v1/customers/{id}` — partial.
- `DELETE /api/v1/customers/{id}` — 204; FK on projects is ON DELETE SET NULL so dangling references are auto-cleared.

##### "Usado en proyectos" surfaces

- `GET /api/v1/components/{id}/projects-using` — returns `ProjectSummary[]` for projects with a direct edge `project_children.child_component_id = {id}`.
- `GET /api/v1/modules/{id}/projects-using` — same for modules (direct edge only, no recursion into module ancestors).
- The existing `/parents` endpoints on components and modules are NOT touched.

##### Config

- Add `HOLDED_BASE_URL` to `app/core/settings.py` (default `"https://app.holded.com"`).
- Add a tiny `GET /api/v1/config` endpoint (auth-gated) returning `{holded_base_url: str}` if a config endpoint doesn't already exist. The FE uses it to build the customer link.

#### Seed scripts

- New `python -m app.scripts.seed_projects` that, after `seed_components` + `seed_modules`, inserts:
  - ~3 sample customers with Holded-ish ids (e.g. `HLD-CUST-001`, `HLD-CUST-002`, `HLD-CUST-003`).
  - ~5 sample projects mixing the seeded modules + components into BOMs that exercise the aggregates: one `Active`, one `Delivered` (with `fecha_entrega_real`), one `Archived`, one `Draft`, one `Active` with mixed module + component children.
  - A handful of consumption `stock_events` linking to one of the projects so the historial view has rows.
- Idempotent: refuses with exit 2 to re-seed if any project exists; `--reset` deletes `project_children`, `projects`, and `customers` in that order before re-seeding. Exits 3 if components or modules aren't seeded yet.

### Frontend

#### Routes (replace placeholders)

- `/projects` → `ProjectsListPage` (Figma 46:3).
- `/projects/new` → `ProjectEditPage mode="create"` (Figma 46:4038).
- `/projects/:id` → `ProjectDetailPage` (Figma 46:878).
- `/projects/:id/edit` → `ProjectEditPage mode="edit"` (Figma 46:4038).

All routes mount inside `DashboardLayout` and use the sticky `DetailPageHeader` (X + `<` `>` nav-stack controls + right action slot).

#### Reused primitives — no new variants

- `DashboardLayout`, `DetailPageHeader`, `DetailNavStack`, `DetailNavControls` (push pathname on mount, reset on X via `DetailPageHeader`).
- `FiltersDrawer` for `status[]` + `customer_id[]` (groups + value/apply pattern, identical to modules/components lists).
- `DataTablePagination`.
- `ConfirmDeleteDialog` for the soft-delete dialog — copy says "Mover a Archivados", confirm label "Archivar".
- `ModulesHierarchyTable` — direct reuse for the BOM. Passed `directChildren={project.children}` it already renders module + component children (XOR per row) with the existing `onRemoveChild` callback to detach an edge.
- `AddChildModal` — reused as-is for the "+ Añadir hijo" finder. The component already accepts a parent identifier; if a prop rename is needed for clarity, generalize to `parentId` + `parentKind: 'module' | 'project'` and update the modules callsite accordingly.
- `FamilyChip`, `NatoScoreBadge`, `TierBadge`, `StockStatusBadge` (with `supplier_stock_summary` already wired on component hijos), `NatoScoringSummaryCard`.
- `HistoricoPreciosChart` for the project price-history pane.

#### New components

- `features/projects/components/ProjectHeaderCard.tsx` — header card (code, name, status badge, customer link, fechas, aggregates side panel à la `ModuleHeaderCard`).
- `features/projects/components/ProjectStatusBadge.tsx` — small pill with 4-colour mapping: `Draft` muted, `Active` emerald, `Delivered` indigo, `Archived` grey. Hover tooltip explains the lifecycle.
- `features/projects/components/CustomerLink.tsx` — renders `<a target="_blank" rel="noopener" href={config.holded_base_url + "/contact/" + holded_id}>{name}</a>` with a small chip showing the `holded_id`.
- `features/projects/components/CreateCustomerModal.tsx` — inline tiny modal (holded_id + name) called from the customer select in `ProjectEditPage`; POSTs to `/api/v1/customers` and selects the newly created row.
- `features/shared/badges/ProjectsHierarchyRow.tsx` — compact one-line row used by the "Usado en proyectos" sections on component & module details. Same look-and-feel as `<ModulesHierarchyTable>` rows but flat (no expand). Columns: code, name, status badge, customer chip, action (ver).

#### "Usado en proyectos" sections

- New section on `ComponentDetailPage` (below the existing "Pertenece a"): heading "Usado en proyectos", fed by `useComponentProjectsUsing(id)`. Empty state copy: "Este componente no se usa todavía en ningún proyecto".
- Same on `ModuleDetailPage` (below its existing "Pertenece a"), fed by `useModuleProjectsUsing(id)`.

#### Pages

##### ProjectsListPage

- Header + search input + `FiltersDrawer` (`status[]` + `customer_id[]` + `include_archived` toggle) + "+ Nuevo proyecto" button.
- Table columns (Figma 46:3): Código, Nombre, Cliente (CustomerLink), Estado (ProjectStatusBadge), NATO agregado, Tier, Precio total, Fecha entrega estimada, Acciones (ver + borrar (soft-delete)).
- Default rows exclude `Archived`. The drawer exposes "Incluir archivados" toggle.
- Loading + error + empty states.
- Pagination via `DataTablePagination`.

##### ProjectDetailPage

- Sticky `DetailPageHeader` (X + nav controls + "Editar proyecto" right slot).
- `ProjectHeaderCard` (left: metadata — code, name, status, customer link, fechas; right: aggregated `NatoScoringSummaryCard`).
- "Contiene" section with `<ModulesHierarchyTable directChildren={project.children} expandable />` (no onRemoveChild here — that's edit-mode only).
- "Histórico de precios" pane (`HistoricoPreciosChart` + week/month/year period toggle).
- "Histórico de eventos" pane — table of stock_events tied to the project (consumption + future delivered).
- Soft-delete via `<ConfirmDeleteDialog>` triggered from the right slot's overflow / icon button.

##### ProjectEditPage

- Same shape as `ModuleEditPage` / `ComponentEditPage`.
- Form fields: Código (required, mutable), Nombre, Descripción, Estado (Select), Cliente (Select from `useCustomers()` + inline "+ Nuevo cliente" affordance), Fecha inicio, Fecha entrega estimada, Fecha entrega real (only visible when Estado = `Delivered`), Notas.
- Audit strip (Fecha de creación / Última modificación) when editing.
- "Contiene" with `<ModulesHierarchyTable directChildren onRemoveChild />` + "+ Añadir hijo" button opening `<AddChildModal>`.
- In create mode, "+ Añadir hijo" triggers save-and-continue exactly like `ModuleEditPage`: persists the project first, then navigates to `/projects/{newId}/edit?add_child=1` and auto-opens the modal once the detail loads.

#### Customer admin in this US

- Out of scope as a full screen. Customers are created via the seed script and (later) via the Holded sync US. The Edit form provides a Select populated by `useCustomers()` plus a small inline "+ Nuevo cliente" affordance (`CreateCustomerModal`) that creates a customer and selects it.

#### TanStack Query hooks

- `useProjects(filters, page, pageSize)`, `useProjectDetail(id)`, `useCreateProject`, `useUpdateProject`, `useDeleteProject` (soft-delete), `useAddProjectChild`, `useRemoveProjectChild`, `useProjectPriceHistory(id, period, enabled)`, `useProjectStockEvents(id, enabled)`.
- `useCustomers()`, `useCreateCustomer()`.
- `useComponentProjectsUsing(id)`, `useModuleProjectsUsing(id)`.
- `useConfig()` (caches `/api/v1/config`).
- All wrap a single endpoint; mutations invalidate the relevant query keys (project detail, project list, the "projects-using" of any descendant on add/remove child).

#### Spanish copy

- All user-facing copy in Spanish (consistent with modules/components).
- All code, comments, log strings in English.

### Tests

#### Backend (pytest, 80% gate)

- Unit:
  - `ProjectService.compute_aggregates` over synthetic DAGs: project → module → component, project → component direct, mixed.
  - Soft-delete behaviour (DELETE flips status, list excludes it, `include_archived=true` resurfaces it).
  - Customer duplicate `holded_id` rejection (case-insensitive).
  - XOR validation on `project_children` (BE-level + DB CHECK).
- Integration:
  - Each endpoint — happy + 401 + 404 + 422 + 409.
  - Pagination boundaries.
  - Search case-insensitive across `code`, `name`, `customer.name`.
  - Status filter: default excludes Archived; `include_archived=true` includes it.
  - `/components/{id}/projects-using` + `/modules/{id}/projects-using` happy + empty.
  - `seed_projects` happy + refusal + `--reset` flows.

#### Frontend (Vitest, 80% gate)

- Component tests for `ProjectStatusBadge` (4 statuses + tooltip), `CustomerLink` (URL build from config), `ProjectHeaderCard`, `ProjectsHierarchyRow`.
- Page tests:
  - `ProjectsListPage` — filter excluding Archived by default, search, empty state, soft-delete from row action.
  - `ProjectEditPage` — form validation (`code` required), create vs edit, save-and-add-child hand-off via `?add_child=1`.
  - `ProjectDetailPage` — BOM renders, "Usado en proyectos" empty/populated paths, soft-delete dialog copy.
- Hook tests for filter+pagination state of `useProjects`.

#### E2E (Playwright @smoke)

- Authenticated user lands on `/projects` → sees seeded projects → opens one → lands on detail → BOM visible → clicks "Editar" → form pre-filled → changes status to `Delivered` (fecha_entrega_real becomes visible/auto-set) → saves → returns to detail with updated badge.
- From a component detail, "Usado en proyectos" lists at least one project; clicking it navigates to the project (and the `< >` nav-stack records the jump).
- Soft-delete: archive a project → it disappears from the default list → toggle "Incluir archivados" → it reappears with the Archived badge.
- Create-new flow including "+ Añadir hijo" via the finder.

### Documentation

- `ai-specs/specs/data-model.md`:
  - Add `Customer`, `Project`, `ProjectChild` sections (mirroring Module / ModuleChild structure).
  - Update the existing `Project` mention (was "not yet implemented") to "✅ Implemented in `project-management` (migration `<date>`)".
  - Update `StockEvent` section to note that `project_id` FK is now materialized.
- `ai-specs/specs/api-spec.yml`:
  - New paths: `/api/v1/projects`, `/api/v1/projects/{id}`, `/api/v1/projects/{id}/children`, `/api/v1/projects/{id}/children/{child_id}`, `/api/v1/projects/{id}/price-history`, `/api/v1/projects/{id}/stock-events`, `/api/v1/customers`, `/api/v1/customers/{id}`, `/api/v1/components/{id}/projects-using`, `/api/v1/modules/{id}/projects-using`, `/api/v1/config`.
  - New schemas: `Customer`, `CustomerCreate`, `CustomerUpdate`, `Project`, `ProjectSummary`, `ProjectChild`, `ProjectResponse`, `PaginatedProjects`, `ProjectCreate`, `ProjectUpdate`, `AddProjectChildRequest`, `UpdateProjectChildRequest`, `ProjectStatus`, `ConfigResponse`.
- `ai-specs/specs/development_guide.md`:
  - New "Seed sample projects" section after the modules one (`python -m app.scripts.seed_projects`, `--reset` behaviour, dependency on prior seeds).
  - Document `HOLDED_BASE_URL` env var (with default `https://app.holded.com`).

## Design References

Figma File:
https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm

Referenced Nodes:
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=46-3
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=46-878
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=46-4038
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=1-3128

Explicitly OBSOLETE — do NOT implement: https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=1-2450 (legacy "Añadir módulo" inline form). Replaced by the existing `<AddChildModal>` finder (a `module-management` primitive).

## Constraints / Notes

- Pixel-perfect at `lg` (1024+) for list/detail/edit, matching the Figma nodes above. Density is similar to modules.
- `code` is the natural business identifier the user owns (case-insensitive UNIQUE). NOT auto-generated. Editable (rename is supported; nothing else references `code`).
- "Borrar proyecto" is a SOFT-DELETE → `status='Archived'`. Hard-delete is not a user action in this US (only happens via cascade if the BBDD is reset).
- `Customer` is a thin id-link entity for the Holded sync surface (the actual Holded sync is a future US). The `holded_id` is what the user clicks; the FE renders the link as `${HOLDED_BASE_URL}/contact/${holded_id}` unless the row has an explicit `holded_url` override.
- Project memberships / roles are OUT OF SCOPE (future US). Authorization in this US is the existing `require_user`.
- Reuse `<AddChildModal>` and `<ModulesHierarchyTable>` as-is. If either needs a tiny tweak (e.g. an extra parent prop on the modal), prefer a generic prop name (`parentId` + `parentKind: 'module' | 'project'`) so the same primitive serves both features. Update the existing modules callsite in the same PR to keep the API consistent.
- No new runtime deps expected. Recharts is already in for the price chart.
<!-- END_ENRICHED_USER_STORY -->
