# Data model spec — project-management

Adds three new tables (`customers`, `projects`, `project_children`) and materializes the previously-deferred `stock_events.project_id` FK. No changes to `components`, `modules`, `module_children`, `supplier_*`, or `component_nato_scorings`.

## `customers`

```sql
CREATE TABLE customers (
    id          uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    holded_id   varchar(64)   NOT NULL,
    name        varchar(200)  NOT NULL,
    holded_url  varchar(500)  NULL,
    notas       text          NULL,
    created_at  timestamptz   NOT NULL DEFAULT now(),
    updated_at  timestamptz   NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_customers_holded_id_lower
    ON customers (lower(holded_id));
```

- `holded_id`: identifier from Holded; the FE uses it to build the customer link. Case-insensitive UNIQUE.
- `name`: denormalised so the UI doesn't depend on Holded availability and to make audit trails human-readable.
- `holded_url`: explicit override. If NULL, the FE constructs `${HOLDED_BASE_URL}/contact/${holded_id}`.

## `projects`

```sql
CREATE TABLE projects (
    id                       uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    code                     varchar(40)   NOT NULL,
    name                     varchar(200)  NOT NULL,
    description              text          NULL,
    status                   varchar(20)   NOT NULL DEFAULT 'Draft',
    customer_id              uuid          NULL,
    fecha_inicio             date          NULL,
    fecha_entrega_estimada   date          NULL,
    fecha_entrega_real       date          NULL,
    notas                    text          NULL,
    created_at               timestamptz   NOT NULL DEFAULT now(),
    updated_at               timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT ck_projects_status
        CHECK (status IN ('Draft', 'Active', 'Delivered', 'Archived')),
    CONSTRAINT fk_projects_customer
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX uq_projects_code_lower
    ON projects (lower(code));
CREATE INDEX ix_projects_name_lower
    ON projects (lower(name));
CREATE INDEX ix_projects_status   ON projects (status);
CREATE INDEX ix_projects_customer_id ON projects (customer_id);
```

- `code`: user-typed business identifier. Case-insensitive UNIQUE. NOT auto-generated. Editable.
- `status`: DB-enforced enum. Soft-delete sets it to `Archived`; the row stays.
- `fecha_entrega_real`: nullable in DB; the BE auto-fills it with today's date when a PATCH transitions the status to `Delivered` and the value is not provided.

## `project_children`

```sql
CREATE TABLE project_children (
    id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_project_id    uuid          NOT NULL,
    child_module_id      uuid          NULL,
    child_component_id   uuid          NULL,
    quantity             smallint      NOT NULL,
    sort_order           integer       NOT NULL DEFAULT 0,
    notes                text          NULL,
    created_at           timestamptz   NOT NULL DEFAULT now(),
    updated_at           timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT fk_project_children_parent
        FOREIGN KEY (parent_project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_project_children_module
        FOREIGN KEY (child_module_id) REFERENCES modules(id) ON DELETE CASCADE,
    CONSTRAINT fk_project_children_component
        FOREIGN KEY (child_component_id) REFERENCES components(id) ON DELETE CASCADE,
    CONSTRAINT ck_project_children_quantity_positive
        CHECK (quantity > 0),
    CONSTRAINT ck_project_children_xor
        CHECK (
            (child_module_id IS NOT NULL)::int
          + (child_component_id IS NOT NULL)::int
          = 1
        )
);

CREATE UNIQUE INDEX uq_project_children_parent_child_module
    ON project_children (parent_project_id, child_module_id)
    WHERE child_module_id IS NOT NULL;

CREATE UNIQUE INDEX uq_project_children_parent_child_component
    ON project_children (parent_project_id, child_component_id)
    WHERE child_component_id IS NOT NULL;

CREATE INDEX ix_project_children_parent_sort
    ON project_children (parent_project_id, sort_order);
CREATE INDEX ix_project_children_child_module
    ON project_children (child_module_id);
CREATE INDEX ix_project_children_child_component
    ON project_children (child_component_id);
```

- XOR CHECK: exactly one of `child_module_id` / `child_component_id` is non-null.
- Partial UNIQUE indexes guarantee one row per `(parent, child)` pair. To repeat a child N times, raise `quantity`.
- CASCADE on `parent_project_id` so soft-delete doesn't leave dangling edges *if* a future hard-delete operation is ever wired up. The current soft-delete (`status='Archived'`) does NOT delete rows here.
- No cycle detection — projects are never children of anything.

## `stock_events` — FK materialization

The column `project_id` already exists from the `component-management` change (defined as `uuid NULL`, with FK deferred until the Project entity shipped). This change adds the FK:

```sql
ALTER TABLE stock_events
    ADD CONSTRAINT fk_stock_events_project
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL;
```

Other columns on `stock_events` (`project_name_snapshot`, `customer_id_holded`, `customer_name_snapshot`) stay unchanged — append-only ledger semantics.

## Migration

A single Alembic revision creates the three tables and adds the FK on `stock_events`:

- `upgrade()`:
  1. `op.create_table("customers", ...)` with all columns/constraints/indexes above.
  2. `op.create_table("projects", ...)`.
  3. `op.create_table("project_children", ...)`.
  4. `op.create_foreign_key("fk_stock_events_project", "stock_events", "projects", ...)`.
- `downgrade()`:
  1. Drop FK on `stock_events`.
  2. Drop the three tables in reverse order.

The functional indexes (`uq_customers_holded_id_lower`, `uq_projects_code_lower`, `ix_projects_name_lower`) are created via `op.execute(...)` since Alembic autogenerate doesn't render them.

## Relationships diagram

```
customers (1) ──┐
                └─< projects (1) ──< project_children >── (1) modules ──< module_children >── (1) components
                                                       └────────────────< project_children >── (direct leaves)

stock_events.project_id   ──→ projects.id   ON DELETE SET NULL
stock_events.component_id ──→ components.id (existing)
stock_events.module_id    ──→ modules.id    (existing)
```

- `customer ──< projects`: one customer can own many projects.
- `project ──< project_children`: edges to modules and/or components (XOR per row).
- `project_children` cascades on parent delete (theoretical — soft-delete keeps everything).
- `stock_events.project_id` ON DELETE SET NULL preserves the ledger if a project is ever hard-deleted in the future.

## Seed dataset (for `seed_projects`)

- 3 customers:
  - `HLD-CUST-001` — "ACME Aerospace" (no `holded_url` override).
  - `HLD-CUST-002` — "Defensa Levante".
  - `HLD-CUST-003` — "Tierra Audio Internal" (overrides `holded_url` to `https://internal.example/contact/3`).
- 5 projects exercising all 4 statuses:
  - `PRY-2026-001` — `Draft` — assigned to ACME — empty BOM.
  - `PRY-2026-002` — `Active` — assigned to ACME — BOM with 2 modules + 1 component.
  - `PRY-2026-003` — `Active` — assigned to Defensa Levante — BOM mixing 1 module (with deep sub-modules) + 4 components.
  - `PRY-2026-004` — `Delivered` — assigned to Tierra Audio Internal — small BOM with fecha_entrega_real set.
  - `PRY-2026-005` — `Archived` — old, kept only to validate the default exclusion from list.
- 4 sample consumption `stock_events` linking to `PRY-2026-002` and `PRY-2026-003` so the "Histórico de eventos" tab has rows.
