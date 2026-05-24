# component-catalog Specification

## Purpose
TBD - created by archiving change component-management. Update Purpose after archive.
## Requirements
### Requirement: The system persists Components with a stable business key

The system SHALL persist `Component` records in a table whose canonical business key is the manufacturer part number (`mpn`). `mpn` MUST be unique and case-insensitive at the storage layer. Every component carries the catalogue metadata surfaced in the UI: SKU, name, family, description, datasheet URL, warehouse location, supplier, price per 100 units (decimal), current stock, tier (`A+|A|B|C|D`), NATO score (`100_otan|otan|allied_otan|neutral|high_risk|no_otan`), and country of origin (ISO 3166-1 alpha-2).

#### Scenario: Components persist with a unique MPN

- **WHEN** a component is created with `mpn = "STM32F407VGT6"`
- **AND** another create is attempted with `mpn = "stm32f407vgt6"` (different case)
- **THEN** the second create is rejected with HTTP 409 and code `MPN_ALREADY_REGISTERED`
- **AND** only one `components` row exists

#### Scenario: Tier and NATO score values are constrained

- **WHEN** a create is attempted with `tier = "Z"` (not one of the allowed values)
- **THEN** the request is rejected with HTTP 422 and code `VALIDATION_ERROR`
- **WHEN** a create is attempted with `nato_score = "made_up"`
- **THEN** the request is rejected with HTTP 422 and code `VALIDATION_ERROR`

#### Scenario: Stock cannot go negative

- **WHEN** a create or update sets `stock` to a negative integer
- **THEN** the request is rejected with HTTP 422 and code `VALIDATION_ERROR`

### Requirement: Authenticated users can list components with search, filters, and pagination

The system SHALL expose `GET /api/v1/components` returning a paginated envelope `{ items, total, page, page_size }`. The endpoint MUST accept the query parameters `q` (free text), `family`, `supplier`, `tier`, `nato_score`, `page` (default 1), `page_size` (default 25, max 100). The `q` parameter matches case-insensitively against `mpn`, `sku`, `name`, and `family` combined with `OR`. All filter parameters compose with `AND`. The endpoint MUST require a valid access token (`require_user`).

#### Scenario: Anonymous request is rejected

- **WHEN** `GET /api/v1/components` is called without an `Authorization` header
- **THEN** the response is HTTP 401 with code `UNAUTHENTICATED`

#### Scenario: Default pagination returns up to 25 items

- **WHEN** an authenticated user calls `GET /api/v1/components` against a database with 30 seeded components
- **THEN** the response is HTTP 200
- **AND** `items.length === 25`
- **AND** `total === 30`
- **AND** `page === 1`
- **AND** `page_size === 25`

#### Scenario: Search matches across all four indexed columns case-insensitively

- **WHEN** seeded components include `ACS712` (mpn), `BME280-Env` (sku), `Sensor corriente Hall` (name), `Microcontroladores` (family)
- **AND** the request is `GET /api/v1/components?q=micro`
- **THEN** the response includes the row whose `family` is `Microcontroladores`
- **WHEN** the request is `GET /api/v1/components?q=ACS`
- **THEN** the response includes the row whose `mpn` is `ACS712`
- **AND** the search is case-insensitive (`?q=acs` returns the same row)

#### Scenario: Filters compose with AND

- **WHEN** the request is `GET /api/v1/components?tier=A%2B&supplier=DigiKey`
- **THEN** only components whose `tier = "A+"` AND `supplier = "DigiKey"` are returned

#### Scenario: Page size cannot exceed 100

- **WHEN** the request is `GET /api/v1/components?page_size=500`
- **THEN** the response is HTTP 422 with code `VALIDATION_ERROR`

### Requirement: Authenticated users can create a component

The system SHALL expose `POST /api/v1/components` accepting a JSON body matching `ComponentCreate`. On success the response is HTTP 201 with the created `Component` body and an `id`, `created_at`, `updated_at` populated server-side. Duplicate `mpn` is rejected with HTTP 409 and code `MPN_ALREADY_REGISTERED`. Invalid payloads are rejected with HTTP 422.

#### Scenario: Successful create returns 201 + body

- **WHEN** an authenticated user POSTs `{ "mpn": "NE555", "name": "Timer NE555", "family": "Discretes", "tier": "C", "nato_score": "otan", "stock": 0 }`
- **THEN** the response is HTTP 201
- **AND** the body contains an `id` (UUIDv4), the submitted fields, `created_at`, `updated_at`, and `stock: 0`

#### Scenario: Duplicate MPN returns 409 with stable code

- **WHEN** a component with `mpn = "NE555"` exists and the user POSTs `{ "mpn": "NE555", ... }`
- **THEN** the response is HTTP 409 with `code: "MPN_ALREADY_REGISTERED"`

### Requirement: Authenticated users can fetch a single component

The system SHALL expose `GET /api/v1/components/{id}` returning the component or HTTP 404 with code `COMPONENT_NOT_FOUND` when the id does not resolve.

#### Scenario: Existing component returns 200 + body

- **WHEN** an authenticated user GETs `/api/v1/components/<existing-id>`
- **THEN** the response is HTTP 200 with the full component body

#### Scenario: Unknown id returns 404 with stable code

- **WHEN** an authenticated user GETs `/api/v1/components/00000000-0000-0000-0000-000000000000`
- **THEN** the response is HTTP 404 with `code: "COMPONENT_NOT_FOUND"`

### Requirement: Authenticated users can patch a component, but the business key is immutable

The system SHALL expose `PATCH /api/v1/components/{id}` accepting a partial body. The fields `id`, `mpn`, `created_at`, `updated_at` MUST be ignored when present in the request payload (silently accepted, not applied) — preventing accidental business-key drift without forcing the client to remove them. The response is HTTP 200 with the updated body.

#### Scenario: Partial update only mutates the provided fields

- **WHEN** an authenticated user PATCHes `/api/v1/components/<id>` with `{ "name": "Nuevo nombre", "stock": 42 }`
- **THEN** the response is HTTP 200
- **AND** the component's `name` is "Nuevo nombre" and `stock` is 42
- **AND** all other fields are unchanged

#### Scenario: MPN in the payload is ignored

- **WHEN** an authenticated user PATCHes `/api/v1/components/<id>` with `{ "mpn": "ANOTHER" }`
- **THEN** the response is HTTP 200
- **AND** the component's `mpn` is unchanged from its previous value

### Requirement: Authenticated users can delete a component idempotently

The system SHALL expose `DELETE /api/v1/components/{id}` returning HTTP 204. Deleting a non-existent id MUST still return 204 — the endpoint is idempotent. Deletion cascades to `component_purchases` via the database foreign key.

#### Scenario: Deleting an existing component succeeds

- **WHEN** an authenticated user DELETEs `/api/v1/components/<existing-id>`
- **THEN** the response is HTTP 204
- **AND** subsequent GETs to that id return HTTP 404

#### Scenario: Deleting an unknown id still returns 204

- **WHEN** an authenticated user DELETEs `/api/v1/components/<random-uuid>`
- **THEN** the response is HTTP 204 (no 404)

#### Scenario: Deletion cascades to purchases

- **WHEN** an authenticated user DELETEs a component that has 4 purchase rows
- **THEN** after deletion the `component_purchases` table has 4 fewer rows for that `component_id`

### Requirement: Components expose a placeholder upstream-sync endpoint

The system SHALL expose `POST /api/v1/components/{id}/sync` that returns HTTP 202 with the JSON body `{ "status": "queued" }` for every existing component. This is a placeholder for the future Holded / KiCAT integrations (USs 5, 6, 7); the endpoint MUST emit an info log line tagged `components.sync.placeholder` with the component id so we can observe usage. If the component does not exist the response is HTTP 404 with `code: "COMPONENT_NOT_FOUND"`.

#### Scenario: Sync of existing component returns 202

- **WHEN** an authenticated user POSTs `/api/v1/components/<existing-id>/sync`
- **THEN** the response is HTTP 202 with body `{ "status": "queued" }`
- **AND** the backend logs include a line tagged `components.sync.placeholder` with the component id

#### Scenario: Sync of unknown id returns 404

- **WHEN** an authenticated user POSTs `/api/v1/components/<random-uuid>/sync`
- **THEN** the response is HTTP 404 with `code: "COMPONENT_NOT_FOUND"`

### Requirement: Developers can seed sample components into a fresh database

The system SHALL provide a one-shot command `python -m app.scripts.seed_components` that, on an empty `components` table, inserts ~10 sample components matching the Figma copy (ACS712, B340A, BME280, ESP32-WROOM-32E, LM2596, NE555, MAX232, STM32F407VGT6, ATmega328P, and one with NATO score `no_otan` to exercise the "No OTAN" badge). Each seeded component also gets 3-6 `ComponentPurchase` rows spread across the last 12 months so the chart + history views render realistic data. Re-running the command when any component exists MUST exit non-zero and print a clear message, UNLESS `--reset` is passed (which truncates `component_purchases` then `components` first).

#### Scenario: Seeding an empty database succeeds

- **WHEN** the operator runs `python -m app.scripts.seed_components` against an empty `components` table
- **THEN** the command exits with code 0
- **AND** ten `Component` rows are persisted with the expected MPNs
- **AND** each component has at least three rows in `component_purchases`

#### Scenario: Re-seeding refuses by default

- **WHEN** at least one component already exists and the operator runs `python -m app.scripts.seed_components`
- **THEN** the command exits non-zero
- **AND** prints a message stating that components already exist and how to use `--reset`

#### Scenario: Re-seeding with --reset truncates first

- **WHEN** components and purchases already exist and the operator runs `python -m app.scripts.seed_components --reset`
- **THEN** existing rows are truncated and the sample set is re-inserted
- **AND** the command exits with code 0
