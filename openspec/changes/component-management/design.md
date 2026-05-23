## Context

After `login-en-asm` (auth) and `dashboard-shell-redesign` (chrome) the SPA is bootable and authenticated, the sidebar links to `/components`, and the route exists but renders the placeholder shell. The backend has no `components` table and no endpoints for the entity yet. The Figma file has five locked frames that together define the full component lifecycle. This US lands the first business entity on top of the auth + chrome chassis.

Three notes that frame everything below:

- **This change is the template for the next entity USs** (Módulo, Proyecto). The patterns established here — `features/<entity>/api`, paginated TanStack hooks, zod schemas mirroring Pydantic shapes, a single edit page in two modes, presentational badge components — will be reused. Choices in this design that look heavier than needed for a single entity are deliberate to avoid re-deciding later.
- **The "Sincronizar" button is a placeholder.** The real Holded / KiCAT sync is owned by USs 5, 6 and 7. The endpoint returns 202 + a log line tagged `components.sync.placeholder` so we can observe usage without pretending the upstream is wired.
- **Charts arrive with this change.** `recharts` is the first chart library introduced in the FE. We bias the import to only the pieces we use to keep the bundle delta predictable.

## Goals / Non-Goals

**Goals:**

- Pixel-faithful at `lg` (1024+) for all five Figma frames (`47:15264`, `47:16048`, `47:20273`, `47:21897`, `47:17405`).
- Backend: `components` + `component_purchases` tables, full CRUD surface for components, paginated purchase history, placeholder sync, seed script.
- Frontend: five real pages replacing the placeholders in `dashboard-shell-redesign`; reusable `<TierBadge>` / `<NatoScoreBadge>` / `<NatoScoreHelpPopover>` / `<CountryOfOriginSelect>`; typed API + TanStack Query hooks + zod schemas; `recharts` for stock + cost trend charts.
- Tests at the same coverage gates as the existing modules: 80 % backend (pytest), 80 % frontend (Vitest), one Playwright `@smoke` covering the end-to-end happy paths.
- Documentation in lockstep: `data-model.md`, `api-spec.yml`, `development_guide.md`.

**Non-Goals:**

- No real upstream sync (KiCAT, Holded). The endpoint is a 202 stub.
- No bulk operations (bulk create, bulk delete, CSV import / export).
- No price-history daily ingest. That's US 8.
- No server-side rule engine for alerts. The alerts panel on the detail page is computed client-side from the loaded data; the engine moves server-side when we have a daily-ingest pipeline.
- No `/projects` or `/modules` pages. Those are sibling USs.
- No full country picker with flags. EU + NATO select with a free-text fallback is enough.
- No optimistic UI on mutations.

## Decisions

### D1. `mpn` is the business key; immutable in this US

- Unique at the DB layer (case-insensitive enforced via a `lower(mpn)` unique index).
- Required at create time. Ignored on PATCH (silently dropped, not 422) — clients sending a stale full body are not rejected, they just don't accidentally rename the key.
- Read-only in the edit form UI.

A future US ("merge / rename components") will introduce a dedicated endpoint with the right safeguards (preserving purchase history, emitting an audit event, etc.).

### D2. Tier and NATO score are stored as constrained strings, not full enum types

We use `varchar(2)` + a `CHECK` constraint for `tier` and `varchar(20)` + a `CHECK` constraint for `nato_score` rather than PostgreSQL `ENUM` types.

- **Why**: enum types in Postgres are painful to evolve (adding / removing / renaming values requires an explicit migration step that locks the type). Adding a future tier or NATO category is more likely than not — a small CHECK constraint is cheaper to migrate.
- **Trade-off**: slightly weaker type guarantee at the column level. We compensate with Pydantic `Literal` types in the API layer and zod enums in the frontend.

### D3. `price_per_100` and money columns are `numeric`, never `float`

- `price_per_100 numeric(12, 4)`, `unit_cost numeric(12, 4)`, `total_cost numeric(14, 4)`.
- SQLAlchemy maps these to `Decimal` in Python; Pydantic schemas use `Decimal` too. The API serialises them as strings (`"8.45"`) per JSON-friendly Decimal convention; the frontend converts to `number` only at format time via the `formatEuros` helper.
- **Why**: floating point + euros = quiet rounding bugs. `numeric` is the boring correct choice.

### D4. Search is `OR` across four columns, case-insensitive via `lower()` indexes

The query is roughly:

```sql
WHERE lower(mpn) LIKE '%' || lower(:q) || '%'
   OR lower(sku) LIKE '%' || lower(:q) || '%'
   OR lower(name) LIKE '%' || lower(:q) || '%'
   OR lower(family) LIKE '%' || lower(:q) || '%'
```

Per-column functional indexes on `lower(mpn)`, `lower(sku)`, `lower(name)`, `lower(family)` exist so the planner can use them. A future US can swap to `pg_trgm` / `tsvector` if we need fuzzy matching or ranking — the API surface (`?q=`) stays the same.

### D5. Pagination envelope is `{ items, total, page, page_size }`

Same shape as the existing auth / placeholder responses elsewhere in the spec. The frontend has a `Paginated<T>` type matching it. We do not use cursor pagination today because there's no infinite-scroll surface; offset pagination is enough for a single-table catalogue at our scale.

### D6. PATCH ignores immutable fields silently; doesn't 422 on them

`PATCH /api/v1/components/{id}` accepts `id`, `mpn`, `created_at`, `updated_at` in the payload and silently drops them. The alternative (422 with `code: "IMMUTABLE_FIELD"`) is "more correct" but pisses off clients that resubmit the full body. We pick lenient.

### D7. Sync is a placeholder 202 endpoint

`POST /api/v1/components/{id}/sync` is wired so future USs can flip it real without changing the URL. It returns 202 with `{ "status": "queued" }` immediately, logs a structured line tagged `components.sync.placeholder` with the component id, and does nothing else.

- USs 5, 6, 7 will likely replace the body with a Celery `delay()` call against a `components.sync` task; the response shape stays 202 with the same JSON.
- The endpoint does NOT 404 on a missing component → 404 (so the frontend's `useSyncComponent` mutation surfaces a real error).

### D8. Two new shadcn primitives: `<Table>` and `<Select>`

This is the first US that needs them. Scaffolded manually under `src/components/ui/` following the existing pattern (we did the same for `<DropdownMenu>` and `<Popover>` in previous changes). No `dlx`.

### D9. Charts: `recharts` + tree-shaken import

```ts
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
```

- Tree-shaken delta: ~30 KB gzipped.
- Vite warns when the main chunk exceeds 350 KB gzipped; with `recharts` we will hover around the mark for the first time. If we exceed it we lazy-load the chart pages via `React.lazy()` — but that's a follow-up if needed, not part of this US.

### D10. Component edit form is one component, two modes

`<ComponentEditPage mode="create" | "edit" />`. Selecting create:

- `mpn` is editable + required, validated client-side via zod.
- Page title is "Crear componente". Submit button: "Crear componente".
- Success → navigate to `/components/{newId}`.

Selecting edit:

- `mpn` rendered with `readOnly` attribute, value pre-filled, not included in the PATCH payload.
- Page title is "Editar componente". Submit button: "Guardar cambios".
- Success → navigate to `/components/{id}`.

Keeping the two modes in one component avoids drift in the form contract.

### D11. Reusable badges own all tier/score label + colour logic

`<TierBadge>` and `<NatoScoreBadge>` are the only place where tier / NATO labels and colours are computed. Anywhere else in the UI that needs a Tier or NATO visual MUST import these components — no string-to-colour map duplicated. The "rubric" copy (the long explanatory paragraph behind each value) lives in `src/features/components/rubrics.ts` and is consumed by the legend on `/components/{id}/nato` and by the `<NatoScoreHelpPopover>`.

Tier colour mapping (light theme):

| Tier | Tailwind classes               |
|------|--------------------------------|
| A+   | `bg-emerald-500/15 text-emerald-700` |
| A    | `bg-emerald-500/10 text-emerald-700` |
| B    | `bg-amber-500/15 text-amber-700`     |
| C    | `bg-orange-500/15 text-orange-700`   |
| D    | `bg-red-500/15 text-red-700`         |

NATO colour mapping:

| Score          | Tailwind classes                       |
|----------------|----------------------------------------|
| `100_otan`     | `bg-emerald-500/15 text-emerald-700`   |
| `otan`         | `bg-emerald-500/10 text-emerald-700`   |
| `allied_otan`  | `bg-sky-500/15 text-sky-700`           |
| `neutral`      | `bg-amber-500/15 text-amber-700`       |
| `high_risk`    | `bg-orange-500/15 text-orange-700`     |
| `no_otan`      | `bg-red-500/15 text-red-700`           |

These are intentionally derived from Tailwind's stock palette + 15 % alpha tints. The Figma uses softer pastel backgrounds; the alpha tints land at the same perceptual weight without us having to mint custom CSS variables for every state. If the design review insists on the exact pastel from Figma we can promote them to CSS variables later — one change, zero ripple.

### D12. EUR formatter helper

`src/lib/format/currency.ts` exports `formatEuros(value: number | string | null | undefined): string`. Uses `Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", minimumFractionDigits: 2, maximumFractionDigits: 2 })`. Returns an empty string for `null` / `undefined`. Every UI surface that displays money MUST go through this helper.

### D13. Alerts panel is client-side for now

The detail page renders an "Alertas" panel with rule-based warnings:

- "Stock interno bajo" when `stock < 10`.
- "Supplier sin actividad reciente" when the most recent purchase is > 180 days old.
- "Sin compras registradas" when there are no purchase rows.

These rules live in `src/features/components/alerts.ts` and operate on the already-loaded data. When US 8 lands the daily ingest, the rule engine will move server-side and the panel will consume a `/api/v1/components/{id}/alerts` endpoint.

### D14. Country select is a curated EU + NATO list with free-text fallback

The `<CountryOfOriginSelect>` shows the union of EU and NATO countries (35-ish entries) plus "Otro…" which reveals a free-text 2-char input validated against ISO 3166-1 alpha-2 by zod. We do NOT ship a full country picker (overkill for an internal tool today). The backend accepts any valid 2-char code so future expansion is data-only.

### D15. No MODIFIED capability deltas

The placeholder routes from `dashboard-shell` (`/components`, `/components/new`, `/components/:id`, `/components/:id/purchases`, `/components/:id/nato`, `/components/:id/edit`) remain registered exactly as declared in that capability — they exist under the protected layout. This US replaces their elements but does NOT change the requirement that those routes exist. So we do not write a delta for `dashboard-shell`.

## Risks / Trade-offs

- **Risk**: `numeric` ↔ Pydantic Decimal serialisation surprises (JSON encodes Decimal as a string by default with FastAPI). → **Mitigation**: configure the response schemas with `model_config = ConfigDict(ser_json_inf_nan="strings")` if needed; for `Decimal` specifically Pydantic v2's default is to serialise as a JSON number when `pydantic.json_encoders` is configured or as a string when not. We pick **string** — `"8.4500"` — and the frontend parses with `Number()` before formatting. Documented in the API spec.
- **Risk**: First chart library lands. Bundle budget tight. → **Mitigation**: tree-shake the imports, monitor `dist/assets/index*.js` after build. If we cross the 350 KB gzip warning we lazy-load the chart-bearing pages.
- **Risk**: `--reset` on `seed_components` truncates `component_purchases`. Safe today (nothing else FKs into `components`). When `Módulo` lands and FKs into `Componente`, the `--reset` script must be rewritten. → **Mitigation**: leave a `# TODO when Módulo lands: extend reset to truncate module-component links first` comment in the seed script.
- **Risk**: The "Sincronizar" placeholder might confuse users in dev when nothing happens. → **Mitigation**: show a toast "Sincronización encolada (placeholder — se conectará con KiCAT / Holded en una US futura)" on the FE so the action is observable but its placeholder nature is honest. Code comment in the route handler points to the future US.
- **Trade-off**: We deliberately go with one fat `<ComponentEditPage>` component over two thin sibling pages. If the create and edit flows diverge significantly later we'll split them.
- **Trade-off**: Tier and NATO are constrained `varchar` + `CHECK`, not Postgres `ENUM`. Slightly weaker type guarantee at the column; cheaper to evolve.

## Migration Plan

After merge:

1. `git pull`.
2. `docker compose up -d --build` to bake the new backend image (Alembic upgrade runs in the `migrate` service automatically).
3. Once the backend is healthy, seed the components: `docker compose run --rm backend python -m app.scripts.seed_components`.
4. Hard-refresh `http://localhost:15173/components`.

Rollback: `git revert` the merge commit. The migration's `downgrade()` drops `component_purchases` then `components`. No data outside this US is affected.

## Open Questions

- **Toast notifications**: we don't yet have a toast / snackbar primitive. The "Sincronización encolada" message above assumes one exists. If not, we ship the sync action without a toast and add toasts in a small dedicated UI-polish US later. Decision: ship without a toast (the magenta loading state on the button is enough); add toasts when the first feature actually depends on them.
- **Numeric serialisation**: confirm with the first integration test whether Pydantic emits `Decimal` as `"8.4500"` (string) or `8.45` (number). The FE handler is written to accept both, but the API spec needs to lock one.
- **Sort order on the list page**: the Figma does not show sort UI. We default to `name ASC`. If the team wants `created_at DESC` (most-recently-added first) that's a one-line change in the service.
- **Bundle size after recharts**: needs a check on the first build. If we exceed 350 KB gzipped we lazy-load the chart-bearing routes via `React.lazy()`.
