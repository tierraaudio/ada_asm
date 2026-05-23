<!--
design-linked: true | scope: BE + FE
-->

## Design References

Figma file: `pMUgDI7rbRRzVWLCJhoVnY` (`ada_asm`).

Referenced Nodes:
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-15264 — Components list
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-16048 — Component detail
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-20273 — Component purchase history
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-21897 — NATO scoring detail
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-17405 — Component edit form

Pixel-perfect at the `lg` (1024+) breakpoint.

Canonical enriched user-story snapshot: `drafts/enriched/component-management-20260523-1722.md`.

## Why

`Componente` is the leaf of the asset tree (`Proyecto → Módulo → Componente`) and the catalogue our team operates against day to day. After `dashboard-shell-redesign` we have a sidebar that already links to `/components`, but the destination is a placeholder. There is no `components` table, no API endpoints, and no UI beyond the empty shell.

This is also the right moment to ship the catalogue: the chrome is locked, the auth layer is in place, the design system tokens are in place, and we have five locked Figma frames covering the full lifecycle (list, detail, purchase history, NATO scoring breakdown, create / edit). Closing this US gives the team a first business surface to work against and unblocks the future USs that depend on having components in the DB (Holded product sync, KiCAT sync, daily price ingest).

## What Changes

### Backend
- **New `Component` entity** persisted in `components` table: `id (uuid)`, `mpn (varchar 100, unique)`, `sku`, `name`, `family`, `description`, `datasheet_url`, `location`, `supplier`, `price_per_100 (numeric)`, `stock (int, ≥ 0)`, `tier ('A+'|'A'|'B'|'C'|'D')`, `nato_score ('100_otan'|'otan'|'allied_otan'|'neutral'|'high_risk'|'no_otan')`, `country_of_origin (ISO 3166-1 alpha-2)`, `created_at`, `updated_at`.
- **New `ComponentPurchase` entity** persisted in `component_purchases`: `id`, `component_id` (FK CASCADE), `purchased_at (date)`, `quantity (int > 0)`, `supplier`, `unit_cost`, `total_cost`, `currency ('EUR' default)`, `created_at`, `updated_at`. Indexed by `(component_id, purchased_at DESC)`.
- **Alembic migration** introducing both tables, reversible end-to-end.
- **Endpoints under `/api/v1/components`** (all protected with `require_user`):
  - `GET /` — paginated, accepts `q`, `family`, `supplier`, `tier`, `nato_score`, `page`, `page_size` (default 25, max 100).
  - `POST /` — create. 409 `MPN_ALREADY_REGISTERED` on dup.
  - `GET /{id}` — single component. 404 `COMPONENT_NOT_FOUND`.
  - `PATCH /{id}` — partial update; ignores `mpn`, `id`, `created_at`, `updated_at`.
  - `DELETE /{id}` — 204; idempotent on missing.
  - `GET /{id}/purchases` — paginated, ordered by `purchased_at DESC`.
  - `POST /{id}/sync` — placeholder 202 with `{ "status": "queued" }`. Real KiCAT / Holded sync lands in their dedicated USs (5, 6, 7 from the backlog).
- **New domain exceptions** `ComponentNotFoundError` (404 / `COMPONENT_NOT_FOUND`) and `ComponentMpnAlreadyRegisteredError` (409 / `MPN_ALREADY_REGISTERED`) in `app/core/exceptions.py`.
- **All errors RFC 7807** with stable `code`.
- **Seed script** `python -m app.scripts.seed_components` inserts ~10 sample components (matching the Figma copy) plus 3-6 purchase rows per component so charts have real data. Idempotent — refuses to re-seed unless `--reset` is passed.

### Frontend
- **Replace placeholder routes** introduced by `dashboard-shell-redesign`:
  - `/components` → `ComponentsListPage` (Figma `47:15264`).
  - `/components/new` → `ComponentEditPage` create mode.
  - `/components/:id` → `ComponentDetailPage` (Figma `47:16048`).
  - `/components/:id/purchases` → `ComponentPurchaseHistoryPage` (Figma `47:20273`).
  - `/components/:id/nato` → `ComponentNatoScoringPage` (Figma `47:21897`).
  - `/components/:id/edit` → `ComponentEditPage` edit mode (Figma `47:17405`).
- **Feature tree** under `frontend/src/features/components/`: `api/`, `hooks/`, `components/`, `pages/`, `schemas.ts`, `types.ts`.
- **Two reusable shadcn-style badges**: `<TierBadge>` (A+ / A / B / C / D) and `<NatoScoreBadge>` (six values), each with the literal Spanish copy from the Figma and the colour mapping documented in design.md.
- **Help popover** `<NatoScoreHelpPopover>` on the "Scoring OTAN" question-mark icon — explains the rubric. Reuses the Popover primitive shipped in `dashboard-shell-redesign`.
- **Country of origin select** `<CountryOfOriginSelect>` — EU + NATO countries + "Otro…" → free-text fallback.
- **TanStack Query hooks** `useComponents`, `useComponent`, `useComponentPurchases`, plus mutations for create / update / delete / sync. Correct key invalidation after mutations.
- **Typed API module** `src/features/components/api/components-api.ts` mirroring `auth-api.ts` conventions.
- **zod schemas** in `src/features/components/schemas.ts` aligned with the backend Pydantic shape.
- **Charts via `recharts`** — first chart library introduced in the FE. `LineChart` for stock trend (detail page) and cost trend (purchase history page). Tooltips, axes, legend.
- **EUR formatter helper** `src/lib/format/currency.ts` so every "Precio (100u)" display is consistent (`"€ 8,45"`).
- **Spanish in user-visible labels**, English in code / comments / logs (per project rule).

### Documentation
- `ai-specs/specs/data-model.md`: `Component` and `ComponentPurchase` move from "not yet implemented" to the new column-level shape.
- `ai-specs/specs/api-spec.yml` extended with the new `/api/v1/components/*` surface and the related schemas.
- `ai-specs/specs/development_guide.md`: add `docker compose run --rm backend python -m app.scripts.seed_components` to the "First run" section, immediately after `seed_admin`.

### Non-goals
- No real KiCAT / Holded sync. The "Sincronizar" endpoint is a 202 stub; real upstream wiring lives in USs 5, 6 and 7.
- No bulk operations (bulk create, bulk delete, CSV import / export).
- No price-history daily ingest job — that's US 8.
- No alerts rule engine on the server — the alerts panel in the detail page is computed client-side from the loaded data for now.
- No full country picker with flags. The select offers EU + NATO countries plus a free-text fallback.
- No optimistic UI for mutations; we wait for the server round-trip.
- No `/projects` or `/modules` pages — sibling USs.

## Capabilities

### New Capabilities
- `component-catalog`: the `Component` entity, its CRUD surface (`/components/*`), the paginated list with filters + search, and the placeholder sync endpoint. Includes the seed-components script.
- `component-purchase-history`: the `ComponentPurchase` entity and the `GET /components/{id}/purchases` endpoint, plus the purchase-history rendering (table + cost trend chart) on the frontend.
- `component-management-ui`: the five pixel-perfect pages on the frontend (list, detail, purchase history, NATO scoring, edit) plus the shared `<TierBadge>` / `<NatoScoreBadge>` / `<NatoScoreHelpPopover>` / `<CountryOfOriginSelect>` primitives.

### Modified Capabilities
_(None — this US only introduces new capabilities. The placeholder routes from `dashboard-shell` are populated by `component-management-ui`, but `dashboard-shell`'s requirement that those routes exist under the protected layout is still true; no spec there needs to change.)_

## Impact

- **Code (backend)**: new files under `app/domain/entities/`, `app/domain/repositories/`, `app/infrastructure/db/models/`, `app/infrastructure/repositories/`, `app/application/services/`, `app/api/v1/schemas/`, `app/api/v1/routers/`, `app/scripts/`. New entries in `app/core/exceptions.py`, `app/api/errors.py` if needed (unlikely — the existing mapper handles `DomainError` subclasses generically). Migration under `backend/migrations/versions/`.
- **Code (frontend)**: new feature tree under `src/features/components/`. Updates to `src/App.tsx` to mount the real pages. New shadcn primitives `<Select>` and `<Table>` under `src/components/ui/` if not already present (this is the first US that needs them).
- **Tests**: new pytest files under `backend/tests/integration/test_components_*.py` and `backend/tests/unit/test_components_service.py`; new Vitest files under `frontend/src/features/components/**/*.test.tsx` and one new Playwright spec `frontend/e2e/components.spec.ts`.
- **Dependencies**:
  - Backend: none new (`numeric` is core SQLAlchemy).
  - Frontend: adds `recharts` (~120 KB gzipped; tree-shaken to ~30 KB for the chart pieces we use).
- **Configuration / env**: none.
- **Operations**: a new one-time seed step on a fresh DB to populate sample components.
- **CI**: no workflow change — existing `backend.yml` and `frontend.yml` cover the new tests via the same gates.
- **Risk**:
  - First entity on top of the auth + chrome chassis — the patterns established here will be reused by Módulo + Proyecto USs. Worth getting right.
  - The `seed_components` reset path uses `TRUNCATE` on `component_purchases` then `components`; safe today because nothing else references components, but worth flagging in design.md so we remember to rethink it when foreign keys land from `Módulo`.
  - First chart library in the project — bundle budget needs a sanity-check after build.
