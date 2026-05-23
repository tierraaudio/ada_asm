<!-- BEGIN_ENRICHED_USER_STORY -->
# Enriched User Story

design-linked: true
scope:
  backend: true
  frontend: true
source: Manual
reference: N/A — backlog US 4 ("Creación de Componentes en ASM" from docs/overview.md)

## Title
Component management — CRUD + list + detail + purchase history + NATO scoring + pixel-perfect UI

## Problem / Context
`Componente` is the leaf of the asset tree (`Proyecto → Módulo → Componente`) and the catalogue our team operates against day to day. Today the backend has no `components` table, no endpoints, and the `/components`, `/components/new`, `/components/:id`, `/components/:id/purchases`, `/components/:id/nato`, `/components/:id/edit` routes added in the previous change (`dashboard-shell-redesign`) all render the placeholder shell. The Figma file has five locked frames covering the full lifecycle:

- List with search, badges and a sync action (Figma 47:15264).
- Detail with the component card and a chart (Figma 47:16048).
- Purchase history with table + cost trend chart (Figma 47:20273).
- NATO scoring breakdown with explanatory legend (Figma 47:21897).
- Create / edit form (Figma 47:17405).

This US closes the gap end-to-end: domain entity + persistence + REST API + protected SPA pages, all pixel-faithful at the `lg` breakpoint, with seed data so the experience works on a fresh clone without needing real supplier data.

## Desired Outcome
An authenticated user can:
1. Open `/components` and see the catalogue table seeded with ~10 sample rows.
2. Search by MPN / SKU / name / family with case-insensitive matching.
3. Filter by tier, NATO score, family, supplier.
4. Open a component detail; switch between the three tabs (Detalle / Historial / Scoring OTAN); see the stock + cost charts populated with real data from the DB.
5. Create a new component or edit an existing one via the form; client-side and server-side validation paths produce useful error states.
6. Trigger the "Sincronizar" placeholder action which returns 202 (real upstream sync lives in US 5 / 6 / 7).
7. Hover the "Scoring OTAN" question mark to see the rubric.

## Acceptance Criteria

### Backend — entities and persistence

- New SQLAlchemy models `ComponentModel` and `ComponentPurchaseModel` under `backend/app/infrastructure/db/models/`. Both inherit `Base + TimestampMixin`.
- Schema (Alembic migration `<ts>_component_management__components_and_purchases.py`):
  - `components`:
    - `id` UUIDv4 PK, default `gen_random_uuid()`.
    - `mpn` `varchar(100)`, unique, not null.
    - `sku` `varchar(100)`, nullable.
    - `name` `varchar(200)`, not null.
    - `family` `varchar(100)`, not null.
    - `description` `text`, nullable.
    - `datasheet_url` `text`, nullable.
    - `location` `varchar(100)`, nullable.
    - `supplier` `varchar(100)`, nullable.
    - `price_per_100` `numeric(12, 4)`, nullable.
    - `stock` `integer`, not null, default `0`, check `stock >= 0`.
    - `tier` `varchar(2)`, not null, check in `('A+', 'A', 'B', 'C', 'D')`.
    - `nato_score` `varchar(20)`, not null, check in `('100_otan', 'otan', 'allied_otan', 'neutral', 'high_risk', 'no_otan')`.
    - `country_of_origin` `char(2)`, nullable (ISO 3166-1 alpha-2).
    - `created_at` / `updated_at` `timestamptz` server-defaulted.
    - Indexes: `lower(mpn)`, `lower(sku)`, `lower(name)`, `lower(family)` for fast case-insensitive search; composite `(family, supplier)`.
  - `component_purchases`:
    - `id` UUIDv4 PK.
    - `component_id` UUIDv4 FK → `components.id` ON DELETE CASCADE.
    - `purchased_at` `date`, not null.
    - `quantity` `integer`, not null, check `quantity > 0`.
    - `supplier` `varchar(100)`, not null.
    - `unit_cost` `numeric(12, 4)`, not null.
    - `total_cost` `numeric(14, 4)`, not null.
    - `currency` `varchar(3)`, not null, default `'EUR'`.
    - `created_at` / `updated_at`.
    - Index: `(component_id, purchased_at DESC)`.
- Migration is reversible end-to-end.
- Domain entities `Component` and `ComponentPurchase` under `backend/app/domain/entities/` are plain frozen dataclasses; no SQLAlchemy imports.
- Repository Protocols under `backend/app/domain/repositories/` cover the operations the service layer needs (list-with-filters, get-by-id, save, update, delete, list-purchases, save-purchase).
- SQLAlchemy implementations under `backend/app/infrastructure/repositories/` mirror the existing pattern (translate model ↔ entity, raise `ComponentNotFoundError` and `ComponentMpnAlreadyRegisteredError` on the right edges).

### Backend — application service

- `ComponentsService` under `backend/app/application/services/components_service.py` exposing:
  - `list(filters: ComponentFilters, page: int, page_size: int) -> Page[Component]`.
  - `get(component_id: UUID) -> Component`.
  - `create(payload: ComponentCreate) -> Component`.
  - `update(component_id: UUID, payload: ComponentUpdate) -> Component`.
  - `delete(component_id: UUID) -> None`.
  - `list_purchases(component_id: UUID, page, page_size) -> Page[ComponentPurchase]`.
  - `enqueue_sync(component_id: UUID) -> None` — placeholder, emits `auth.tag = "components.sync.placeholder"` info log and returns.
- Filters DTO covers `q`, `family`, `supplier`, `tier`, `nato_score`. The `q` search is case-insensitive against MPN, SKU, name and family combined with `OR`.
- Pagination DTO `Page[T] = { items: list[T]; total: int; page: int; page_size: int }`. Defaults: `page=1`, `page_size=25`, max `100`.

### Backend — HTTP

- Pydantic schemas in `backend/app/api/v1/schemas/components.py`:
  - `TierLiteral = Literal["A+", "A", "B", "C", "D"]`.
  - `NatoScoreLiteral = Literal["100_otan", "otan", "allied_otan", "neutral", "high_risk", "no_otan"]`.
  - `ComponentResponse`, `ComponentCreateRequest`, `ComponentUpdateRequest` (all fields optional), `PaginatedComponents`, `ComponentPurchaseResponse`, `PaginatedComponentPurchases`, `ComponentSyncResponse`.
- Router under `backend/app/api/v1/routers/components.py`, registered into `api_v1_router`. All routes require `Depends(require_user)`.
- Endpoints:
  - `GET /api/v1/components` — paginated list with the documented filters.
  - `POST /api/v1/components` — 201 + body; 409 `MPN_ALREADY_REGISTERED` on dup.
  - `GET /api/v1/components/{id}` — 200; 404 `COMPONENT_NOT_FOUND`.
  - `PATCH /api/v1/components/{id}` — 200; ignores `mpn` / `id` / `created_at` / `updated_at`.
  - `DELETE /api/v1/components/{id}` — 204; idempotent on missing.
  - `GET /api/v1/components/{id}/purchases` — paginated, `purchased_at DESC`.
  - `POST /api/v1/components/{id}/sync` — 202 with `{ "status": "queued" }`.
- New domain exceptions `ComponentNotFoundError` (404 / `COMPONENT_NOT_FOUND`) and `ComponentMpnAlreadyRegisteredError` (409 / `MPN_ALREADY_REGISTERED`) added to `app/core/exceptions.py`.
- All errors RFC 7807 with stable `code`.
- OpenAPI auto-generated tags `components` group the routes.

### Backend — seed script

- `python -m app.scripts.seed_components` inserts ~10 sample components matching the Figma copy (ACS712, B340A, BME280, ESP32-WROOM-32E, LM2596, NE555, MAX232, STM32F407VGT6, ATmega328P, plus one with extreme NATO classification for the "Alto riesgo" badge). Each component also gets 3-6 `ComponentPurchase` rows spread across the last 12 months so the charts render real-looking data.
- Refuses with exit 2 if any component already exists, UNLESS `--reset` is passed (in which case the script truncates `component_purchases` then `components` first).

### Frontend — feature tree

- `frontend/src/features/components/` with the following structure:
  - `api/components-api.ts` — typed client mirroring `auth-api.ts`.
  - `hooks/use-components.ts`, `use-component.ts`, `use-component-purchases.ts`, `use-component-mutations.ts`.
  - `types.ts` — `Component`, `ComponentPurchase`, `TierValue`, `NatoScoreValue`, `ComponentFilters`, `Paginated<T>`.
  - `schemas.ts` — zod schemas for create + edit, derived from the backend Pydantic shape; `name.min(1)`, `mpn.min(1)`, valid tier / nato_score enums, `stock >= 0`, `price_per_100 >= 0`.
  - `components/TierBadge.tsx`, `components/NatoScoreBadge.tsx`, `components/NatoScoreHelpPopover.tsx`, `components/CountryOfOriginSelect.tsx`.
  - `pages/ComponentsListPage.tsx`, `ComponentDetailPage.tsx`, `ComponentEditPage.tsx`, `ComponentPurchaseHistoryPage.tsx`, `ComponentNatoScoringPage.tsx`.

### Frontend — routes wiring (`src/App.tsx`)

Replace the placeholder elements added in `dashboard-shell-redesign` so they render the real pages:

- `/components` → `<ComponentsListPage />`.
- `/components/new` → `<ComponentEditPage mode="create" />`.
- `/components/:id` → `<ComponentDetailPage />`.
- `/components/:id/purchases` → `<ComponentPurchaseHistoryPage />`.
- `/components/:id/nato` → `<ComponentNatoScoringPage />`.
- `/components/:id/edit` → `<ComponentEditPage mode="edit" />`.

All routes stay under `<RequireAuth />` and use the existing `DashboardLayout` (Header + collapsible Sidebar from `dashboard-shell-redesign`).

### Frontend — list page (Figma 47:15264)

- Search input above the table — placeholder `"Buscar por MPN, SKU, nombre o familia…"`. Debounced 300 ms; updates the `q` query param so the URL is shareable.
- Filter dropdowns: Familia, Supplier, Tier, NATO Score. Each is a shadcn `<Select>` with the values surfaced from the seeded data.
- "Sincronizar" button on the right side calls `POST /api/v1/components/{id}/sync` — for the list it actually calls the per-row sync action; documented as a future improvement to add a bulk-sync endpoint.
- "+ Nuevo componente" primary button (magenta), top-right; navigates to `/components/new`.
- Table columns: **MPN** (mono), **Nombre** (medium), **Familia**, **Ubicación**, **Supplier**, **Precio (100u)** (right-aligned, EUR-formatted), **Stock** (right-aligned), **Tier** (badge), **NATO** (badge), **Acciones** (kebab menu → "Ver", "Editar", "Eliminar"). Row click navigates to detail.
- Pagination controls at the bottom (page size 25, navigation arrows + page-of-page).
- Empty state when API returns 0 items: centred illustration placeholder + "Aún no hay componentes" + "Crea el primero" button → `/components/new`.

### Frontend — detail page (Figma 47:16048)

- Header card pixel-faithful to the design: MPN + name big, then a grid of metadata fields (SKU, Familia, Ubicación, Supplier, Precio (100u), Stock, Tier, NATO Score, País de origen).
- Tabs strip: **Detalle** (active by default) / **Historial** / **Scoring OTAN**. Switching tabs uses route navigation (`/components/:id`, `/components/:id/purchases`, `/components/:id/nato`) so the tabs are deep-linkable.
- Within the Detalle tab: description text + a stock-level chart (`recharts` `<LineChart>`) using the purchase quantities as series; X axis = purchase date, Y axis = quantity.
- Alerts panel right-side: shows the rule-based warnings (e.g., "Stock interno bajo", "Supplier sin actividad reciente") — computed client-side from the loaded data for now; future US can move the rule engine server-side.
- Header actions: **Editar** button → `/components/:id/edit`; **Eliminar** with a confirm dialog (shadcn) → `DELETE` then navigate to `/components`.

### Frontend — purchase history page (Figma 47:20273)

- Same component header card as detail.
- Cost-trend `<LineChart>`: X axis = `purchased_at`, Y axis = `unit_cost`. Tooltips on hover show the full row (date, quantity, supplier, unit cost, total cost).
- Table below: Fecha, Cantidad, Proveedor, Costo unitario (EUR), Costo total (EUR). Sorted by `purchased_at DESC`. Pagination at the bottom (page size 25).

### Frontend — NATO scoring page (Figma 47:21897)

- Same component header card.
- Tier breakdown panel with the `<TierBadge>` large + the explanatory description from the rubric ("Tier 1 → Chips y microcontroladores → Riesgo Muy alto", etc.).
- NATO classification block: `<NatoScoreBadge>` + the country of origin + the rubric ("100% OTAN → Todos los componentes verificados", etc.).
- Legend section at the bottom listing every tier and every NATO classification with their badge + meaning. Copy verbatim from `docs/overview.md` (already documented).

### Frontend — edit form (Figma 47:17405)

- One form shared by create + edit; differs only in initial values, page title, submit button label and post-submit navigation.
- react-hook-form + zod resolver. Fields:
  - MPN (text, **read-only in edit mode**, required in create mode).
  - SKU (text).
  - Nombre (text, required).
  - Familia (text, required).
  - Descripción (textarea).
  - Datasheet URL (url).
  - Ubicación (text).
  - Supplier (text).
  - Precio (100u) (number, ≥ 0).
  - Stock (number, ≥ 0, integer).
  - Tier (select: A+ / A / B / C / D).
  - NATO Score (select with the 6 enum values, rendered with `<NatoScoreBadge>` inside the option).
  - País de origen (CountryOfOriginSelect: dropdown with EU + NATO countries + "Otro…" → free-text fallback).
- Submit button: **Guardar** (primary magenta). Cancel button: **Cancelar** (ghost).
- 409 from server (duplicate MPN on create) is surfaced under the MPN field via `setError("mpn", { message })`.
- 422 from server is mapped field-by-field via the RFC 7807 `errors[]` payload.

### Frontend — design tokens + shared primitives

- `<TierBadge>` and `<NatoScoreBadge>` are stateless presentational components. Tier colour mapping: A+ = green (`bg-emerald-500/15 text-emerald-700`), A = green-soft, B = amber, C = orange, D = red. NATO colour mapping: `100_otan` = green, `otan` = emerald-soft, `allied_otan` = blue, `neutral` = amber, `high_risk` = orange, `no_otan` = red. Concrete Tailwind classes are aligned to the existing palette (`bg-emerald-500/15`, etc.) — design.md documents the exact mapping.
- `<NatoScoreHelpPopover>` reuses the Popover primitive added in `dashboard-shell-redesign` (no new shadcn primitive needed for the popover itself). Body copy comes from the Figma rubric.
- `recharts` is added to `frontend/package.json` runtime deps. We import only the components we use to keep the bundle delta predictable.
- The shared shadcn `<Select>` and `<Table>` primitives are scaffolded under `frontend/src/components/ui/` if not already present (the current change is the first to introduce them).
- Currency formatting: a small helper `formatEuros(value: number | null): string` in `frontend/src/lib/format/currency.ts` so we have one place that owns Spanish-locale euro formatting (`"€ 8,45"` with non-breaking space).

### Tests — backend

- Unit tests for `ComponentsService` happy path + every error edge (mocked repos).
- Integration tests against the running postgres (existing fixture pattern):
  - `GET /api/v1/components` — happy, empty, filter combinations, pagination boundaries, 401 without token.
  - `POST` — 201 + 409 (duplicate MPN) + 422 (invalid tier / nato_score / negative stock).
  - `GET /:id` — 200 + 404.
  - `PATCH /:id` — partial update + ignore immutable fields + 404.
  - `DELETE /:id` — 204 + idempotent on missing.
  - `GET /:id/purchases` — ordered DESC + pagination + empty case + 404 if component missing.
  - `POST /:id/sync` — 202 + log line present.
  - Case-insensitive search across mpn / sku / name / family.
- `seed_components` test: happy + refusal + `--reset` flow (against the docker postgres, mirroring the `seed_admin` test).
- Coverage gate stays at 80 % global.

### Tests — frontend

- zod schema unit tests for valid + invalid create / edit payloads.
- Component tests:
  - `<TierBadge>` and `<NatoScoreBadge>` render the correct copy + colour per value.
  - `<ComponentsListPage>`: renders rows from MSW-mocked API; empty state when 0 items; search input updates query; filter dropdowns update query.
  - `<ComponentEditPage>` (create mode): submit happy → navigates to detail; submit returning 409 → inline error under MPN.
  - `<ComponentEditPage>` (edit mode): MPN field is rendered as read-only; pre-filled with current values.
  - `<ComponentDetailPage>`: renders tabs + active state for the current route; "Eliminar" triggers confirm dialog.
  - `<NatoScoreHelpPopover>`: opens on bell-icon click; closes on Escape.
- Hook tests: `useComponents` builds the URL with the right filters / pagination from its arg.
- Vitest coverage stays ≥ 80 %.

### Tests — Playwright @smoke

- `frontend/e2e/components.spec.ts` (against the live docker stack, seeded):
  - Authenticated user navigates `/components`; sees ≥ 10 rows; clicks the row for `ACS712`; lands on `/components/<id>`; sees the detail card; clicks the "Historial" tab; lands on `/components/<id>/purchases`; sees the chart and the table rows.
  - On detail, clicks "Editar"; lands on `/components/<id>/edit`; form pre-filled; changes the name; saves; back on detail with the new name visible.
  - On `/components`, clicks "+ Nuevo componente"; lands on `/components/new`; fills the required fields; saves; lands on the new detail page.

### Documentation

- `ai-specs/specs/data-model.md`: `Component` and `ComponentPurchase` move from "not yet implemented" to the new column-level shape (same level of detail as `User`).
- `ai-specs/specs/api-spec.yml`: add `Component`, `ComponentCreate`, `ComponentUpdate`, `ComponentPurchase`, `PaginatedComponents`, `PaginatedComponentPurchases`, `ComponentSyncResponse` schemas + the seven endpoints under the `components` tag.
- `ai-specs/specs/development_guide.md`: add `docker compose run --rm backend python -m app.scripts.seed_components` to the "First run" section, immediately after the `seed_admin` step.

## Design References

Figma File:
https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm

Referenced Nodes:
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-15264
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-16048
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-20273
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-21897
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-17405

## Constraints / Notes
- Pixel-perfect at `lg` (1024+); below `lg` the tables degrade to horizontal scroll, charts shrink. No mobile-first work beyond that.
- `mpn` is the natural business key, surfaced read-only in the edit form. A future "merge / rename components" US can relax that.
- The "Sincronizar" button is a placeholder action returning 202 today — wired up by US 5 / 6 / 7 (Holded products + KiCAT updates). Documented in design.md.
- Alerts panel rules (low stock, stale supplier) are computed client-side for now. Rule engine moves server-side when we have the price-history daily ingest (US 8).
- Charts: `recharts` — React-native, no extra runtime, tree-shaken to the two components we use (`LineChart`, `Tooltip`, `Legend`, `XAxis`, `YAxis`).
- Country code: ISO 3166-1 alpha-2 at the DB layer; FE shows an EU + NATO select with a free-text fallback. Full country picker is out of scope.
- New runtime deps: `recharts` on the FE only. No new BE deps (`numeric` is a SQLAlchemy core type).
- This change introduces the first business entity on top of the auth + chrome chassis. The patterns established here (`features/<entity>/api/...`, paginated hook, zod schemas mirroring Pydantic, two-mode form pattern) will be reused by Módulo + Proyecto USs.

<!-- END_ENRICHED_USER_STORY -->
