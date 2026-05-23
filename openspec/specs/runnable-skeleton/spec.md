# runnable-skeleton Specification

## Purpose
TBD - created by archiving change bootstrap-runnable-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Backend service boots and exposes a health endpoint

The backend service SHALL boot as a FastAPI application and expose `GET /api/v1/health` returning HTTP 200 with a JSON body indicating service status, version and current UTC timestamp. The endpoint MUST NOT require authentication. The service MUST refuse to start if any required environment variable declared in `app/core/config.py` is missing.

#### Scenario: Successful boot exposes health endpoint

- **WHEN** the `backend` container is started with a valid `.env` file
- **THEN** `GET http://localhost:8000/api/v1/health` returns HTTP 200 within 20 seconds
- **AND** the response body contains `status: "ok"`, a `version` string, and a `timestamp` in ISO 8601 UTC format

#### Scenario: Missing required environment variable prevents boot

- **WHEN** the `backend` container is started without a required env var (e.g., `JWT_SECRET`)
- **THEN** the process exits with a non-zero code before binding to its port
- **AND** the logs contain the name of the missing variable

#### Scenario: Health endpoint is unauthenticated

- **WHEN** `GET /api/v1/health` is called with no Authorization header
- **THEN** the response is HTTP 200, not HTTP 401 or HTTP 403

### Requirement: Database baseline migration is applied automatically

The system SHALL provide an Alembic configuration with one baseline migration that enables required PostgreSQL extensions (`pgcrypto`, `ltree`). The migration MUST be reversible. The `migrate` service in `docker-compose.yml` MUST run `alembic upgrade head` to completion before the `backend` service starts.

#### Scenario: Baseline migration applies cleanly on a fresh database

- **WHEN** the stack is started against an empty PostgreSQL volume
- **THEN** the `migrate` service exits with code 0
- **AND** the `alembic_version` table is created and populated with the baseline revision
- **AND** the extensions `pgcrypto` and `ltree` are installed in the database

#### Scenario: Backend waits for migrations before starting

- **WHEN** `docker compose up` is executed
- **THEN** the `backend` service does not start until `migrate` exits successfully
- **AND** if `migrate` fails, `backend` is never started

#### Scenario: Baseline migration is reversible

- **WHEN** `alembic downgrade base` is executed against an upgraded database
- **THEN** the command exits with code 0
- **AND** the `alembic_version` table reports no applied revisions

### Requirement: Frontend serves a placeholder application shell

The frontend SHALL serve a Vite-built React + TypeScript application that renders a placeholder `DashboardLayout` (header, sidebar, content area) with no business content. The bundle MUST include Tailwind CSS, the shadcn/ui base components used by the layout, and routing wired through React Router. The placeholder route `/` MUST be protected — anonymous visitors are redirected to `/login` (see capability `frontend-auth-shell`). The public routes `/login`, `/forgot-password` and `/reset-password` MUST be reachable without authentication. The Header MUST host: (1) a sidebar toggle button on the left, (2) a notification bell + panel pair, and (3) a user menu pill. The Header's left toggle and the sidebar contract are defined in capability `dashboard-shell`; the notification bell + panel contract is defined in capability `in-app-notifications`; the user menu pill contract is defined in capability `frontend-auth-shell`. The placeholder "ADA ASM" plain-text header copy that was used during bootstrap is no longer rendered.

#### Scenario: Frontend container serves the application

- **WHEN** the `frontend` container is healthy
- **THEN** `GET http://localhost:5173/` returns HTTP 200 with `text/html`
- **AND** the response includes either the placeholder `DashboardLayout` markup (when authenticated client-side) OR the login page markup (when anonymous client-side)

#### Scenario: Health endpoint of the static server

- **WHEN** `GET http://localhost:5173/healthz` is called
- **THEN** the response is HTTP 200 with body `ok`

#### Scenario: Frontend uses configured API base URL at build time

- **WHEN** the frontend image is built with `VITE_API_URL=http://example:9000`
- **THEN** the bundled JavaScript contains `http://example:9000` as the resolved base URL for API calls

#### Scenario: Anonymous visit to / lands on login

- **WHEN** the user opens `http://localhost:5173/` in an incognito window (no prior session)
- **THEN** the browser ends on `http://localhost:5173/login` with `?next=/`
- **AND** the response is HTTP 200 with the login form markup

#### Scenario: Authenticated dashboard renders the sidebar toggle, bell and user pill in the header

- **WHEN** an authenticated user opens `/`
- **THEN** the Header renders the sidebar toggle on the left (per `dashboard-shell`), the notification bell + panel trigger (per `in-app-notifications`), and the `UserMenuPill` on the right (per `frontend-auth-shell`)
- **AND** the placeholder plain-text "ADA ASM" header copy is not rendered anywhere

### Requirement: Celery worker and beat connect to the broker without errors

The system SHALL provide a Celery application factory in `app/infrastructure/celery_app.py` so that the `celery_worker` and `celery_beat` containers start, connect to Redis, and remain running. No business tasks are registered in this change; both containers MUST run with an empty task registry without crashing.

#### Scenario: Celery worker stays running

- **WHEN** the `celery_worker` container is started
- **THEN** it reports `celery@... ready.` in its logs within 30 seconds
- **AND** the container remains in `running` state for at least 60 seconds

#### Scenario: Celery beat stays running

- **WHEN** the `celery_beat` container is started
- **THEN** it reports `beat: Starting...` in its logs within 30 seconds
- **AND** the container remains in `running` state for at least 60 seconds

### Requirement: Local stack is reproducible via documented env contract

The repository SHALL provide an `.env.example` file at the project root that declares every environment variable referenced by `docker-compose.yml`, `backend/app/core/config.py` and the frontend build. Each variable MUST have a non-secret default suitable for local development (or a clear placeholder like `change-me`). The file MUST NOT contain real secrets.

#### Scenario: Fresh clone can bring the stack up

- **WHEN** a developer runs `cp .env.example .env` and `docker compose up --build` on a fresh clone
- **THEN** all six services (`postgres`, `redis`, `migrate`, `backend`, `celery_worker`, `celery_beat`, `frontend`) reach a healthy or completed state without further configuration

#### Scenario: Every compose variable is documented

- **WHEN** `docker-compose.yml` references a variable via `${VAR}` or `${VAR:-default}`
- **THEN** `VAR` is also listed in `.env.example`

#### Scenario: No secrets in .env.example

- **WHEN** `.env.example` is inspected
- **THEN** all values are either non-secret defaults, ports, hostnames, or clearly marked placeholders (`change-me-in-env`, `replace-me`)

### Requirement: Developer onboarding documentation enables a new developer to run the stack

The system SHALL provide a `development_guide.md` under `ai-specs/specs/` that documents, in this order: prerequisites (Docker, Make/pnpm/uv as relevant), clone instructions, env setup, the canonical `docker compose up` flow, the URLs to verify each service, and the path for the next step (the first user story). A developer following the guide on a fresh machine MUST be able to reach `/api/v1/health` returning 200 without consulting other documents.

#### Scenario: Onboarding guide covers the bootable flow end-to-end

- **WHEN** a developer reads `ai-specs/specs/development_guide.md` top to bottom
- **THEN** every command needed to reach a green health check is present and ordered
- **AND** the document references `.env.example`, `docker-compose.yml`, and both standards files

### Requirement: Data-model document lists the planned entity catalogue

The system SHALL provide a `data-model.md` under `ai-specs/specs/` that lists the entities planned by the project overview (`User`, `Project`, `Module`, `Component`, `PriceSnapshot`, `RefreshToken`) and, for each, a one-paragraph description and the User Story that will introduce its table definition. This change MUST NOT define column-level schemas — those belong to the introducing User Story.

#### Scenario: Each entity is referenced with a forward link

- **WHEN** `ai-specs/specs/data-model.md` is read
- **THEN** every entity in the planned catalogue has its own heading, a description, and a "Introduced by:" pointer to a future User Story or `TBD`
