## ADDED Requirements

### Requirement: Authenticated users can ingest a component from a manufacturer MPN

The system SHALL expose `POST /api/v1/components/ingest` (protected by `require_user`, RFC 7807 errors) that accepts a body `{mpn: string, ubicacion?: string, stock_inicial?: int, holded_id?: string, force?: bool}`. The endpoint SHALL walk the enabled suppliers for the given MPN, blend the results, infer the internal family, attempt datasheet archival, persist a new `Component` with every field the suppliers could fill plus the optional manual fields, and return the created component (HTTP 201) including which fields were populated and which suppliers contributed. The MPN is the manufacturer part number (the natural business key); the internal `sku` SHALL be auto-generated, never supplied by the caller.

#### Scenario: Ingesting a known MPN creates a fully populated component

- **WHEN** an authenticated user POSTs `{"mpn": "NE555P"}` and at least one supplier returns data
- **THEN** the response is HTTP 201 with the created component
- **AND** `name`, `description`, `manufacturer`, `package`, `family`, `stock` (per-supplier), and price breaks are populated from the suppliers
- **AND** `sources_succeeded` lists the suppliers that contributed
- **AND** the component is persisted and retrievable via `GET /api/v1/components/{id}`

#### Scenario: Optional manual fields are applied

- **WHEN** the body includes `{"mpn": "NE555P", "ubicacion": "G-T-23", "stock_inicial": 500, "holded_id": "HLD-NE555"}`
- **THEN** the created component has `location="G-T-23"`, `stock=500`, `holded_id="HLD-NE555"`
- **AND** these override any supplier-derived defaults for those fields

#### Scenario: Unknown MPN returns 404

- **WHEN** an authenticated user POSTs an MPN that no enabled supplier recognises
- **THEN** the response is HTTP 404 with code `COMPONENT_MPN_NOT_FOUND`
- **AND** no component is created

#### Scenario: Duplicate MPN is rejected unless forced

- **WHEN** a component with the same MPN (case-insensitive) already exists and `force` is absent or false
- **THEN** the response is HTTP 409 with code `MPN_ALREADY_REGISTERED`

#### Scenario: All suppliers unreachable returns 502

- **WHEN** every enabled supplier raises a transport error for the MPN
- **THEN** the response is HTTP 502 with code `SUPPLIER_LOOKUP_UNAVAILABLE`
- **AND** no component is created

#### Scenario: Unauthenticated request is rejected

- **WHEN** the request carries no valid bearer token
- **THEN** the response is HTTP 401

### Requirement: The ingestion response includes a structured ingestion report

The system SHALL return, alongside the created component, a structured `report` object summarizing the ingestion outcome so a future frontend can render a results view without re-deriving anything. The report SHALL include: overall `status` (`ok` | `ok_with_warnings`), the input `mpn` and generated `sku`, `sources_consulted` / `sources_succeeded` / `sources_contributed` (suppliers whose data actually landed on the component), a `family` block (inferred value or null, `needs_review`, `decided_by` supplier, `match_type`, `raw_category`, `confidence`), a `datasheet` block (`outcome` ∈ {`archived`, `link_only`, `none`}, `source`, `url`, `blob_path` when archived, `size_bytes`), `fields_populated` / `fields_missing` lists, `counts` (price_breaks, supplier_stock_rows, parameters, compliance_codes, cross_refs, documents), `manual_overrides_applied`, and a `warnings[]` list (e.g. a supplier errored, a datasheet host needed headless and was stored link-only, RS disabled). The report SHALL be present on every successful ingestion (HTTP 201), not only on warnings.

#### Scenario: Successful ingestion returns a populated report

- **WHEN** a component is ingested successfully from `NE555P`
- **THEN** the response body contains both the created `component` and a `report`
- **AND** `report.status` is `ok` or `ok_with_warnings`
- **AND** `report.family` states the inferred family, the deciding supplier and match type (or `needs_review=true`)
- **AND** `report.datasheet.outcome` is one of `archived` / `link_only` / `none` with its source
- **AND** `report.sources_contributed` lists the suppliers whose data landed on the component
- **AND** `report.counts` reports how many price breaks, parameters, compliance codes, cross-refs and documents were stored

#### Scenario: Partial-success warnings are surfaced in the report

- **WHEN** a component is ingested but one supplier errored and the datasheet could only be stored as a link
- **THEN** `report.status` is `ok_with_warnings`
- **AND** `report.warnings` describes the supplier error and the link-only datasheet outcome
- **AND** the component is still created (HTTP 201)

#### Scenario: The report mirrors what was actually stored

- **WHEN** the report lists a field in `fields_populated` or a non-zero `counts` value
- **THEN** the corresponding data is present on the persisted component (the report never claims more than was stored)

### Requirement: The internal SKU is auto-generated from the inferred family

The system SHALL generate `Component.sku` as `<family-prefix>-<zero-padded-sequence>` where the prefix is derived from the inferred family (e.g. `DIO` for Diodos, `TRN` for Transistores, `MCU` for Microcontroladores), matching the convention used by the seed script. When the family could not be inferred, the system SHALL use a generic prefix (e.g. `CMP`). The generated SKU SHALL be unique.

#### Scenario: SKU prefix follows the inferred family

- **WHEN** a component is ingested and its family is inferred as `Diodos`
- **THEN** the generated `sku` starts with `DIO-`

#### Scenario: Generic prefix when family is unknown

- **WHEN** a component is ingested and no family could be inferred
- **THEN** the generated `sku` starts with the generic prefix
- **AND** `family` is empty and the component is flagged for review

### Requirement: Ingestion is invokable as a CLI for local and prod one-off runs

The system SHALL provide `python -m app.scripts.ingest_component <MPN> [--ubicacion ...] [--stock-inicial ...] [--holded-id ...] [--force]` that calls the same application service as the HTTP endpoint. It SHALL be runnable locally via `docker exec` and in production as a one-off Container App Job. The script SHALL exit 0 on success printing the created component id, and non-zero on failure printing a typed error.

#### Scenario: CLI ingests a component locally

- **WHEN** `python -m app.scripts.ingest_component NE555P` runs against a running stack with supplier credentials
- **THEN** the script exits 0 and prints the created component id
- **AND** the component exists in the database

#### Scenario: CLI surfaces a typed error on failure

- **WHEN** the CLI is invoked with an MPN that already exists and `--force` is absent
- **THEN** the script exits non-zero printing `MPN_ALREADY_REGISTERED`

### Requirement: Ingested components are registered for the daily supplier sync

The system SHALL persist the ingested component such that the existing daily supplier-sync cron picks it up and accumulates `supplier_prices` and `supplier_stocks` history from the next scheduled run, without any additional registration step.

#### Scenario: A freshly ingested component is synced the next night

- **WHEN** a component is ingested and the daily sync runs afterwards
- **THEN** the sync processes the new component (it appears in `components_processed`)
- **AND** new `supplier_prices` / `supplier_stocks` rows are written for it
