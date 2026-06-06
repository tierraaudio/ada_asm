# API spec — project-management

All endpoints under `/api/v1/projects*`, `/api/v1/customers*`, the new `/projects-using` sub-resources on components/modules, and `/api/v1/config` are protected with `Depends(require_user)` and return RFC 7807 problem details on errors.

## Status enum

`ProjectStatus = "Draft" | "Active" | "Delivered" | "Archived"` — shared between BE (Pydantic Literal) and FE (TS type). Enforced by a DB CHECK constraint.

## Endpoints — Projects

### `GET /api/v1/projects`

List projects (catalogue view) with aggregates hydrated server-side.

Query params:
- `q` `string` (optional) — case-insensitive ILIKE match against `lower(code)`, `lower(name)`, `lower(customer.name)` (joined).
- `status` `ProjectStatus[]` (repeatable). When omitted, the BE applies the default filter "all except `Archived`". Combined with `include_archived=true`, the BE lifts the exclusion (and if `status[]` is empty, all statuses including Archived are returned).
- `include_archived` `bool` (default false). Opt-in to include `Archived` rows in the response. Independent of `status[]`.
- `customer_id` `UUID[]` (repeatable).
- `page` `int` (default 1, min 1).
- `page_size` `int` (default 25, min 1, max 100).

Response 200: `PaginatedProjects`

```ts
{
  items: ProjectSummary[],   // each item carries aggregated_* + customer hydrated server-side
  total: number,
  page: number,
  page_size: number
}
```

### `POST /api/v1/projects`

Create a project.

Request body: `ProjectCreateRequest`
```ts
{
  code: string,                       // required, 1..40, case-insensitive unique
  name: string,                       // required, 1..200
  description?: string | null,
  status?: ProjectStatus,             // default "Draft"
  customer_id?: string | null,        // UUID
  fecha_inicio?: string | null,       // YYYY-MM-DD
  fecha_entrega_estimada?: string | null,
  fecha_entrega_real?: string | null,
  notas?: string | null
}
```

Responses:
- `201` `ProjectResponse` (project + aggregates + empty `children` + customer summary).
- `409` `PROJECT_CODE_ALREADY_REGISTERED` — duplicate `code` (case-insensitive).
- `422` validation errors per Pydantic.

### `GET /api/v1/projects/{project_id}`

Project detail.

Responses:
- `200` `ProjectResponse` (project + aggregates + hydrated children + customer summary).
- `404` `PROJECT_NOT_FOUND`.

### `PATCH /api/v1/projects/{project_id}`

Partial update. Body is `ProjectUpdateRequest` (all fields optional). Immutable fields: `id`, `created_at`, `updated_at`. `code` IS mutable.

Special behaviour:
- If the PATCH transitions `status` to `Delivered` and `fecha_entrega_real` is not provided in the same body, the BE auto-fills it with `today()`.
- Any other status transition is allowed (including `Archived → Active` to "unarchive").

Responses:
- `200` `ProjectResponse`.
- `404` `PROJECT_NOT_FOUND`.
- `409` `PROJECT_CODE_ALREADY_REGISTERED` (if renaming to a taken code).

### `DELETE /api/v1/projects/{project_id}`

**Soft-delete**. Transitions `status` to `Archived`. The row stays; `project_children` are preserved. Idempotent.

Responses:
- `204`.
- `404` `PROJECT_NOT_FOUND` (when the project never existed; archiving an already-archived project returns 204 since the post-state is identical).

### `POST /api/v1/projects/{project_id}/children`

Add an edge. Payload `AddProjectChildRequest`:
```ts
{
  child_module_id?: string,           // XOR with child_component_id
  child_component_id?: string,
  quantity: number,                   // > 0
  sort_order?: number,
  notes?: string | null
}
```

Responses:
- `201` `ProjectChildResponse` (hydrated with `child_module` summary OR `child_component` summary, plus supplier_stock_summary on component leaves).
- `404` `PROJECT_NOT_FOUND` / `INVALID_CHILD_REFERENCE`.
- `409` `CHILD_ALREADY_PRESENT` (duplicate edge).
- `422` XOR violation, validation errors.

### `PATCH /api/v1/projects/{project_id}/children/{child_id}`

Patch `quantity`, `sort_order`, `notes` of an existing edge. Cannot change which entity it points to.

Responses:
- `200` `ProjectChildResponse` (re-hydrated).
- `404` `PROJECT_NOT_FOUND` / child not found.

### `DELETE /api/v1/projects/{project_id}/children/{child_id}`

Remove an edge. The referenced module/component is NOT touched. Idempotent.

Responses: `204` / `404`.

### `GET /api/v1/projects/{project_id}/price-history`

Aggregated price time-series, mirror of `/modules/{id}/price-history`.

Query params:
- `period` `"week" | "month" | "year"` (default `"year"`).

Response 200: `ProjectPriceHistoryResponse`
```ts
{
  period: "week" | "month" | "year",
  points: [{ date: string, price: string }]   // price is Decimal as string (EUR)
}
```

### `GET /api/v1/projects/{project_id}/stock-events`

Paginated `stock_events` filtered by `project_id`, ordered by `occurred_at DESC`.

Query params:
- `page` (default 1), `page_size` (default 50, max 200).

Response 200: `PaginatedStockEvents` (same shape used by modules/components).

## Endpoints — Customers

### `GET /api/v1/customers`

List all customers. No pagination (small dataset until Holded sync ships).

Response 200: `CustomerResponse[]`.

### `POST /api/v1/customers`

Create a customer.

Request body: `CustomerCreateRequest`
```ts
{
  holded_id: string,        // required, case-insensitive unique
  name: string,             // required
  holded_url?: string | null,
  notas?: string | null
}
```

Responses:
- `201` `CustomerResponse`.
- `409` `CUSTOMER_HOLDED_ID_ALREADY_REGISTERED`.
- `422` validation errors.

### `GET /api/v1/customers/{customer_id}`

Responses: `200` `CustomerResponse` / `404` `CUSTOMER_NOT_FOUND`.

### `PATCH /api/v1/customers/{customer_id}`

Partial update. Body is `CustomerUpdateRequest`. All fields optional. Same 409 if `holded_id` collides.

### `DELETE /api/v1/customers/{customer_id}`

`204`. FK on `projects.customer_id` is `ON DELETE SET NULL` — dangling references self-clear.

## Endpoints — Cross-feature ("Usado en proyectos")

### `GET /api/v1/components/{component_id}/projects-using`

Projects that hold this component as a direct edge (`project_children.child_component_id = {component_id}`).

Response 200: `ProjectSummary[]` (hydrated with aggregates + customer summary).

`404` if the component itself doesn't exist.

### `GET /api/v1/modules/{module_id}/projects-using`

Same for modules. Direct edges only (no recursion into module ancestors).

Response 200: `ProjectSummary[]`. `404` if the module doesn't exist.

## Endpoint — Config

### `GET /api/v1/config`

Tiny config endpoint so the FE doesn't bake URLs.

Response 200:
```ts
{
  holded_base_url: string   // from app.core.settings.HOLDED_BASE_URL (default "https://app.holded.com")
}
```

`require_user`-protected. The FE caches this in TanStack Query with a long `staleTime`.

## Schemas

### `ProjectStatus`

`"Draft" | "Active" | "Delivered" | "Archived"`.

### `Customer`

```ts
{
  id: string,
  holded_id: string,
  name: string,
  holded_url: string | null,
  notas: string | null,
  created_at: string,
  updated_at: string
}
```

### `Project`

```ts
{
  id: string,
  code: string,
  name: string,
  description: string | null,
  status: ProjectStatus,
  customer_id: string | null,
  customer: Customer | null,            // hydrated server-side when present
  fecha_inicio: string | null,
  fecha_entrega_estimada: string | null,
  fecha_entrega_real: string | null,
  notas: string | null,
  created_at: string,
  updated_at: string
}
```

### `ProjectSummary`

`Project` + server-computed aggregates (same fields as `ModuleSummary`):

```ts
ProjectSummary = Project & {
  precio_total: string | null,          // Decimal as string (EUR)
  aggregated_nato_score: NatoScore | null,
  aggregated_tier: 1 | 2 | 3 | 4 | null,
  aggregated_expires_at: string | null,
  buildable_stock: number               // 0 when empty
}
```

### `ProjectChild`

```ts
{
  id: string,
  parent_project_id: string,
  child_module_id: string | null,       // XOR with child_component_id
  child_component_id: string | null,
  quantity: number,
  sort_order: number,
  notes: string | null,
  child_module: ModuleSummary | null,   // hydrated when child_module_id is set
  child_component: ComponentSummary | null   // hydrated when child_component_id is set
}
```

### `ProjectResponse`

`ProjectSummary` + `{ children: ProjectChild[] }`.

### `PaginatedProjects`

`{ items: ProjectSummary[], total, page, page_size }`.

### `AddProjectChildRequest`, `UpdateProjectChildRequest`

Same shape as the modules variants.

### `ProjectPriceHistoryResponse`

Same shape as `ModulePriceHistoryResponse`.

### `ConfigResponse`

`{ holded_base_url: string }`.

## Errors

Stable codes (RFC 7807 `type` URL ends with these slugs):

- `PROJECT_NOT_FOUND` (404).
- `PROJECT_CODE_ALREADY_REGISTERED` (409).
- `INVALID_CHILD_REFERENCE` (404) — referenced module/component doesn't exist.
- `CHILD_ALREADY_PRESENT` (409) — duplicate edge.
- `CUSTOMER_NOT_FOUND` (404).
- `CUSTOMER_HOLDED_ID_ALREADY_REGISTERED` (409).

All other validation errors stay as standard Pydantic 422 with field paths.
