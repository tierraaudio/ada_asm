# API spec — module-management

All endpoints under `/api/v1/modules*` are protected with `Depends(require_user)` and return RFC 7807 problem details on errors.

## Endpoints

### `GET /api/v1/modules`

List modules (catalogue view).

Query params:
- `q` `string` (optional) — ILIKE match against `lower(sku)`, `lower(name)`, `lower(description)`.
- `page` `int` (default 1, min 1).
- `page_size` `int` (default 25, min 1, max 100).

Response 200: `PaginatedModules`
```ts
{
  items: ModuleSummary[],   // each item carries aggregated_* hydrated server-side
  total: number,
  page: number,
  page_size: number,
}
```

### `POST /api/v1/modules`

Create a module.

Body: `ModuleCreateRequest` (sku required + unique, name required, others optional).

Responses:
- 201 → `ModuleResponse`
- 409 `MODULE_SKU_ALREADY_REGISTERED`
- 422 on validation errors.

### `GET /api/v1/modules/{id}`

Module detail with hydrated aggregates, children (with `child_module` or `child_component` summary hydrated), and parents list.

Response 200: `ModuleResponse`
```ts
{
  ...ModuleBase,
  // Aggregates (server-computed):
  precio_total: string | null,           // EUR Decimal-as-string, null if no children
  aggregated_nato_score: NatoScore | null,
  aggregated_tier: 1|2|3|4 | null,
  aggregated_expires_at: string | null,  // ISO date
  buildable_stock: number,               // 0 if no children or any child has 0 effective stock

  children: ModuleChildResponse[],       // direct children, ordered by sort_order
  parents:  ModuleSummary[],             // modules that contain this one as a direct child
}
```

`ModuleChildResponse`:
```ts
{
  id: uuid,
  parent_module_id: uuid,
  child_module_id: uuid | null,
  child_component_id: uuid | null,
  quantity: number,                       // >= 1
  sort_order: number,
  notes: string | null,
  child_module: ModuleSummary | null,     // hydrated when child_module_id is set
  child_component: ComponentSummary | null,  // hydrated when child_component_id is set
}
```

Errors: 404 `MODULE_NOT_FOUND`.

### `PATCH /api/v1/modules/{id}`

Partial update. `id`, `created_at`, `updated_at` ignored if sent. `sku` is updatable; conflict raises 409 `MODULE_SKU_ALREADY_REGISTERED`.

Body: `ModuleUpdateRequest` (all fields optional).

Response 200: `ModuleResponse` (re-hydrated with aggregates).

Errors: 404, 409, 422.

### `DELETE /api/v1/modules/{id}`

Soft assumption: NOT idempotent on missing (returns 404) to match component semantics. ON DELETE CASCADE removes its `module_children` rows but does not cascade-delete child entities themselves.

Response: 204.

Errors: 404.

### `GET /api/v1/modules/{id}/tree`

Recursive expansion of the children subtree, depth-limited to 8 to bound the response size.

Response 200: `ModuleTreeResponse`
```ts
{
  module_id: uuid,
  depth_limit_reached: boolean,
  root: ModuleTreeNode,
}

ModuleTreeNode = {
  kind: "module" | "component",
  // module branch:
  module?: ModuleSummary & { aggregates: {...}, children: ModuleTreeNode[] },
  // component branch:
  component?: ComponentSummary,
  quantity: number,           // multiplied along the path? No — just the local edge quantity.
}
```

Errors: 404.

### `POST /api/v1/modules/{id}/children`

Add a child (module XOR component) with a quantity.

Body: `AddChildRequest`
```ts
{
  child_module_id?: uuid,
  child_component_id?: uuid,   // exactly one of the two must be set
  quantity: number,             // >= 1
  notes?: string,
  sort_order?: number,
}
```

Validation:
- XOR enforced (422 `INVALID_CHILD_REFERENCE`).
- If `child_module_id` is set, run cycle detection (`WITH RECURSIVE`) → 422 `MODULE_CYCLE_DETECTED` on hit.
- If the (parent, child) pair already exists → 422 `CHILD_ALREADY_PRESENT` (force the user to update quantity instead).

Response: 201 → `ModuleChildResponse`.

Errors: 404 (parent or child not found), 422.

### `PATCH /api/v1/modules/{id}/children/{child_id}`

Update `quantity` and/or `notes` and/or `sort_order` of an existing edge.

Body: `UpdateChildRequest`
```ts
{
  quantity?: number,     // >= 1
  notes?: string | null,
  sort_order?: number,
}
```

Response: 200 → `ModuleChildResponse`.

Errors: 404 (parent or edge not found), 422.

### `DELETE /api/v1/modules/{id}/children/{child_id}`

Remove an edge. Idempotent on missing (204).

Response: 204.

### `GET /api/v1/modules/{id}/price-history`

Aggregated price time-series.

Query params:
- `period` `enum` (`week | month | year`, default `year`).

Response 200: `ModulePriceHistoryResponse`
```ts
{
  module_id: uuid,
  period: "week" | "month" | "year",
  series: Array<{
    date: string,    // ISO date
    price: string,   // EUR Decimal-as-string
  }>,
}
```

If the module has no component descendants with `supplier_prices` in the period, `series` is `[]`.

Errors: 404.

## Error codes (added)

| Code | HTTP | When |
|---|---|---|
| `MODULE_NOT_FOUND` | 404 | Module id not in DB |
| `MODULE_SKU_ALREADY_REGISTERED` | 409 | `lower(sku)` unique violation on create/update |
| `MODULE_CYCLE_DETECTED` | 422 | Adding a child module would close a cycle |
| `CHILD_ALREADY_PRESENT` | 422 | (parent, child) edge already exists |
| `INVALID_CHILD_REFERENCE` | 422 | XOR violation (both or neither set) OR referenced module/component not found |

## OpenAPI sketches (schemas)

```yaml
ModuleSummary:
  type: object
  required: [id, sku, name, version, stock, created_at, updated_at]
  properties:
    id: { type: string, format: uuid }
    sku: { type: string }
    name: { type: string }
    version: { type: string }
    fabricante: { type: string, nullable: true }
    location: { type: string, nullable: true }
    tipo_almacenamiento: { type: string, nullable: true }
    stock: { type: integer, minimum: 0 }
    precio_total: { type: string, nullable: true, description: "Aggregated, server-computed (EUR Decimal as string)" }
    aggregated_nato_score: { type: string, enum: ["A+",A,B,C,D,F], nullable: true }
    aggregated_tier: { type: integer, enum: [1,2,3,4], nullable: true }
    aggregated_expires_at: { type: string, format: date, nullable: true }
    buildable_stock: { type: integer, minimum: 0 }
    created_at: { type: string, format: date-time }
    updated_at: { type: string, format: date-time }

ModuleResponse:
  allOf:
    - $ref: '#/components/schemas/ModuleSummary'
    - type: object
      properties:
        description: { type: string, nullable: true }
        notas: { type: string, nullable: true }
        fecha_creacion: { type: string, format: date, nullable: true }
        children:
          type: array
          items: { $ref: '#/components/schemas/ModuleChildResponse' }
        parents:
          type: array
          items: { $ref: '#/components/schemas/ModuleSummary' }
```
