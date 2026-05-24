# component-management-ui Specification

## Purpose
TBD - created by archiving change component-management. Update Purpose after archive.
## Requirements
### Requirement: The components catalogue renders a searchable, filterable, paginated list

The frontend SHALL render a page at `/components` (pixel-faithful to Figma `47:15264`) that lists components from `GET /api/v1/components`. The page contains: a search input (debounced 300 ms, placeholder `"Buscar por MPN, SKU, nombre o familia…"` — updates the URL's `?q=` so the URL is shareable), four filter dropdowns (Familia, Supplier, Tier, NATO Score), a `"+ Nuevo componente"` primary magenta button (top-right) navigating to `/components/new`, and a "Sincronizar" secondary button on the right side. The table has columns **MPN** (mono font), **Nombre** (medium weight), **Familia**, **Ubicación**, **Supplier**, **Precio (100u)** (right-aligned, EUR-formatted via the shared helper), **Stock** (right-aligned), **Tier** (`<TierBadge>` column), **NATO** (`<NatoScoreBadge>` column), **Acciones** (kebab menu → Ver / Editar / Eliminar). Pagination controls live at the bottom (page-of-page + arrows). Clicking a row navigates to `/components/{id}`.

#### Scenario: List renders the seeded rows

- **WHEN** the dev stack is seeded and the authenticated user opens `/components`
- **THEN** the page shows the table with ≥ 10 rows
- **AND** each row's Tier and NATO columns render their respective badge components

#### Scenario: Search drives the URL

- **WHEN** the user types `ACS` into the search input
- **THEN** after the debounce, the URL becomes `/components?q=ACS`
- **AND** the table re-fetches with `?q=ACS` and shows only matching rows

#### Scenario: Empty state renders a CTA to create one

- **WHEN** the API returns `total: 0`
- **THEN** the table area is replaced by a centred empty state with the text `"Aún no hay componentes"` and a "Crea el primero" button linking to `/components/new`

#### Scenario: Row click navigates to detail

- **WHEN** the user clicks any row outside the kebab-menu cell
- **THEN** the browser navigates to `/components/{rowId}`

### Requirement: The component detail page renders header + tabs + stock chart + alerts

The frontend SHALL render a page at `/components/{id}` (pixel-faithful to Figma `47:16048`) that shows: a header card with MPN (big), name (medium), and a metadata grid (SKU, Familia, Ubicación, Supplier, Precio 100u, Stock, Tier badge, NATO badge, País de origen); a tabs strip with three tabs (**Detalle** active, **Historial**, **Scoring OTAN**); the body of the active tab. The tabs MUST be deep-linkable — they navigate between `/components/{id}`, `/components/{id}/purchases`, `/components/{id}/nato`. The Detalle tab body contains the description text, a `recharts` `LineChart` of historic stock levels (derived from the component's purchase history quantities), and an Alerts panel on the right (computed client-side from the loaded data: low-stock, stale-supplier). Two header actions: **Editar** → `/components/{id}/edit`; **Eliminar** → confirm dialog (shadcn) → `DELETE` → navigate back to `/components`.

#### Scenario: Tabs deep-link

- **WHEN** the user is on `/components/{id}` and clicks the "Historial" tab
- **THEN** the browser navigates to `/components/{id}/purchases`
- **AND** the URL is bookmark-friendly (a hard reload at that URL lands on the same tab active)

#### Scenario: Header renders the live identity

- **WHEN** the page loads a component whose `mpn = "ACS712"`, `name = "Sensor corriente Hall ±20A"`
- **THEN** the header shows `ACS712` and `Sensor corriente Hall ±20A` per the Figma typography

#### Scenario: Eliminar opens a confirmation and deletes on confirm

- **WHEN** the user clicks "Eliminar" and confirms in the dialog
- **THEN** a `DELETE /api/v1/components/{id}` is issued
- **AND** on 204, the browser navigates to `/components`

### Requirement: The NATO scoring page renders the tier + classification with a legend

The frontend SHALL render a page at `/components/{id}/nato` (pixel-faithful to Figma `47:21897`) showing: the shared component header card, a Tier breakdown panel (`<TierBadge>` large + the rubric text from `docs/overview.md`), a NATO classification block (`<NatoScoreBadge>` + country of origin + the rubric text), and a Legend section at the bottom listing every Tier (A+ → D) with its meaning and every NATO score with its meaning. All copy comes verbatim from the Figma and from the Overview document. A `<NatoScoreHelpPopover>` is anchored to the question-mark icon next to the "Scoring OTAN" heading.

#### Scenario: Legend lists every Tier and every NATO score

- **WHEN** the user opens `/components/{id}/nato`
- **THEN** the Legend section renders one row per Tier (`A+`, `A`, `B`, `C`, `D`) with its rubric description
- **AND** one row per NATO score (`100_otan`, `otan`, `allied_otan`, `neutral`, `high_risk`, `no_otan`) with its rubric description

#### Scenario: Help popover opens on click

- **WHEN** the user clicks the question-mark icon next to "Scoring OTAN"
- **THEN** the popover opens with the rubric text
- **AND** Escape closes it

### Requirement: The component edit form covers create + edit modes

The frontend SHALL render a page at `/components/new` (create mode) and `/components/{id}/edit` (edit mode) that share a single `<ComponentEditPage>` (pixel-faithful to Figma `47:17405`). Form fields: MPN (text, **read-only in edit mode**, required in create mode), SKU (text), Nombre (text, required), Familia (text, required), Descripción (textarea), Datasheet URL (url), Ubicación (text), Supplier (text), Precio (100u) (number, ≥ 0), Stock (number, integer ≥ 0), Tier (select: A+ / A / B / C / D), NATO Score (select with the six enum values, each option renders a `<NatoScoreBadge>` next to its Spanish label), País de origen (`<CountryOfOriginSelect>` — dropdown of EU + NATO countries with a "Otro…" item that reveals a free-text input). Submit button text: "Crear componente" in create mode, "Guardar cambios" in edit mode. Cancel button (ghost) navigates back. Validation: react-hook-form + zod. Server-side 409 (duplicate MPN on create) is mapped to an inline error under the MPN field. Server-side 422 maps field-by-field via the RFC 7807 `errors[]` payload.

#### Scenario: MPN is read-only in edit mode

- **WHEN** the user opens `/components/{id}/edit`
- **THEN** the MPN input is rendered with the `readOnly` attribute (or as a `<p>` with `aria-readonly`) so the value is visible but not editable
- **AND** the form does not include MPN in the PATCH payload it submits

#### Scenario: Create happy path navigates to the new detail page

- **WHEN** the user fills the required fields in `/components/new` and clicks "Crear componente"
- **AND** the server returns 201 with a new component `id`
- **THEN** the browser navigates to `/components/{newId}`
- **AND** a toast / inline confirmation reports the creation

#### Scenario: Duplicate MPN on create surfaces inline

- **WHEN** the user submits a create with a duplicate `mpn` and the server returns 409 `MPN_ALREADY_REGISTERED`
- **THEN** an inline error message under the MPN field reads "Ya existe un componente con ese MPN"
- **AND** no navigation happens

#### Scenario: Edit happy path returns to the detail page

- **WHEN** the user changes a field in `/components/{id}/edit` and clicks "Guardar cambios"
- **AND** the server returns 200
- **THEN** the browser navigates to `/components/{id}`
- **AND** the updated value is visible on the detail header

### Requirement: TierBadge and NatoScoreBadge expose the canonical visual mapping

The frontend SHALL provide two reusable presentational components, `<TierBadge value="A+|A|B|C|D" />` and `<NatoScoreBadge value="100_otan|otan|allied_otan|neutral|high_risk|no_otan" />`. Each renders the literal Spanish label from the Figma and a colour mapping defined in the design document. Both components are pure — no data fetching, no state. They MUST be the only place where tier / score labels and colours are computed in the UI.

#### Scenario: TierBadge renders the right label per value

- **WHEN** a `<TierBadge value="A+" />` is rendered
- **THEN** the visible text is `A+`
- **WHEN** a `<TierBadge value="D" />` is rendered
- **THEN** the visible text is `D`

#### Scenario: NatoScoreBadge renders the Spanish copy from the Figma

- **WHEN** a `<NatoScoreBadge value="100_otan" />` is rendered
- **THEN** the visible text is `100% OTAN`
- **WHEN** a `<NatoScoreBadge value="allied_otan" />` is rendered
- **THEN** the visible text is `Aliados OTAN`
- **WHEN** a `<NatoScoreBadge value="high_risk" />` is rendered
- **THEN** the visible text is `Alto riesgo`
- **WHEN** a `<NatoScoreBadge value="no_otan" />` is rendered
- **THEN** the visible text is `No OTAN`

### Requirement: The components feature exposes typed API + TanStack Query hooks

The frontend SHALL provide a typed API module `src/features/components/api/components-api.ts` mirroring the conventions in `auth-api.ts`. The exposed methods are `list(filters, page, pageSize)`, `get(id)`, `create(payload)`, `update(id, payload)`, `delete(id)`, `listPurchases(id, page, pageSize)`, `sync(id)`. A set of TanStack Query hooks (`useComponents`, `useComponent`, `useComponentPurchases`, plus mutations for create / update / delete / sync) MUST invalidate the right query keys on success (`["components", "list"]` after create / update / delete / sync; `["components", "detail", id]` after update; `["components", "purchases", id]` after sync).

#### Scenario: Updating a component invalidates the list and the detail query

- **WHEN** `useUpdateComponent` mutation completes successfully for `id = X`
- **THEN** the QueryClient invalidates `["components", "list"]` AND `["components", "detail", X]`
- **AND** does not invalidate other component detail queries

#### Scenario: Sync invalidates the purchase history of that component

- **WHEN** `useSyncComponent` mutation completes successfully for `id = X`
- **THEN** the QueryClient invalidates `["components", "purchases", X]` so the next render fetches fresh data
