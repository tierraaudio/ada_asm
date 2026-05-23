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

A leaf in the asset tree representing a single electronic part. Carries identifying metadata (name, description, datasheet URL), warehouse `location`, supplier, and the two classification fields the workshop operates on: `tier` (criticality A+/A/B/C/D) and `nato_score` (geopolitical origin scoring).

- **Status**: ✅ Implemented in migration `20260523_1800_component_management__components_and_purchases.py` (introduced by `component-management`).
- **Table**: `components`.
- **Columns**:
  - `id` UUIDv4, PK, `server_default gen_random_uuid()`
  - `mpn` `varchar(100)`, not null — manufacturer part number; case-insensitive unique via functional index on `lower(mpn)`
  - `sku` `varchar(100)`, nullable
  - `name` `varchar(200)`, not null
  - `family` `varchar(100)`, not null — e.g. `Sensores`, `Microcontroladores`
  - `description` `text`, nullable
  - `datasheet_url` `text`, nullable
  - `location` `varchar(100)`, nullable — warehouse slot
  - `supplier` `varchar(100)`, nullable
  - `price_per_100` `numeric(12,4)`, nullable — last known unit price for a 100-unit purchase
  - `stock` `integer`, not null, default `0` — current on-hand quantity
  - `tier` `varchar(8)`, not null — CHECK in `('A+','A','B','C','D')`
  - `nato_score` `varchar(16)`, not null — CHECK in `('100_otan','otan','allied_otan','neutral','high_risk','no_otan')`
  - `country_of_origin` `varchar(2)`, nullable — ISO 3166-1 alpha-2
  - `created_at` / `updated_at` `timestamptz`, server-defaulted to `now()`
- **Indexes**: unique functional `uq_components_mpn_lower`, plus per-column `lower(...)` indexes on `sku`, `name`, `family` for case-insensitive search.

### 5. ComponentPurchase

Append-only purchase history for a Component — one row per restock event. Drives the cost-trend chart and the per-component history view. Renamed from the original `PriceSnapshot` concept once we realised the team thinks in concrete "purchases" rather than abstract snapshots; a future `PriceSnapshot` may still ship to unify across suppliers + quantity tiers.

- **Status**: ✅ Implemented in `component-management`.
- **Table**: `component_purchases`.
- **Columns**:
  - `id` UUIDv4, PK
  - `component_id` UUIDv4, FK → `components.id` ON DELETE CASCADE
  - `purchased_at` `date`, not null
  - `quantity` `integer`, not null — CHECK `> 0`
  - `supplier` `varchar(100)`, not null
  - `unit_cost` `numeric(12,4)`, not null
  - `total_cost` `numeric(14,4)`, not null
  - `currency` `varchar(3)`, not null, default `'EUR'`
  - `created_at` / `updated_at` `timestamptz`, server-defaulted to `now()`
- **Indexes**: composite `(component_id, purchased_at DESC)` for paginated history listings.

### 6. RefreshToken

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

### 7. PasswordResetToken

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
User *───* Project    (via project_memberships, see Login US for the join table)
Project 1───* Module
Module 1───* Module          (self-reference)
Module 1───* Component
Component 1───* PriceSnapshot
Module    1───* PriceSnapshot   (rolled-up snapshots; optional, design TBD)
```
