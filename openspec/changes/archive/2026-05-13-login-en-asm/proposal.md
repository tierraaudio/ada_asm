<!--
design-linked: true | scope: BE + FE
-->

## Design References

Figma file: `pMUgDI7rbRRzVWLCJhoVnY` (`ada_asm`).

Referenced Nodes:
- Login page — https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=37-2
- User menu pill in Header + Logout dropdown — https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=37-45

The implementation MUST be pixel-faithful to these frames at the `lg` breakpoint (1024+). Design tokens (colors, typography, radii, shadows) extracted from these frames are bound into Tailwind CSS variables — see design.md and tasks.md.

## Why

User Story 1 (`Login en ASM 1.0` from `docs/overview.md` and the Notion backlog) is the gate for every other feature: every Project / Module / Component endpoint will eventually require an authenticated user, and the per-project RBAC roadmap depends on the auth substrate landing first. The bootstrap skeleton has no users, no auth and no protected endpoints yet — we need the minimum viable login (email + password + recovery) with a token format that already supports per-project roles, so the future RBAC change is a pure data + middleware addition, not a re-architecture.

## What Changes

### Backend
- **`User` entity** persisted in `users` table: `id (uuid)`, `email (unique, citext)`, `password_hash (argon2id)`, `full_name`, `global_role ('admin' | 'user')`, `is_active`, `created_at`, `updated_at`.
- **`RefreshToken` entity** persisted in `refresh_tokens`: `id (uuid)`, `user_id`, `token_hash (argon2id of the secret)`, `expires_at`, `revoked_at (nullable)`, `created_at`, `created_from_ip (nullable)`, `user_agent (nullable)`.
- **`PasswordResetToken` entity** persisted in `password_reset_tokens`: `id (uuid)`, `user_id`, `token_hash`, `expires_at`, `used_at (nullable)`, `created_at`.
- **Alembic migration** introducing the three tables and necessary indexes.
- **Endpoints under `/api/v1/auth`**:
  - `POST /login` — email + password → access + refresh tokens.
  - `POST /refresh` — refresh token → new access (+ rotated refresh, old refresh revoked).
  - `POST /logout` — revoke the supplied refresh token.
  - `POST /password-recovery` — start password reset (always returns 202, never leaks whether email exists).
  - `POST /password-reset` — submit new password using the recovery token.
  - `GET /me` — returns the current user from the access token.
- **JWT format** with claims: `sub` (user id), `email`, `roles` (array — initially just `["user"]` or `["admin"]`), `project_scopes` (array — initially `["*"]`), `iat`, `exp`, `type` (`access` | `refresh`), `jti`. Signed HS256 with `JWT_SECRET`.
- **`require_user` FastAPI dependency** that validates JWT + loads the user. Decorated endpoints reject expired / revoked / malformed tokens with 401 in RFC 7807 format.
- **`require_role(...)` dependency** scaffold accepting a list of allowed roles — usable today via the `global_role`, ready to extend with per-project roles in a later US.
- **Outbound email** abstracted behind an `EmailSender` Protocol with two implementations: `ConsoleEmailSender` (default in dev — prints the reset link to the log) and a stub `SmtpEmailSender` (config-driven; not wired to a real SMTP in this change).
- **Rate limiting** on `/auth/login` and `/auth/password-recovery` (per-IP, in-memory token bucket — Redis-backed limiter scaffolded as a follow-up).
- **Seed command** `python -m app.scripts.seed_admin --email <e> --password <p>` for bootstrapping the first administrator on a fresh database.

### Frontend
- **Auth Zustand store** holding `accessToken`, `user`, `status` (`anonymous` | `authenticating` | `authenticated`). `accessToken` lives in memory only (refresh-token rotation is invisible to the SPA; the refresh token is short-lived and stored in `localStorage` with a documented trade-off — see design).
- **Axios interceptors** in `src/lib/api/client.ts`:
  - Request interceptor attaches `Authorization: Bearer <access>` when present.
  - Response interceptor catches 401, attempts a single refresh, retries the original request; on second failure, clears the store and routes to `/login`.
- **Login page** at `/login` — email + password form (react-hook-form + zod) with inline server-error mapping.
- **Password-recovery page** at `/forgot-password` and **password-reset page** at `/reset-password?token=...`.
- **Route guards**: a `RequireAuth` wrapper component used in `App.tsx`; visiting `/` while anonymous redirects to `/login`. After successful login the user lands on `/`.
- **`UserMenuPill` component in the Header** — the placeholder Header copy ("ADA ASM" plain text) is replaced by the design from Figma `37:45`: a notification bell with a status dot, plus a clickable pill with the user's avatar circle, full name and role, and a chevron-down. Clicking the pill opens a 256 px dropdown showing the user's name, email and role, with a "Cerrar sesión" / "Log out" action in destructive red.
- **Logout action** in the dropdown drops the access token, calls `POST /auth/logout` (best-effort), and redirects to `/login`.
- **TanStack Query** `useMe()` hook hits `GET /api/v1/auth/me` on app load to validate the in-memory token across hard refreshes (using a refresh-token round-trip on 401 before declaring the user anonymous).

### Design system seeds
- **Brand tokens added to `frontend/src/styles/globals.css`**: introduces CSS variables for the magenta brand color (`#e91e8c`), destructive red used in logout (`#dc2626`), the Inter / Menlo font stacks, and the shadow recipes pulled from Figma. These are wired into `tailwind.config.ts` so feature code references them as Tailwind utilities (e.g. `bg-brand`, `text-destructive`).
- **Self-hosted Inter and Menlo fonts** added under `frontend/public/fonts/` with an `@font-face` block in `globals.css` so the dev experience does not depend on a CDN font fetch and the login screen renders identically offline.

### Documentation / spec
- **`ai-specs/specs/api-spec.yml`** extended with the six auth endpoints.
- **`ai-specs/specs/data-model.md`** updated: `User`, `RefreshToken`, `PasswordResetToken` move from "not yet implemented" to documented with column-level schemas.
- **`ai-specs/specs/backend-standards.mdc`** — no change needed (already documents the auth strategy that this change implements).
- **`ai-specs/specs/frontend-standards.mdc`** — no change needed (the brand-token additions follow the standards' "Tailwind + CSS variables for design tokens" rule).

### Non-goals
- No per-project RBAC enforcement. The token shape supports it (`roles`, `project_scopes`) but no endpoint inspects per-project scopes yet — `Project` doesn't exist.
- No social / SSO login.
- No email-verification flow on signup. Admins create users via seed/admin endpoint; user-driven signup is a later US.
- No production SMTP wiring — `ConsoleEmailSender` is the only sender active by default. A real SMTP provider is wiring + config, deferred.
- No password complexity policy beyond a `min length = 12` rule. Strength scoring (zxcvbn etc.) is a follow-up.
- No MFA.
- No session listing / "log me out of all devices" UI (the data supports it; the surface lands later).

## Capabilities

### New Capabilities
- `user-account`: the `User` entity, password lifecycle (set, change, hash with Argon2id, recover via email, reset with token), `is_active` toggle, and the `global_role` field that authentication consumes. Includes seed-admin script.
- `authentication`: login (issue access + refresh), refresh (rotate refresh, mint new access), logout (revoke refresh), JWT validation dependency, `GET /me`, rate limiting on credential-handling endpoints.
- `frontend-auth-shell`: login (pixel-faithful to Figma `37:2`), password-recovery and password-reset pages; axios interceptors for token attachment + 401 refresh-and-retry; Zustand auth store; route guards; **`UserMenuPill` component in the Header (pixel-faithful to Figma `37:45`)** that hosts the avatar pill + dropdown + logout action.

### Modified Capabilities
- `runnable-skeleton`: the placeholder shell on `/` now lives behind a route guard (unauthenticated visit redirects to `/login`); the public health endpoint remains unauthenticated; OpenAPI now exposes the `/auth/*` surface.

## Impact

- **Code**: introduces `backend/app/domain/entities/{user,refresh_token,password_reset_token}.py`, `backend/app/infrastructure/db/models/`, `backend/app/infrastructure/security.py` (JWT + hashing), `backend/app/infrastructure/email/` (Protocol + console + SMTP stub), `backend/app/api/v1/routers/auth.py`, `backend/app/application/services/auth_service.py`, `backend/app/scripts/seed_admin.py`. Frontend introduces `src/features/auth/` (api, schemas, pages, store, hooks) and updates `src/App.tsx`, `src/main.tsx`, `src/lib/api/client.ts`.
- **Database**: three new tables, one Alembic migration. Adds `citext` extension to the baseline (`pgcrypto`, `ltree` already there).
- **Dependencies**: backend adds nothing new — `python-jose`, `passlib[argon2]`, `slowapi` (for rate limiting) are added via `pyproject.toml`. Frontend adds nothing new — all libs already pinned by the bootstrap.
- **Configuration / env**: new variables in `.env.example` (`JWT_ACCESS_TOKEN_TTL_SECONDS`, `JWT_REFRESH_TOKEN_TTL_SECONDS`, `PASSWORD_RESET_TOKEN_TTL_SECONDS`, `LOGIN_RATE_LIMIT_PER_MINUTE`, `SMTP_*` placeholders).
- **CI**: no workflow change — existing `backend.yml` and `frontend.yml` cover the new tests via the same gates.
- **Operations**: a fresh deploy now requires running `seed_admin` once to create the first administrator before anyone can log in. Documented in `development_guide.md`.
- **Risk**: this is the first PR where the spec for `runnable-skeleton` is `MODIFIED` (placeholder shell moves behind a guard) — exercising the openspec delta workflow end-to-end.
