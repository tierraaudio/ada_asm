## ADDED Requirements

### Requirement: The system persists per-run sync telemetry in supplier_sync_runs

The system SHALL create a `supplier_sync_runs` table with: `id` UUIDv4 PK, `supplier` varchar(32) NOT NULL CHECK in `('mouser','digikey','tme','farnell','rs')`, `started_at` timestamptz NOT NULL, `finished_at` timestamptz nullable, `components_processed` integer NOT NULL DEFAULT 0, `components_updated` integer NOT NULL DEFAULT 0, `errors_count` integer NOT NULL DEFAULT 0, `status` varchar(16) NOT NULL CHECK in `('running','success','partial','failed')` DEFAULT `'running'`, `error_summary` text nullable, `created_at` timestamptz NOT NULL DEFAULT `now()`. Migration MUST be reversible.

#### Scenario: Migration creates the table with constraints

- **WHEN** Alembic applies the migration
- **THEN** the `supplier_sync_runs` table exists with all listed columns and CHECK constraints
- **AND** `alembic downgrade -1` removes the table cleanly

### Requirement: The system persists per-component sync failures in supplier_sync_errors

The system SHALL create a `supplier_sync_errors` table with: `id` UUIDv4 PK, `run_id` UUIDv4 NOT NULL FK → `supplier_sync_runs.id` ON DELETE CASCADE, `component_id` UUIDv4 NOT NULL FK → `components.id` ON DELETE CASCADE, `supplier` varchar(32) NOT NULL, `error_code` varchar(64) NOT NULL (one of `RATE_LIMITED|NOT_FOUND|HTTP_5XX|PARSE_ERROR|AUTH_FAILED|FX_UNAVAILABLE|TIMEOUT|UNKNOWN`), `error_message` text NOT NULL, `occurred_at` timestamptz NOT NULL.

#### Scenario: Sub-task records a typed error row

- **WHEN** `sync_supplier_chunk` calls `fetch_by_mpn` and the supplier returns HTTP 500
- **THEN** a `supplier_sync_errors` row is inserted with `error_code="HTTP_5XX"` and a non-empty `error_message`
- **AND** the run's `errors_count` is incremented

### Requirement: The daily sync runs via Celery Beat at the configured UTC hour

The system SHALL register a Celery Beat entry `supplier-sync-daily` in `celery_app.beat_schedule` pointing to `app.infrastructure.tasks.supplier_sync.run_daily_sync` with cron `0 ${SUPPLIER_SYNC_DAILY_HOUR_UTC} * * *`. `run_daily_sync` SHALL, for each enabled supplier: create a `supplier_sync_runs` row with `status='running'`, partition the component IDs into chunks of 50, dispatch `sync_supplier_chunk(supplier, component_ids, run_id)` per chunk, and use a Celery `chord` to update the run row's `finished_at`, `components_updated`, `errors_count`, and `status` when all sub-tasks complete.

#### Scenario: Daily job creates one run row per enabled supplier

- **WHEN** `run_daily_sync` is invoked with `SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser,digikey"`
- **THEN** two new `supplier_sync_runs` rows are inserted (one per supplier) with `status='running'`

#### Scenario: Run finalises with status='partial' when some sub-tasks error

- **WHEN** the sync iterates 100 components and 3 fail with HTTP 5xx but 97 succeed
- **THEN** the run row finalises with `status='partial'`, `components_processed=100`, `components_updated=97`, `errors_count=3`

#### Scenario: Run finalises with status='success' when all sub-tasks succeed

- **WHEN** the sync iterates 100 components and all succeed
- **THEN** the run row finalises with `status='success'`, `errors_count=0`

### Requirement: Sub-tasks upsert append-only history rows

For each component the system SHALL call the adapter's `fetch_by_mpn` and, on a non-`None` result, INSERT a new `supplier_prices` row (one per price break) AND a new `supplier_stocks` row (current stock snapshot) without UPDATEing any prior row. The component's `last_supplier_sync_at` SHALL be set to the current timestamp on every successful upsert.

#### Scenario: A successful sync appends a new history snapshot

- **WHEN** the sync hits a component with three existing `supplier_prices` rows for Mouser
- **AND** the adapter returns a new quote with two price breaks
- **THEN** two new `supplier_prices` rows are inserted (total 5)
- **AND** one new `supplier_stocks` row is inserted
- **AND** `components.last_supplier_sync_at` is updated for that row

#### Scenario: A None response does NOT touch existing history

- **WHEN** the sync hits a component and the adapter returns `None`
- **THEN** no `supplier_prices` row is inserted for that component
- **AND** no `supplier_stocks` row is inserted
- **AND** `components.last_supplier_sync_at` is NOT updated

### Requirement: Authenticated users can list recent supplier sync runs

The system SHALL expose `GET /api/v1/supplier-sync/runs?limit=N&supplier=<code>` (auth `require_user`) returning the most recent run rows ordered by `started_at DESC`. Default `limit=50`, max `limit=200`. Optional `supplier` filter restricts to one of the five codes. Each item carries the full row payload.

#### Scenario: Listing returns runs in reverse chronological order

- **WHEN** an authenticated user GETs `/api/v1/supplier-sync/runs?limit=5`
- **THEN** the response is HTTP 200 with up to 5 items ordered by `started_at DESC`

#### Scenario: Filter by supplier narrows results

- **WHEN** runs exist for Mouser and DigiKey and the user GETs `?supplier=mouser`
- **THEN** the response contains only Mouser rows

### Requirement: Authenticated users can list per-run errors

The system SHALL expose `GET /api/v1/supplier-sync/runs/{id}/errors?limit=N` (auth `require_user`) returning the `supplier_sync_errors` rows for that run, ordered by `occurred_at DESC`. Default `limit=200`, max `limit=1000`. 404 RFC-7807 with `code="SUPPLIER_SYNC_RUN_NOT_FOUND"` when the run does not exist.

#### Scenario: Returns errors for a known run

- **WHEN** a run has 12 errors and the user GETs `/api/v1/supplier-sync/runs/{id}/errors`
- **THEN** the response is HTTP 200 with 12 items

#### Scenario: Returns 404 for an unknown run id

- **WHEN** the user GETs `/api/v1/supplier-sync/runs/<random-uuid>/errors`
- **THEN** the response is HTTP 404 with `code="SUPPLIER_SYNC_RUN_NOT_FOUND"`

### Requirement: Operators can trigger an ad-hoc sync for a single supplier

The system SHALL expose `POST /api/v1/supplier-sync/runs?supplier=<code>` (auth `require_user`) that enqueues `run_daily_sync` restricted to one supplier and returns HTTP 202 with `{"run_id": "<uuid>"}` immediately (the task runs asynchronously). 422 RFC-7807 with `code="SUPPLIER_NOT_ENABLED"` when the supplier is not in `SUPPLIER_SYNC_ENABLED_SUPPLIERS` or has no configured credentials.

#### Scenario: Ad-hoc trigger returns a run_id immediately

- **WHEN** an authenticated user POSTs `/api/v1/supplier-sync/runs?supplier=mouser`
- **AND** Mouser is enabled and configured
- **THEN** the response is HTTP 202 with `{"run_id": "<uuid>"}`
- **AND** a new `supplier_sync_runs` row exists with `status='running'`

#### Scenario: Ad-hoc trigger for a disabled supplier returns 422

- **WHEN** the user POSTs `?supplier=rs` and RS is not in `SUPPLIER_SYNC_ENABLED_SUPPLIERS`
- **THEN** the response is HTTP 422 with `code="SUPPLIER_NOT_ENABLED"`
