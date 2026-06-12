## MODIFIED Requirements

### Requirement: Celery worker connects to the broker without errors

The system SHALL provide a Celery application factory in `app/infrastructure/celery_app.py` so that the `celery_worker` container starts, connects to Redis, registers the tasks declared in the `imports` config, and remains running. The previously-required `celery_beat` container is REMOVED from `docker-compose.yml` — periodic invocations now run in cloud via a KEDA-triggered Container App Job (see capability `cloud-infrastructure`). Local development triggers the daily sync manually via the new `make daily-sync` target, which invokes `python -m app.scripts.cron_run_daily_sync` inside the backend container.

#### Scenario: Celery worker stays running

- **WHEN** the `celery_worker` container is started
- **THEN** it reports `celery@... ready.` in its logs within 30 seconds
- **AND** the container remains in `running` state for at least 60 seconds
- **AND** the registered task list includes `supplier_sync.run_daily_sync` and `supplier_sync.sync_one_supplier`

#### Scenario: Local daily sync is invokable on demand

- **WHEN** a developer runs `make daily-sync` against a running local stack
- **THEN** the new entry-point script executes `run_daily_sync()` synchronously and exits 0 on success
- **AND** a new row appears in `supplier_sync_runs` for each enabled supplier

### Requirement: Local stack is reproducible via documented env contract

The repository SHALL provide an `.env.example` file at the project root that declares every environment variable referenced by `docker-compose.yml`, `backend/app/core/config.py`, and the frontend build. Each variable MUST have a non-secret default suitable for local development (or a clear placeholder like `change-me`). The file MUST NOT contain real secrets.

#### Scenario: Fresh clone can bring the stack up

- **WHEN** a developer runs `cp .env.example .env` and `docker compose up --build` on a fresh clone
- **THEN** all FIVE services (`postgres`, `redis`, `migrate`, `backend`, `celery_worker`, `frontend`) reach a healthy or completed state without further configuration
- **AND** the previously-required `celery_beat` service is NOT present in the compose file

#### Scenario: Every compose variable is documented

- **WHEN** `docker-compose.yml` references a variable via `${VAR}` or `${VAR:-default}`
- **THEN** `VAR` is also listed in `.env.example`

#### Scenario: No secrets in .env.example

- **WHEN** `.env.example` is inspected
- **THEN** all values are either non-secret defaults, ports, hostnames, or clearly marked placeholders (`change-me-in-env`, `replace-me`)
