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

The top of the asset hierarchy. Sourced bidirectionally with Holded — created either inside ADA ASM (push to Holded) or polled from Holded (created in ADA ASM). Aggregates the Modules and Components that comprise the project's bill of materials.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Creación de proyecto en ASM automático desde Holded`.

### 3. Module

A grouping node in the asset tree. Can contain other Modules or Components. The tree has no fixed depth limit and is persisted using `ltree` so the path itself is queryable. Carries the rolled-up price computed from its children.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Creación de Módulo en ASM`.

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
  - `created_at` / `updated_at` `timestamptz`, server-defaulted to `now()`
- **Indexes**: unique functional `uq_components_mpn_lower`, plus per-column `lower(...)` indexes on `sku`, `name`, `family` for case-insensitive search; `ix_components_proveedor_preferente_id`.

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

Append-only ledger of every quantity-affecting event on the internal warehouse — `purchase` (restock from a supplier) or `consumption` (allocated to a project). Drives the "Historial de compras" modal (Stock interno con eventos line chart, Proveedor más comprado bar chart, Estadísticas de compra, Alertas y recomendaciones) and is the source of truth for derived metrics (weighted FIFO cost of the current stock, supplier spend aggregates). Supersedes the original `component_purchases` table from the first draft of `component-management`; the previous table was dropped in the same change.

- **Status**: ✅ Implemented in `component-management` (migration `20260524_1200`).
- **Table**: `stock_events`.
- **Columns**:
  - `id` UUIDv4, PK
  - `component_id` UUIDv4, FK → `components.id` ON DELETE CASCADE
  - `kind` `varchar(16)`, not null — CHECK in `('purchase', 'consumption')`
  - `quantity` `integer`, not null — CHECK `> 0` (sign is implied by `kind`)
  - `occurred_at` `date`, not null
  - `notes` `text`, nullable
  - `supplier_id` UUIDv4, nullable, FK → `suppliers.id` ON DELETE SET NULL — required when `kind='purchase'`, null otherwise
  - `unit_cost` `numeric(12,4)`, nullable, EUR — purchase only
  - `total_cost` `numeric(14,4)`, nullable, EUR — purchase only (precomputed = `quantity × unit_cost`)
  - `currency` `varchar(3)`, not null, default `'EUR'`
  - `project_id` UUIDv4, nullable — consumption only (FK lands when the Project entity ships)
  - `project_name_snapshot` `varchar(200)`, nullable — denormalised so the audit trail survives project renames/deletes
  - `created_at` / `updated_at` `timestamptz`
- **Indexes**: composite `(component_id, occurred_at DESC)`; partial `(supplier_id) WHERE kind='purchase'`.

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
Module  1───* Module            (self-reference)
Module  1───* Component

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
```
