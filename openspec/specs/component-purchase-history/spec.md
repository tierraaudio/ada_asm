# component-purchase-history Specification

## Purpose
TBD - created by archiving change component-management. Update Purpose after archive.
## Requirements
### Requirement: The system persists ComponentPurchase records linked to components

The system SHALL persist `ComponentPurchase` rows that capture one purchase event of one supplier at one date for one component. Required fields: `id (UUIDv4)`, `component_id (FK, ON DELETE CASCADE)`, `purchased_at (date)`, `quantity (integer > 0)`, `supplier`, `unit_cost (numeric)`, `total_cost (numeric)`, `currency (varchar(3), default 'EUR')`, `created_at`, `updated_at`. A composite index on `(component_id, purchased_at DESC)` MUST exist so the per-component history is paginated efficiently.

#### Scenario: Purchase rows are deleted when their component is deleted

- **WHEN** a component has 3 purchase rows
- **AND** the component is deleted via `DELETE /api/v1/components/{id}`
- **THEN** the `component_purchases` table has 3 fewer rows for that `component_id`

#### Scenario: Quantity must be strictly positive

- **WHEN** a `ComponentPurchase` insert is attempted with `quantity = 0` or a negative integer
- **THEN** the database rejects it (CHECK constraint)

### Requirement: Authenticated users can list a component's purchase history

The system SHALL expose `GET /api/v1/components/{id}/purchases` returning a paginated envelope `{ items, total, page, page_size }`. Items are ordered by `purchased_at DESC` (most recent first). The endpoint MUST require a valid access token. If the component does not exist the response is HTTP 404 with `code: "COMPONENT_NOT_FOUND"`. Pagination defaults: `page=1`, `page_size=25`, max `100`.

#### Scenario: Purchases are returned newest-first

- **WHEN** a component has purchase rows dated 2026-01-15, 2026-03-20, 2026-05-10
- **AND** an authenticated user GETs `/api/v1/components/{id}/purchases`
- **THEN** the response items appear in order 2026-05-10, 2026-03-20, 2026-01-15

#### Scenario: Empty history returns an empty page

- **WHEN** a component has zero purchases
- **AND** an authenticated user GETs `/api/v1/components/{id}/purchases`
- **THEN** the response is HTTP 200 with `items: []`, `total: 0`, `page: 1`, `page_size: 25`

#### Scenario: Unknown component returns 404

- **WHEN** an authenticated user GETs `/api/v1/components/<random-uuid>/purchases`
- **THEN** the response is HTTP 404 with `code: "COMPONENT_NOT_FOUND"`

#### Scenario: Page size cap applies

- **WHEN** the user requests `?page_size=500`
- **THEN** the response is HTTP 422 with `code: "VALIDATION_ERROR"`

### Requirement: Purchase rows carry monetary values with currency

Every purchase row SHALL carry a `currency` value (ISO 4217 three-letter code). The default at the database layer is `'EUR'`. `unit_cost` and `total_cost` are stored as `numeric` so no floating-point rounding occurs. The frontend MUST format displayed monetary values via a shared helper that uses the Spanish locale (`"€ 8,45"` with non-breaking space).

#### Scenario: Default currency on insert is EUR

- **WHEN** a purchase row is inserted without specifying a currency
- **THEN** the persisted row has `currency = "EUR"`

#### Scenario: Frontend always uses the shared euro formatter

- **WHEN** any UI surface (list page price column, detail page header, purchase-history table) displays a monetary value
- **THEN** the rendered string is produced by the shared `formatEuros` helper, not by `Number.prototype.toLocaleString` or `Intl.NumberFormat` calls scattered through components

### Requirement: The purchase history UI renders the table and the cost-trend chart

The frontend SHALL provide a page at `/components/{id}/purchases` (pixel-faithful to Figma `47:20273`) that renders, in this order, the shared component header card, a `recharts` `LineChart` of `unit_cost` over `purchased_at`, and a paginated table with columns `Fecha`, `Cantidad`, `Proveedor`, `Costo unitario`, `Costo total`. Tooltips on the chart show the full row (date, quantity, supplier, unit cost, total cost) on hover. The table page size is 25 with arrow-based pagination at the bottom.

#### Scenario: Empty purchase history shows an empty state

- **WHEN** a component has zero purchases
- **AND** the user opens `/components/{id}/purchases`
- **THEN** the chart area shows a "Aún no hay compras registradas" message instead of an empty chart
- **AND** the table renders a single empty-state row with the same copy

#### Scenario: Cost-trend chart receives the loaded purchase data

- **WHEN** the page loads a component with purchases
- **THEN** the rendered `LineChart` has one data point per purchase, with `x` = `purchased_at` and `y` = `unit_cost`
- **AND** hovering a point renders the tooltip with the date, quantity, supplier, unit cost and total cost of that row

