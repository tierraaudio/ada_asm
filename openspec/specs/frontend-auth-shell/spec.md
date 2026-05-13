# frontend-auth-shell Specification

## Purpose
TBD - created by archiving change login-en-asm. Update Purpose after archive.
## Requirements
### Requirement: Anonymous visitors are redirected to the login page

The frontend SHALL gate every non-public route behind an authentication check. Visiting any non-public path while anonymous MUST redirect to `/login` with the original path captured for post-login redirect. The public routes are `/login`, `/forgot-password` and `/reset-password`.

#### Scenario: Anonymous visit to / redirects to /login

- **WHEN** an anonymous user opens `http://localhost:5173/` directly
- **THEN** the browser ends on `http://localhost:5173/login`
- **AND** the URL preserves a `?next=/` query parameter so successful login lands the user back on `/`

#### Scenario: Authenticated visit to / renders the dashboard shell

- **WHEN** the auth store is in state `authenticated`
- **AND** the user opens `/`
- **THEN** the placeholder shell renders (header, sidebar, "ADA ASM placeholder" content area)
- **AND** the URL stays at `/`

### Requirement: The login page authenticates against the backend and persists session

The frontend SHALL render a login form at `/login` with email + password fields validated client-side by zod via react-hook-form. Submitting valid credentials hits `POST /api/v1/auth/login`, stores the access token in memory (Zustand), stores the refresh token in `localStorage` under a documented key, populates the `user` slice from `GET /api/v1/auth/me`, and routes to `?next=...` or `/`. The visual layout MUST match Figma node `37:2` at the `lg` breakpoint: a 448 px centered card on a `#fafafa` page, with the "singularthings" brand wordmark (black + magenta) above an "ASM V2" heading and the subtitle "Ingresa tus credenciales para continuar"; the form card carries the email + password fields (each with a leading icon), a magenta "¿Olvidaste tu contraseña?" link aligned right, and a full-width magenta "Iniciar sesión" submit button; a divider precedes a "Usuarios de prueba" hint with a monospace credential chip.

#### Scenario: Successful login routes to the originally requested path

- **WHEN** the user submits valid credentials on `/login?next=/projects`
- **THEN** after the login succeeds, the browser navigates to `/projects`
- **AND** the auth store reports `status = "authenticated"` and a non-null `user`

#### Scenario: Server-side validation errors surface in the form

- **WHEN** the backend returns 401 `INVALID_CREDENTIALS`
- **THEN** the form displays an inline non-field error reading "Email or password is incorrect" (or the localised equivalent)
- **AND** no field-level error is shown (the message is intentionally non-discriminating)
- **AND** the password field is cleared

#### Scenario: Disabled submit while the request is in flight

- **WHEN** the user clicks "Log in"
- **THEN** the submit button is `disabled` and shows a pending indicator until the response returns
- **AND** the form cannot be re-submitted by Enter while the request is pending

#### Scenario: The "Usuarios de prueba" credentials chip is gated by environment

- **WHEN** the application is built with `VITE_ENV=development` and the user visits `/login`
- **THEN** the footer area of the login card renders the "Usuarios de prueba:" label and the monospace chip with the seeded admin credentials, matching Figma `37:2`
- **WHEN** the application is built with `VITE_ENV` set to anything other than `development` (e.g. `staging`, `production`) and the user visits `/login`
- **THEN** the "Usuarios de prueba" block is not rendered at all (no label, no chip, no divider above it)
- **AND** the rest of the card layout adjusts gracefully (the card is shorter; no empty space is left behind)

### Requirement: The axios client attaches the access token and refreshes on 401

The frontend's axios client SHALL:
- Attach `Authorization: Bearer <access_token>` to every outgoing request when an access token is in the Zustand store.
- On a 401 response, attempt a single `POST /api/v1/auth/refresh` using the persisted refresh token, then retry the original request once.
- If the refresh attempt also fails, clear the auth store and navigate to `/login?next=<current path>`.

#### Scenario: 401 triggers a single transparent refresh + retry

- **WHEN** the access token is expired and a request to `GET /api/v1/projects` returns 401 `ACCESS_TOKEN_EXPIRED`
- **AND** the persisted refresh token is still valid
- **THEN** the client calls `/api/v1/auth/refresh` once, updates the store with the new access token, retries the original request
- **AND** the calling code sees the eventual response (200 or whatever), never the intermediate 401

#### Scenario: Two consecutive 401s log the user out

- **WHEN** the second 401 fires after the refresh attempt also returned 401
- **THEN** the auth store is reset to `anonymous`
- **AND** the browser navigates to `/login?next=<current path>`
- **AND** no third request is attempted for that original call

#### Scenario: Public endpoints are not interfered with

- **WHEN** a request is made to `/api/v1/health` (which is unauthenticated)
- **AND** the auth store has no access token
- **THEN** the request goes out without an `Authorization` header
- **AND** the response (200) is returned untouched

### Requirement: The Header hosts a user menu pill matching the Figma design

The Header SHALL render a `UserMenuPill` component on the right side, pixel-faithful to Figma node `37:45` at the `lg` breakpoint. The pill consists of, in this order from left to right: a 36 px notification bell button with an 8 px red status dot at its top-right; a clickable pill (52 px tall) containing a 32 px magenta avatar circle with a person icon, two stacked text lines (`full_name` in 14 px medium `#1a1a1a`, then `Administrator` / `User` in 12 px medium `#6b6b6b`), and a 16 px chevron-down icon. The avatar circle MUST use the brand magenta token. The pill is keyboard reachable; activating it toggles the dropdown.

#### Scenario: Pill renders the authenticated user's identity

- **WHEN** the auth store status is `authenticated` and `user.full_name = "Admin User"`, `user.global_role = "admin"`
- **THEN** the Header renders a button labelled "Admin User" with the role text "Administrator"
- **AND** the avatar circle background uses the brand magenta CSS variable
- **AND** the bell button is visible

#### Scenario: Role text reflects the user's global_role

- **WHEN** the authenticated user has `global_role = "user"`
- **THEN** the secondary line of the pill displays "User" (capitalised) instead of "Administrator"

### Requirement: The user menu dropdown exposes the logout action

Clicking the pill SHALL open a 256 px dropdown anchored to the pill, pixel-faithful to Figma node `37:45`. The dropdown contains, from top to bottom: a header section with `full_name` (16 px medium), `email` (14 px regular `#6b6b6b`), and the role text (12 px regular `#6b6b6b`); a 1 px divider; a "Cerrar sesión" / "Log out" action in destructive red (`#dc2626`) with a leading 16 px icon. Clicking outside the dropdown or pressing `Escape` MUST close it. The dropdown MUST be keyboard navigable (Tab cycles into items, Enter activates).

#### Scenario: Clicking the pill opens the dropdown

- **WHEN** the user clicks the pill while it is closed
- **THEN** the dropdown is visible with the user's full name, email and role rendered as documented
- **AND** the dropdown's "Log out" action is focusable via Tab

#### Scenario: Pressing Escape closes the dropdown

- **WHEN** the dropdown is open and the user presses `Escape`
- **THEN** the dropdown is removed from the DOM (or hidden via CSS state)
- **AND** focus returns to the pill button

#### Scenario: Clicking outside the dropdown closes it

- **WHEN** the dropdown is open and the user clicks anywhere outside both the pill and the dropdown
- **THEN** the dropdown closes
- **AND** no logout request is dispatched

### Requirement: Logout clears local state and notifies the backend

The frontend SHALL expose a logout action inside the user-menu dropdown described above. Triggering it MUST: call `POST /api/v1/auth/logout` with the current refresh token (best-effort — failures are logged but do not block), clear the Zustand auth store, remove the refresh token from `localStorage`, and navigate to `/login`. The dropdown closes immediately on click; a brief loading indicator MAY be shown while the logout request is in flight.

#### Scenario: Logout clears all client-side auth state

- **WHEN** the user clicks "Cerrar sesión" / "Log out" in the dropdown
- **THEN** after the click, `localStorage` does not contain the refresh-token key
- **AND** the Zustand store is back to `{ accessToken: null, user: null, status: "anonymous" }`
- **AND** the browser is on `/login`

#### Scenario: Logout proceeds even if the backend call fails

- **WHEN** `POST /api/v1/auth/logout` returns a network error
- **THEN** the local state is still cleared and the user is still routed to `/login`
- **AND** a `console.warn` reports the backend failure

#### Scenario: Logout is reachable by keyboard

- **WHEN** the user opens the dropdown via Enter on the pill
- **AND** the user presses Tab until the "Log out" action is focused
- **AND** the user presses Enter
- **THEN** the logout flow runs exactly as if the action had been clicked

### Requirement: Password recovery and reset flows are reachable from the login page

The frontend SHALL provide a "Forgot password?" link on `/login` that routes to `/forgot-password`, a form that submits to `POST /api/v1/auth/password-recovery`, and a reset page at `/reset-password?token=...` that submits the new password to `POST /api/v1/auth/password-reset`.

#### Scenario: Password recovery shows a confirmation regardless of email existence

- **WHEN** the user submits any well-formed email on `/forgot-password`
- **THEN** the page shows a confirmation message ("If an account exists for that email, a reset link is on its way") regardless of whether the email is registered
- **AND** the message wording does not reveal account existence

#### Scenario: Reset page requires a token in the URL

- **WHEN** the user opens `/reset-password` with no `?token=` query
- **THEN** the page renders an error state telling the user the reset link is invalid or expired
- **AND** the form is not displayed

