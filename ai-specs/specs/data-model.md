# Data Model Documentation

This document is the **forward-looking catalogue** of entities planned for the ADA ASM system. As of this document, no business tables exist in the database — the Alembic baseline migration only enables required PostgreSQL extensions (`pgcrypto`, `ltree`). Each entity below names a future User Story that will introduce its column-level schema and constraints. **Do not treat this document as a schema** — it is intentionally specification-light until each entity lands.

## Model Descriptions

### 1. User

Represents an authenticated person who can access the ADA ASM application.

- **Status**: ✅ Implemented in migration `20260513_1200_login_en_asm__users_refresh_reset.py` (introduced by `login-en-asm`).
- **Table**: `users`.
- **Columns**:
  - `id` UUIDv4, PK, `server_default gen_random_uuid()`
  - `email` `citext`, unique, not null
  - `password_hash` `varchar(255)`, not null — Argon2id digest
  - `full_name` `varchar(200)`, not null, default `''`
  - `global_role` `varchar(16)`, not null, default `'user'` — one of `'admin' | 'user'`
  - `is_active` `boolean`, not null, default `true`
  - `created_at` / `updated_at` `timestamptz`, server-defaulted to `now()`
- **Indexes**: unique on `email` (via the `uq_users_email` constraint).

### 2. Project

The top of the asset hierarchy. Aggregates the Modules and Components that comprise the project's bill of materials. Linked to a Holded customer via the `Customer` entity (see below). Soft-delete is the only delete operation (`status='Archived'`); rows are preserved so historical `stock_events` remain traceable.

- **Status**: ✅ Implemented in `project-management` (migrations `20260526_0900` + `20260526_1500`).
- **Table**: `projects`.
- **Columns**:
  - `id` UUIDv4, PK
  - `code` `varchar(40)`, not null — case-insensitive UNIQUE via `lower(code)`. User-typed, editable, no auto-generation. Surfaced in the UI as "Clave".
  - `name` `varchar(200)`, not null
  - `description` `text`, nullable
  - `status` `varchar(20)`, not null, default `'Presupuestado'` — CHECK in `('Presupuestado', 'Esperando', 'En proceso', 'Completado', 'Archivado')`. Spanish enum matches the FE labels directly (no translation layer).
  - `customer_id` UUIDv4, nullable, FK → `customers.id` ON DELETE SET NULL
  - `icon` `varchar(8)`, nullable — single emoji char/cluster. Free input; FE renders with the project's `color` as a 10%-opacity background.
  - `color` `varchar(7)`, nullable — hex `#rrggbb`. Used as visual accent in the list row icon cell and in the detail header.
  - `tags` `varchar[]` (PostgreSQL `text[]`), not null, default `'{}'` — free-text labels (e.g. `power`, `motor`, `automotive`).
  - `version` `varchar(40)`, nullable — free-text version string (e.g. `v1.0`, `v2.1`).
  - `fecha_inicio` `date`, nullable
  - `fecha_entrega_estimada` `date`, nullable
  - `fecha_entrega_real` `date`, nullable — auto-filled with today's date when a PATCH transitions `status` to `Completado` and no explicit value is provided.
  - `notas` `text`, nullable
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: `uq_projects_code_lower`, `ix_projects_name_lower`, `ix_projects_status`, `ix_projects_customer_id`.

### 2a. ProjectChild

An edge in the project BOM. Mirrors `ModuleChild` exactly: each row points from a `parent_project_id` to **exactly one** of (`child_module_id`, `child_component_id`) — XOR CHECK. The same `(parent, child)` pair is unique (one edge per pair); to repeat a hijo `N` times, raise `quantity`. No cycle detection is needed — projects can't be hijos.

- **Status**: ✅ Implemented in `project-management` (migration `20260526_0900`).
- **Table**: `project_children`.
- **Columns**:
  - `id` UUIDv4, PK
  - `parent_project_id` UUIDv4, FK → `projects.id` ON DELETE CASCADE
  - `child_module_id` UUIDv4, nullable, FK → `modules.id` ON DELETE CASCADE
  - `child_component_id` UUIDv4, nullable, FK → `components.id` ON DELETE CASCADE
  - `quantity` `smallint`, not null, CHECK `> 0`
  - `sort_order` `integer`, not null, default `0`
  - `notes` `text`, nullable
  - `created_at` / `updated_at` `timestamptz`
- **Constraints**:
  - CHECK XOR: `(child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1`
- **Partial UNIQUE indexes**:
  - `uq_project_children_parent_child_module (parent_project_id, child_module_id) WHERE child_module_id IS NOT NULL`
  - `uq_project_children_parent_child_component (parent_project_id, child_component_id) WHERE child_component_id IS NOT NULL`
- **Non-unique indexes**: `(parent_project_id, sort_order)`, `(child_module_id)`, `(child_component_id)`.

### 2c. ProjectInterestLink

Sub-entity of `Project` — the rows that power the "Enlaces de interés" surface. Each row is a `{name, url}` pair the user wants pinned to a project (datasheets, references, internal docs…). CRUD is exposed via dedicated sub-resource endpoints and the FE renders the same component in the detail and edit pages.

- **Status**: ✅ Implemented in `project-management` (migration `20260526_1500`).
- **Table**: `project_interest_links`.
- **Columns**:
  - `id` UUIDv4, PK
  - `project_id` UUIDv4, NOT NULL, FK → `projects.id` ON DELETE CASCADE
  - `name` `varchar(200)`, not null
  - `url` `varchar(2000)`, not null
  - `sort_order` `integer`, not null, default `0`
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: `ix_project_interest_links_project_order (project_id, sort_order)`.

### 2b. Customer

Thin id-link entity that anchors a project to a Holded customer. `holded_id` is the business key (case-insensitive UNIQUE) and `name` is denormalised so the UI doesn't depend on Holded availability. The actual Holded sync ships in a separate, future US.

- **Status**: ✅ Implemented in `project-management` (migration `20260526_0900`).
- **Table**: `customers`.
- **Columns**:
  - `id` UUIDv4, PK
  - `holded_id` `varchar(64)`, not null — case-insensitive UNIQUE via `lower(holded_id)`.
  - `name` `varchar(200)`, not null
  - `holded_url` `varchar(500)`, nullable — explicit override; when null, the FE builds `${HOLDED_BASE_URL}/contact/{holded_id}`.
  - `notas` `text`, nullable
  - `created_at` / `updated_at` `timestamptz`

### 3. Module

A reusable assembly catalogue entry — the intermediate node of the asset tree. Holds metadata (sku/name/version/fabricante/location/tipo_almacenamiento) + `stock` of already-assembled units. Connected to its children (other modules or components) through `module_children` edges, each carrying an explicit `quantity`. Reuse is supported: the same module or component can appear under multiple parents (the tree is a DAG, not a strict tree). Cycles are forbidden and rejected by the service before insert (via `WITH RECURSIVE`).

Aggregates (`precio_total`, `aggregated_nato_score`, `aggregated_tier`, `aggregated_expires_at`, `buildable_stock`) are **computed server-side at read time** from the descendant components — they're never persisted. See the "Aggregations" subsection below.

- **Status**: ✅ Implemented in `module-management` (migration `20260524_1938`).
- **Table**: `modules`.
- **Columns**:
  - `id` UUIDv4, PK, `server_default gen_random_uuid()`
  - `sku` `varchar(100)`, not null — case-insensitive unique via `lower(sku)`
  - `name` `varchar(200)`, not null
  - `description` `text`, nullable
  - `version` `varchar(40)`, not null, default `'v1.0'` — free-text, no implicit versioning
  - `family` `varchar(40)`, not null, default `'Board'` — CHECK in `('Board', 'Device', 'Bundle', 'Case')` (DB-enforced enum)
  - `fabricante` `varchar(120)`, nullable
  - `location` `varchar(100)`, nullable — e.g. `G-M-01`
  - `tipo_almacenamiento` `varchar(80)`, nullable — FE-enforced enum `Gaveta | Almacén`
  - `stock` `integer`, not null, default `0` — assembled units in the warehouse
  - `notas` `text`, nullable
  - `fecha_creacion` `date`, nullable
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: unique functional `uq_modules_sku_lower (lower(sku))`; `ix_modules_name_lower (lower(name))`.
- **Later migration**: `family` column added in `20260525_2000_modules_family.py` (default `'Board'` for back-fill, CHECK constraint enforced at DB level).

### 3a. ModuleChild

An edge in the module DAG. Each row points from a `parent_module_id` to **exactly one** of (`child_module_id`, `child_component_id`) — enforced via XOR CHECK constraint. The same `(parent, child)` pair is unique (one edge per pair); to repeat a hijo `N` times, raise `quantity`. Cycles among module nodes are forbidden (checked by `ModuleService` before insert; trivial self-reference also blocked at DB level).

- **Status**: ✅ Implemented in `module-management` (migration `20260524_1938`).
- **Table**: `module_children`.
- **Columns**:
  - `id` UUIDv4, PK
  - `parent_module_id` UUIDv4, FK → `modules.id` ON DELETE CASCADE
  - `child_module_id` UUIDv4, nullable, FK → `modules.id` ON DELETE CASCADE
  - `child_component_id` UUIDv4, nullable, FK → `components.id` ON DELETE CASCADE
  - `quantity` `smallint`, not null, CHECK `> 0`
  - `sort_order` `integer`, not null, default `0`
  - `notes` `text`, nullable
  - `created_at` / `updated_at` `timestamptz`
- **Constraints**:
  - CHECK `(child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1` (XOR)
  - CHECK `child_module_id IS NULL OR child_module_id <> parent_module_id` (no direct self-ref)
- **Partial UNIQUE indexes**:
  - `uq_module_children_parent_child_module (parent_module_id, child_module_id) WHERE child_module_id IS NOT NULL`
  - `uq_module_children_parent_child_component (parent_module_id, child_component_id) WHERE child_component_id IS NOT NULL`
- **Non-unique indexes**: `(parent_module_id, sort_order)`, `(child_module_id)`, `(child_component_id)`.

#### Aggregations (`Module` server-computed, never persisted)

For a module `M` the API hydrates the following on every `GET /api/v1/modules/{id}` (and `GET /api/v1/modules`):

| Aggregate | Formula | Notes |
|---|---|---|
| `precio_total` | `Σ child ∈ direct_children: quantity × child_price` | Component children → `current_price_per_100_eur`. Module children → recursively, `precio_total(M')`. Returns `null` when no descendants have prices. |
| `aggregated_nato_score` | `MIN_lex(F < D < C < B < A < A+)` over **component descendants** | The worst score across all leaf components contributes. `null` when no descendant components. |
| `aggregated_tier` | `MIN_numeric` over component descendants | Tier 1 = most critical = worst. `null` when no descendant components. |
| `aggregated_expires_at` | `MIN(date)` over descendant components with an active scoring | `null` when no scorings present. |
| `buildable_stock` | `MIN(component.stock // edge.quantity)` over direct **component** edges | Submodule children currently don't contribute (only direct components count); the FE surfaces this caveat in a tooltip. Returns `0` when no direct component children. |

The recursive walks are bounded to depth 8 to prevent runaway in case of misconfigured DAGs.

### 4. Component

A leaf in the asset tree representing a single electronic part. Carries identifying metadata (mpn/sku/name/description/datasheet), warehouse location + storage type, manufacturer, preferred supplier (FK), current on-hand stock, and the two **cached** classification fields the workshop operates on: `tier` (criticality 1–4) and `nato_score` (geopolitical origin scoring A+/A/B/C/D/F). The classification cache is kept in sync with whichever `component_nato_scorings` row is currently `status='active'` — never edited directly via the component PATCH path.

- **Status**: ✅ Implemented (introduced by `component-management`; iterated across migrations `20260523_1800`, `20260524_1200`, `20260525_0900`).
- **Table**: `components`.
- **Columns**:
  - `id` UUIDv4, PK, `server_default gen_random_uuid()`
  - `mpn` `varchar(100)`, not null — manufacturer part number; case-insensitive unique via functional index on `lower(mpn)`
  - `sku` `varchar(100)`, nullable
  - `name` `varchar(200)`, not null
  - `family` `varchar(100)`, not null — one of `Microcontroladores`, `Sensores`, `Conectores`, `Resistencias`, `Condensadores`, `Inductores`, `Diodos`, `Transistores`, `Módulos`, `Fuentes de alimentación` (FE-enforced enum, BE column is free-text)
  - `description` `text`, nullable
  - `datasheet_url` `text`, nullable
  - `location` `varchar(100)`, nullable — warehouse slot (e.g. `G-A-12`)
  - `fabricante` `varchar(120)`, nullable — manufacturer name (free text)
  - `tipo_almacenamiento` `varchar(80)`, nullable — FE-enforced enum `Gaveta` | `Almacén`
  - `holded_id` `varchar(80)`, nullable — external bookkeeping ID
  - `fecha_creacion` `date`, nullable — user-supplied creation date (distinct from `created_at` timestamp)
  - `notas` `text`, nullable
  - `stock` `integer`, not null, default `0` — current on-hand quantity
  - `stock_min` `integer`, nullable — explicit floor; when null the effective minimum is `tier * 5`
  - `tier` `smallint`, not null — CHECK in `(1, 2, 3, 4)` (1 = most critical). Cached from the active scoring.
  - `nato_score` `varchar(4)`, not null — CHECK in `('A+', 'A', 'B', 'C', 'D', 'F')`. Cached from the active scoring.
  - `country_of_origin` `varchar(2)`, nullable — ISO 3166-1 alpha-2
  - `proveedor_preferente_id` UUIDv4, nullable, FK → `suppliers.id` ON DELETE SET NULL
  - `last_supplier_sync_at` `timestamptz`, nullable — last time the supplier sync (change `supplier-sync`, migration `20260528_1330`) wrote a `supplier_prices` or `supplier_stocks` row for this component. NULL on components that have never been synced.
  - **Blended supplier-derived columns** (change `ingest-component-from-mpn`, migration `20260613_1000`): `lifecycle_status` `varchar(32)`, `last_buy_date` `date`, `discontinued` `boolean`, `end_of_life` `boolean`, `moq` `integer`, `order_multiple` `integer`, `lead_time_days` `integer`, `unit_weight_kg` `numeric(12,6)`, `image_url` `text` — all nullable, populated at ingest from the supplier APIs and refreshable by sync.
  - **Family-inference provenance** (same migration): `family_inferred_supplier` `varchar(32)`, `family_inferred_match_type` `varchar(32)`, `raw_category_id` `varchar(64)`, `raw_category_name` `text`, `raw_tariff_code` `varchar(32)`, `family_confidence` `smallint` (all nullable), `family_needs_review` `boolean` not null default `false`. These record which supplier signal decided the family so a mis-mapping is auditable and components can be re-classified in bulk without re-calling the APIs.
  - `created_at` / `updated_at` `timestamptz`, server-defaulted to `now()`
- **Indexes**: unique functional `uq_components_mpn_lower`, plus per-column `lower(...)` indexes on `sku`, `name`, `family` for case-insensitive search; `ix_components_proveedor_preferente_id`.

### 4a. Blended ingestion tables (change `ingest-component-from-mpn`)

Per-supplier data captured when a component is ingested from its MPN (migration `20260613_1001`). All cascade-delete with their parent component.

- **`component_parameters`** — parametric specs as N key/value rows: `component_id` FK, `supplier`, `param_key` (stable supplier parameter id when present), `param_label`, `param_value`, `param_unit`.
- **`component_compliance`** — export/customs + compliance codes: `component_id` FK, `supplier`, `code_type` (ECCN/HTS/RoHS/REACH/MSL/country…), `code_value`.
- **`component_documents`** — datasheets and other documents (multiple per component): `component_id` FK, `supplier`, `doc_type`, `url`, `file_name`, `size_bytes`, `language`, `blob_path` (Azure Blob path of the archived PDF, `datasheets/<sha256>.pdf`), `sha256`, `content_type`, `fetched_at`.
- **`component_cross_refs`** — alternates/substitutes/aliases: `component_id` FK, `supplier`, `ref_type`, `ref_value`.
- **`component_supplier_payloads`** — raw JSONB snapshot of each supplier's product object (`component_id`, `supplier`, `raw_payload jsonb`, `fetched_at`), unique on `(component_id, supplier)`, so doc-only fields are re-parseable without an API call.

### 4b. ComponentFamilyRule (change `ingest-component-from-mpn`)

Editable seed table (migration `20260613_1001`, seeded `20260613_1002`) mapping a single supplier category signal to one internal family. `FamilyInferenceService` evaluates these by signal strength (stable `category_id` 100 > HS `tariff_prefix` 70 > localized `name_keyword` 40).

- **Table**: `component_family_rules`.
- **Columns**: `id` PK, `supplier` (CHECK in the five codes), `match_type` (CHECK in `category_id`|`tariff_prefix`|`name_keyword`), `match_value`, `family` (CHECK in the nine families), `confidence` `smallint`, `priority` `smallint`, `enabled` `boolean`, `notes` `text`. Unique on `(supplier, match_type, match_value)`. Grows from logged misses without a code deploy.

### 5. Supplier

A distributor / vendor (DigiKey, Mouser, Farnell, RS, TME…). Standalone entity referenced by `components.proveedor_preferente_id`, `supplier_prices.supplier_id`, `supplier_stocks.supplier_id`, and `stock_events.supplier_id`. Future KiCAT / Holded sync USs will be the source of writes — for now, the seed script inserts a handful of well-known suppliers and the UI is read-only.

- **Status**: ✅ Implemented in `component-management` (migration `20260524_1200`).
- **Table**: `suppliers`.
- **Columns**:
  - `id` UUIDv4, PK
  - `name` `varchar(120)`, not null, unique (case-insensitive via functional index)
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: unique functional `uq_suppliers_name_lower`.

### 6. SupplierPrice

Time-series of catalogue prices broken down by `(component, supplier, quantity-tier, valid_from)`. Drives the "Precios de hoy" table (latest per supplier × tier) and the "Histórico de precios" chart (filtered by tier + period). The component table caches the latest 100u price from the preferred supplier in `current_price_per_100_eur` (server-computed, not persisted).

- **Status**: ✅ Implemented in `component-management` (migration `20260524_1200`).
- **Table**: `supplier_prices`.
- **Columns**:
  - `id` UUIDv4, PK
  - `component_id` UUIDv4, FK → `components.id` ON DELETE CASCADE
  - `supplier_id` UUIDv4, FK → `suppliers.id` ON DELETE CASCADE
  - `qty_tier` `smallint`, not null — CHECK in `(1, 10, 100, 1000)` (price-break columns from the catalogue)
  - `price` `numeric(12,4)`, not null — CHECK `>= 0`, EUR
  - `valid_from` `date`, not null — date the snapshot was taken
  - `price_original` `numeric(12,4)`, nullable — supplier's native price BEFORE FX conversion (change `supplier-sync`, migration `20260528_1330`). Filled by the daily sync. NULL for historical rows or when FX conversion was identity (e.g. supplier already quoted EUR).
  - `currency_original` `varchar(3)`, nullable — ISO 4217 of `price_original`. NULL on historical rows.
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: composite `(component_id, supplier_id, qty_tier, valid_from DESC)`; `(component_id, valid_from DESC)` for chart queries.

### 7. SupplierStockSnapshot

Time-series of supplier-side stock availability (the "Stock disponible en proveedores" chart on the component detail). One row per `(component, supplier, snapshot_at)`. Will eventually be populated by the KiCAT / Holded sync USs.

- **Status**: ✅ Implemented in `component-management` (migration `20260524_1200`).
- **Table**: `supplier_stocks`.
- **Columns**:
  - `id` UUIDv4, PK
  - `component_id` UUIDv4, FK → `components.id` ON DELETE CASCADE
  - `supplier_id` UUIDv4, FK → `suppliers.id` ON DELETE CASCADE
  - `quantity` `integer`, not null — CHECK `>= 0`
  - `snapshot_at` `date`, not null
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: composite `(component_id, supplier_id, snapshot_at DESC)`.

### 8. StockEvent

Append-only ledger of every quantity-affecting event on the internal warehouse — for **components** (`purchase`, `consumption`) or **modules** (`fabricated`, `delivered`). Drives the "Historial de compras" modal on the component detail and the "Histórico de fabricación" modal on the module detail. Source of truth for derived metrics: weighted FIFO cost of the current stock, supplier spend aggregates, "Proveedor más comprado" across module descendants.

Polymorphic owner: each row carries **exactly one** of `component_id` / `module_id` — enforced via XOR CHECK constraint.

- **Status**: ✅ Implemented in `component-management` (migration `20260524_1200`); extended to module-level events in `module-management` (migration `20260525_1800_stock_events_module_level.py`).
- **Table**: `stock_events`.
- **Columns**:
  - `id` UUIDv4, PK
  - `component_id` UUIDv4, **nullable**, FK → `components.id` ON DELETE CASCADE
  - `module_id` UUIDv4, **nullable**, FK → `modules.id` ON DELETE CASCADE
  - `kind` `varchar(16)`, not null — CHECK in `('purchase', 'consumption', 'fabricated', 'delivered')`
    - `purchase`, `consumption` → component-level (component_id set)
    - `fabricated`, `delivered` → module-level (module_id set)
  - `quantity` `integer`, not null — CHECK `> 0` (sign is implied by `kind`)
  - `occurred_at` `date`, not null
  - `notes` `text`, nullable
  - `supplier_id` UUIDv4, nullable, FK → `suppliers.id` ON DELETE SET NULL — required when `kind='purchase'`, null otherwise
  - `unit_cost` `numeric(12,4)`, nullable, EUR — `purchase` / `fabricated` (computed cost per unit assembled)
  - `total_cost` `numeric(14,4)`, nullable, EUR — `purchase` / `fabricated` (precomputed = `quantity × unit_cost`)
  - `currency` `varchar(3)`, not null, default `'EUR'`
  - `project_id` UUIDv4, nullable — `consumption` only. FK → `projects.id` ON DELETE SET NULL (materialised in `project-management` migration `20260526_0900`).
  - `project_name_snapshot` `varchar(200)`, nullable — denormalised so the audit trail survives project renames/deletes
  - `customer_id_holded` `varchar(64)`, nullable — `delivered` only (Holded customer ID for the module shipment)
  - `customer_name_snapshot` `varchar(200)`, nullable — `delivered` only, denormalised for audit
  - `created_at` / `updated_at` `timestamptz`
- **Constraints**: XOR CHECK on `(component_id IS NOT NULL)::int + (module_id IS NOT NULL)::int = 1`.
- **Indexes**: composite `(component_id, occurred_at DESC)` (component path); `(module_id, occurred_at DESC)` (module path); partial `(supplier_id) WHERE kind='purchase'`.

### 9. ComponentNatoScoring

Per-execution audit envelope for a NATO classification. One row per "click of Clasificar componente" — exactly one row per component is `status='active'` (enforced by a partial UNIQUE index); previous executions are kept with `status='archived'`. Carries the classifier (FK to `users`), the date it was classified, an expiration date (default `classified_at + 6 months`), and optional notes. The active row's `(nato_score, tier)` is mirrored back to the `components` cache on every create.

- **Status**: ✅ Implemented in `component-management` (migration `20260525_0900`).
- **Table**: `component_nato_scorings`.
- **Columns**:
  - `id` UUIDv4, PK
  - `component_id` UUIDv4, FK → `components.id` ON DELETE CASCADE
  - `nato_score` `varchar(4)`, not null — CHECK in `('A+', 'A', 'B', 'C', 'D', 'F')`
  - `tier` `smallint`, not null — CHECK in `(1, 2, 3, 4)`
  - `classified_at` `date`, not null
  - `expires_at` `date`, not null
  - `classified_by_user_id` UUIDv4, nullable, FK → `users.id` ON DELETE SET NULL
  - `status` `varchar(16)`, not null — CHECK in `('active', 'archived')`
  - `notes` `text`, nullable
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: partial UNIQUE `uq_nato_scorings_one_active_per_component (component_id) WHERE status='active'`; `(component_id, created_at DESC)`.

### 10. ScoringClassification

Per-sub-part classification owned by a `ComponentNatoScoring`. The "Detalle de Clasificación" table in the NATO scoring modal. Each row classifies a discrete sub-part of the parent component (e.g. "Chip principal", "Encapsulado plástico", "Sustrato cerámico") with its own fabricante / origin / score and an optional cross-reference to either another `Component` or a free-text URL — the two cross-references are mutually exclusive.

- **Status**: ✅ Implemented in `component-management` (migration `20260525_0900`).
- **Table**: `scoring_classifications`.
- **Columns**:
  - `id` UUIDv4, PK
  - `nato_scoring_id` UUIDv4, FK → `component_nato_scorings.id` ON DELETE CASCADE
  - `part_label` `varchar(200)`, not null
  - `fabricante` `varchar(120)`, nullable
  - `country_of_origin` `varchar(2)`, nullable
  - `nato_score` `varchar(4)`, nullable — CHECK in `('A+', 'A', 'B', 'C', 'D', 'F')` when set
  - `verificado` `boolean`, not null, default `false`
  - `notas` `text`, nullable
  - `reference_component_id` UUIDv4, nullable, FK → `components.id` ON DELETE SET NULL
  - `reference_url` `text`, nullable
  - `sort_order` `integer`, not null, default `0`
  - `created_at` / `updated_at` `timestamptz`
- **Constraints**: CHECK `reference_component_id IS NULL OR reference_url IS NULL` (mutex).
- **Indexes**: `(nato_scoring_id, sort_order)`.

### 11. ScoringAlternative

Per-execution directional pointer to an alternative `Component` that could replace the one being classified. Drives the "Otras Opciones OTAN" table in the scoring modal. The response is hydrated server-side with a `ComponentSummary` (mpn, name, fabricante, country, score, tier, stock, current 100u price) so the table can render without a second round-trip.

- **Status**: ✅ Implemented in `component-management` (migration `20260525_0900`).
- **Table**: `scoring_alternatives`.
- **Columns**:
  - `id` UUIDv4, PK
  - `nato_scoring_id` UUIDv4, FK → `component_nato_scorings.id` ON DELETE CASCADE
  - `alternative_component_id` UUIDv4, FK → `components.id` ON DELETE CASCADE
  - `notes` `text`, nullable
  - `sort_order` `integer`, not null, default `0`
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: `(nato_scoring_id, sort_order)`.

### 12. RefreshToken

Allows minting new access tokens without re-prompting credentials, and is the surface used by logout and forced sign-out.

- **Status**: ✅ Implemented in `login-en-asm`.
- **Table**: `refresh_tokens`.
- **Columns**:
  - `id` UUIDv4, PK
  - `user_id` UUIDv4, FK → `users.id` ON DELETE CASCADE
  - `jti_hash` `varchar(64)`, unique, not null — SHA-256 hex of the JWT's `jti` claim (the `jti` is itself 128-bit CSPRNG, so SHA-256 is sufficient)
  - `expires_at` `timestamptz`, not null
  - `revoked_at` `timestamptz`, nullable — set on rotation, logout, password reset
  - `created_from_ip` `inet`, nullable
  - `user_agent` `varchar(500)`, nullable
  - `created_at` / `updated_at`
- **Indexes**: `ix_refresh_tokens_user_id`, unique `ix_refresh_tokens_jti_hash`.

### 13. PasswordResetToken

Single-use token redeemable to set a new password. The token itself never travels through the DB — only its Argon2id hash.

- **Status**: ✅ Implemented in `login-en-asm`.
- **Table**: `password_reset_tokens`.
- **Columns**:
  - `id` UUIDv4, PK
  - `user_id` UUIDv4, FK → `users.id` ON DELETE CASCADE
  - `token_hash` `varchar(255)`, unique, not null — Argon2id
  - `expires_at` `timestamptz`, not null (default TTL 1 hour, configurable)
  - `used_at` `timestamptz`, nullable
  - `created_at` / `updated_at`
- **Indexes**: `ix_password_reset_tokens_user_id`, unique `ix_password_reset_tokens_token_hash`.

### 14. SupplierSyncRun

Audit telemetry for the daily Celery sync (change `supplier-sync`). One row per `sync_one_supplier` invocation — daily Beat-triggered AND ad-hoc operator triggers (`POST /api/v1/supplier-sync/runs?supplier=...`). Drives the admin "Recent runs" view and the per-supplier success/failure timeline.

- **Status**: ✅ Implemented in `supplier-sync` (migration `20260528_1330`).
- **Table**: `supplier_sync_runs`.
- **Columns**:
  - `id` UUIDv4, PK, `server_default gen_random_uuid()`
  - `supplier` `varchar(32)`, not null — CHECK in `('mouser', 'digikey', 'tme', 'farnell', 'rs')`
  - `started_at` `timestamptz`, not null, default `now()`
  - `finished_at` `timestamptz`, nullable — set when the task finalises
  - `components_processed` `integer`, not null, default 0 — components walked (whether or not the supplier had data)
  - `components_updated` `integer`, not null, default 0 — components for which a `supplier_prices` / `supplier_stocks` row was written
  - `errors_count` `integer`, not null, default 0
  - `status` `varchar(16)`, not null, default `'running'` — CHECK in `('running', 'success', 'partial', 'failed')`
    - `success`: errors_count == 0 and at least one component processed.
    - `partial`: some errors, some updates — the daily sync proceeds best-effort.
    - `failed`: every component errored (or every consulted component failed).
  - `error_summary` `text`, nullable — short free-text summary set when `status='failed'` so the admin view can show the top-level cause without opening the per-error table.
  - `created_at` `timestamptz`, not null, default `now()`
- **Indexes**: `(supplier, started_at DESC)` for the per-supplier timeline; `(status)` for "find all currently-running" queries.

### 15. SupplierSyncError

Per-component error captured by the daily sync (change `supplier-sync`). One row per `(run, component, error)`. The Celery task continues after each failure and records the typed error code (`HTTP_5XX`, `AUTH_FAILED`, `RATE_LIMITED`, etc.); the `error_code` set is the same union the adapter exceptions carry. Drives the per-run drill-down (`GET /api/v1/supplier-sync/runs/{id}/errors`).

- **Status**: ✅ Implemented in `supplier-sync` (migration `20260528_1330`).
- **Table**: `supplier_sync_errors`.
- **Columns**:
  - `id` UUIDv4, PK, `server_default gen_random_uuid()`
  - `run_id` UUIDv4, not null, FK → `supplier_sync_runs.id` ON DELETE CASCADE
  - `component_id` UUIDv4, not null, FK → `components.id` ON DELETE CASCADE
  - `supplier` `varchar(32)`, not null — CHECK in `('mouser', 'digikey', 'tme', 'farnell', 'rs')`
  - `error_code` `varchar(64)`, not null — CHECK in `('RATE_LIMITED', 'NOT_FOUND', 'HTTP_5XX', 'PARSE_ERROR', 'AUTH_FAILED', 'FX_UNAVAILABLE', 'TIMEOUT', 'UNKNOWN')`
  - `error_message` `text`, not null — bounded to 2000 chars at the application layer
  - `occurred_at` `timestamptz`, not null, default `now()`
- **Indexes**: `(run_id, occurred_at DESC)` for the per-run drill-down; `(component_id)` for "all failures on this MPN" queries.
- **Retention**: not pruned automatically — when the volume becomes a concern, add a daily cleanup task (out of scope for the initial change).

## Conventions to apply in each upcoming migration

- **Primary keys**: UUIDv4, `server_default text("gen_random_uuid()")` (uses `pgcrypto`).
- **Timestamps**: `created_at` and `updated_at` are `TIMESTAMPTZ`, server-defaulted to `now()` with an `onupdate` trigger for `updated_at`.
- **Hierarchy**: the asset tree uses an `ltree` `path` column on `Module` and `Component`, with a GiST index.
- **Soft delete**: not enabled by default. Justify per entity if introduced.
- **Naming**: snake_case table names, plural; foreign keys named `<entity>_id`.

## Entity-Relationship overview

A full ER diagram will be added when the first business entities ship. For now, the planned relationships are:

```
User 1───* RefreshToken
User *───* Project              (via project_memberships, see Login US for the join table)
User 1───* ComponentNatoScoring (classified_by_user_id)

Project 1───* Module
Module  1───* ModuleChild       (parent_module_id)
ModuleChild *───1 Module        (child_module_id, nullable)     -- XOR with child_component_id
ModuleChild *───1 Component     (child_component_id, nullable)  -- XOR with child_module_id

  -- DAG semantics: a Module or Component can be a child of N parents.
  -- Cycles among Module nodes are forbidden (BE-enforced via WITH RECURSIVE
  -- before insert).

Supplier 1───* SupplierPrice
Supplier 1───* SupplierStockSnapshot
Supplier 0..1───* Component     (proveedor_preferente_id, nullable)
Supplier 0..1───* StockEvent    (purchase kind only)

Component 1───* SupplierPrice
Component 1───* SupplierStockSnapshot
Component 1───* StockEvent
Component 1───* ComponentNatoScoring (1 active, N archived)

ComponentNatoScoring 1───* ScoringClassification
ComponentNatoScoring 1───* ScoringAlternative
ScoringAlternative *───1 Component  (alternative_component_id)
ScoringClassification 0..1───1 Component (reference_component_id; XOR reference_url)

SupplierSyncRun  1───* SupplierSyncError
SupplierSyncError *───1 Component  (component_id)
  -- The run row is the per-(supplier, invocation) audit; the error rows
  -- attach to the specific components whose fetch failed during the run.
```
