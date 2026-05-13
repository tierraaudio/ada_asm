# Data Model Documentation

This document is the **forward-looking catalogue** of entities planned for the ADA ASM system. As of this document, no business tables exist in the database — the Alembic baseline migration only enables required PostgreSQL extensions (`pgcrypto`, `ltree`). Each entity below names a future User Story that will introduce its column-level schema and constraints. **Do not treat this document as a schema** — it is intentionally specification-light until each entity lands.

## Model Descriptions

### 1. User

Represents an authenticated person who can access the ADA ASM application. Carries the global role (`admin` or `user`) and is referenced by `RefreshToken` and by per-project membership rows.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Login en ASM 1.0`.

### 2. Project

The top of the asset hierarchy. Sourced bidirectionally with Holded — created either inside ADA ASM (push to Holded) or polled from Holded (created in ADA ASM). Aggregates the Modules and Components that comprise the project's bill of materials.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Creación de proyecto en ASM automático desde Holded`.

### 3. Module

A grouping node in the asset tree. Can contain other Modules or Components. The tree has no fixed depth limit and is persisted using `ltree` so the path itself is queryable. Carries the rolled-up price computed from its children.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Creación de Módulo en ASM`.

### 4. Component

A leaf in the asset tree representing a single electronic part. Carries identifying metadata (name, description, datasheet URL), warehouse `location`, and the supplier that supplies it. Its current price is the latest entry for the component in `PriceSnapshot`.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Creación de Componentes en ASM`.

### 5. PriceSnapshot

Append-only time-series record of the price of one Component (or rolled-up Module) at one supplier, at one quantity tier (10 / 100 / 1000 units), at one point in time. The basis for historical price charts and alert evaluation.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Bulk update diario de precios de componentes y módulos`.

### 6. RefreshToken

Hashed (Argon2id) refresh tokens issued to a User upon login. Allow a new access token to be minted without re-prompting credentials, and provide a revocation surface for logout / forced sign-out.

- **Status**: Not yet implemented.
- **Introduced by**: User Story `Login en ASM 1.0`.

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
