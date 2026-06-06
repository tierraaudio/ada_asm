## ADDED Requirements

### Requirement: Components carry a last_supplier_sync_at column

The system SHALL add a nullable `last_supplier_sync_at timestamptz` column to the `components` table. The column is updated to the current timestamp every time the daily Celery sync (or an ad-hoc trigger) successfully upserts at least one `supplier_prices` or `supplier_stocks` row for that component. It remains NULL for components that have never been synced.

#### Scenario: New components start with NULL

- **WHEN** a component is created via `POST /api/v1/components`
- **THEN** the persisted row has `last_supplier_sync_at = NULL`

#### Scenario: A successful sync updates the timestamp

- **WHEN** the daily sync inserts a `supplier_prices` row for a component
- **THEN** the component's `last_supplier_sync_at` is set to the sync's wall-clock timestamp

### Requirement: supplier_prices rows preserve the original currency

The system SHALL add two nullable columns to `supplier_prices`: `price_original numeric(12,4)` and `currency_original varchar(3)` (ISO 4217). Adapters MUST populate both columns alongside `price_eur` so that re-conversion is possible if EUR rates are revised. Existing rows (pre-migration) are left with NULL values in the new columns.

#### Scenario: Mouser sync stores USD origin and EUR conversion

- **WHEN** Mouser returns a price of `5.00 USD` and the EUR/USD rate is `0.92`
- **THEN** the inserted `supplier_prices` row has `price_eur=4.60`, `price_original=5.00`, `currency_original="USD"`

#### Scenario: A row with no FX rate available stores original only

- **WHEN** the FX rate cache is empty and ECB is unreachable
- **THEN** the inserted `supplier_prices` row has `price_eur=NULL`, `price_original` and `currency_original` populated
- **AND** a `supplier_sync_errors` row with `error_code="FX_UNAVAILABLE"` is recorded
