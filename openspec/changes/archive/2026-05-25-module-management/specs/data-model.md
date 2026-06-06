# Data model spec — module-management

Adds two new tables (`modules`, `module_children`) and references the existing `components` table.

## `modules`

```sql
CREATE TABLE modules (
    id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    sku             varchar(100)  NOT NULL,
    name            varchar(200)  NOT NULL,
    description     text,
    version         varchar(40)   NOT NULL DEFAULT 'v1.0',
    fabricante      varchar(120),
    location        varchar(100),
    tipo_almacenamiento varchar(80),
    stock           integer       NOT NULL DEFAULT 0,
    notas           text,
    fecha_creacion  date,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    updated_at      timestamptz   NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_modules_sku_lower ON modules (lower(sku));
CREATE INDEX ix_modules_name_lower ON modules (lower(name));
```

## `module_children`

```sql
CREATE TABLE module_children (
    id                  uuid       PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_module_id    uuid       NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    child_module_id     uuid                REFERENCES modules(id) ON DELETE CASCADE,
    child_component_id  uuid                REFERENCES components(id) ON DELETE CASCADE,
    quantity            smallint   NOT NULL CHECK (quantity > 0),
    sort_order          integer    NOT NULL DEFAULT 0,
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_module_children_xor_child CHECK (
        (child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1
    ),
    CONSTRAINT ck_module_children_no_self_ref CHECK (
        child_module_id IS NULL OR child_module_id <> parent_module_id
    )
);

CREATE UNIQUE INDEX uq_module_children_parent_child_module
    ON module_children (parent_module_id, child_module_id)
    WHERE child_module_id IS NOT NULL;

CREATE UNIQUE INDEX uq_module_children_parent_child_component
    ON module_children (parent_module_id, child_component_id)
    WHERE child_component_id IS NOT NULL;

CREATE INDEX ix_module_children_parent_order
    ON module_children (parent_module_id, sort_order);
CREATE INDEX ix_module_children_child_module
    ON module_children (child_module_id);
CREATE INDEX ix_module_children_child_component
    ON module_children (child_component_id);
```

## ER additions

```
Module 1───* ModuleChild (parent_module_id)
ModuleChild *───1 Module    (child_module_id, nullable)      -- XOR with child_component_id
ModuleChild *───1 Component (child_component_id, nullable)   -- XOR with child_module_id

DAG semantics: a Module or Component can appear as a child of N parents.
Cycles among Module nodes are forbidden (BE-enforced via WITH RECURSIVE on insert).
```

## Aggregations (server-computed, not persisted)

See `design.md` for full formulas. Summary:

| Aggregate | Source | Formula | Notes |
|---|---|---|---|
| `precio_total(M)` | All children (recursive) | Σ `quantity × precio_hijo` | Component leaves use `current_price_per_100_eur`; sub-modules recurse. |
| `aggregated_nato_score(M)` | Component descendants (recursive) | `MIN(F<D<C<B<A<A+)` lex order | NULL if no descendant components. |
| `aggregated_tier(M)` | Component descendants (recursive) | `MIN(numeric)` (Tier 1 = worst) | NULL if no descendant components. |
| `aggregated_expires_at(M)` | Component descendants with active scoring | `MIN(date)` | Null-safe. |
| `buildable_stock(M)` | Direct children | `MIN(child.stock // child.quantity)` (modules count both assembled + buildable recursively) | Surfaced as a tooltip in FE. |

## Existing entities unchanged

- `components`: no schema changes. The new `module_children.child_component_id` references it via FK with `ON DELETE CASCADE` (deleting a Component removes it from all parent modules).
- `users`: unaffected.
- `suppliers`, `supplier_prices`, `supplier_stocks`, `stock_events`, `component_nato_scorings`, `scoring_classifications`, `scoring_alternatives`: unaffected.
