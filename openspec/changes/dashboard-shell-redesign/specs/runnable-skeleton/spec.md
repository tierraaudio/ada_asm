## MODIFIED Requirements

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
