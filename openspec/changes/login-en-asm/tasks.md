## 1. Backend: dependencies and config

- [ ] 1.1 Add `slowapi>=0.1.9,<1.0` to `backend/pyproject.toml` runtime deps. Run `uv lock` and commit `uv.lock`.
- [ ] 1.2 Extend `app/core/config.py` with: `jwt_access_token_ttl_seconds` (default 900), `jwt_refresh_token_ttl_seconds` (default 14*86400), `password_reset_token_ttl_seconds` (default 3600), `login_rate_limit_per_minute` (default 10), `frontend_base_url` (required string, used to build reset links), `smtp_host` / `smtp_port` / `smtp_username` / `smtp_password` / `smtp_from` (all optional, used only by `SmtpEmailSender`).
- [ ] 1.3 Update `.env.example` with the new variables. Sensible local defaults / `change-me` placeholders.

## 2. Backend: domain entities

- [ ] 2.1 Create `app/domain/entities/user.py`: `User` dataclass with `id (UUID)`, `email`, `password_hash`, `full_name`, `global_role` (Literal `'admin' | 'user'`), `is_active`, `created_at`, `updated_at`. Class method `verify_password(plaintext) -> bool` that delegates to `passlib`.
- [ ] 2.2 Create `app/domain/entities/refresh_token.py`: `RefreshToken` dataclass with `id`, `user_id`, `jti_hash`, `expires_at`, `revoked_at`, `created_at`, `created_from_ip`, `user_agent`.
- [ ] 2.3 Create `app/domain/entities/password_reset_token.py`: `PasswordResetToken` dataclass with `id`, `user_id`, `token_hash`, `expires_at`, `used_at`, `created_at`.
- [ ] 2.4 Create `app/domain/repositories/user_repository.py`: Protocol with `get_by_email`, `get_by_id`, `save`, `update_password`, `list_admins`.
- [ ] 2.5 Create `app/domain/repositories/refresh_token_repository.py`: Protocol with `get_by_jti_hash`, `save`, `revoke`, `revoke_all_for_user`.
- [ ] 2.6 Create `app/domain/repositories/password_reset_token_repository.py`: Protocol with `get_unused_by_token_hash`, `save`, `mark_used`.

## 3. Backend: database models + migration

- [ ] 3.1 Add `app/infrastructure/db/base.py` with `DeclarativeBase` and the `created_at` / `updated_at` mixin.
- [ ] 3.2 Add `app/infrastructure/db/session.py` with `async_engine` + `async_session_factory` reading `DATABASE_URL` from settings.
- [ ] 3.3 Add `app/infrastructure/db/models/user.py`, `refresh_token.py`, `password_reset_token.py` (SQLAlchemy 2 `Mapped[...]` declarations matching the entity fields).
- [ ] 3.4 Wire `target_metadata = Base.metadata` in `backend/migrations/env.py`.
- [ ] 3.5 Generate Alembic migration `<timestamp>_login_en_asm__users_refresh_reset.py` whose `upgrade()` (a) enables `citext`, (b) creates `users`, `refresh_tokens`, `password_reset_tokens` with all indexes and FK constraints. Verify autogenerate output, hand-edit the column types (UUID via `gen_random_uuid()`, email via `citext`). `downgrade()` drops the three tables in reverse FK order and disables `citext`.
- [ ] 3.6 Run the migration locally against the dockerised postgres: `uv run alembic upgrade head` then `uv run alembic downgrade -1` then `upgrade head` again — all exit 0.

## 4. Backend: security primitives

- [ ] 4.1 Create `app/infrastructure/security.py`: `hash_password`, `verify_password` (Argon2id via passlib); `sha256_hex(s)` helper for `jti` hashing; `argon2_hash`, `argon2_verify` helpers for password-reset tokens.
- [ ] 4.2 Create `app/infrastructure/jwt.py`: `mint_access_token(user)`, `mint_refresh_token(user)`, `decode_token(raw)`. Use `python-jose`. Encode `roles`, `project_scopes`, `type`, `jti` claims.
- [ ] 4.3 Unit-test the JWT roundtrip: mint → decode → claims match; expired token raises; wrong-type token raises.

## 5. Backend: repository implementations

- [ ] 5.1 Implement `app/infrastructure/repositories/user_repository.py` against `AsyncSession` + the SQLAlchemy model. Translate between ORM models and domain entities — domain layer must NOT import SQLAlchemy.
- [ ] 5.2 Implement `app/infrastructure/repositories/refresh_token_repository.py` with: `save`, `get_by_jti_hash`, `revoke (single)`, `revoke_all_for_user`.
- [ ] 5.3 Implement `app/infrastructure/repositories/password_reset_token_repository.py` with: `save`, `get_unused_by_token_hash`, `mark_used`.

## 6. Backend: email sender

- [ ] 6.1 Create `app/infrastructure/email/sender.py`: `EmailSender` Protocol.
- [ ] 6.2 Create `app/infrastructure/email/console.py`: `ConsoleEmailSender` that emits a structured log line tagged `email.console.delivery` with `dev_only=true`.
- [ ] 6.3 Create `app/infrastructure/email/smtp.py`: `SmtpEmailSender` that opens `aiosmtplib` (add to deps if needed) only when `smtp_host` is set; raises a clear `EmailNotConfiguredError` otherwise. Stub but importable.
- [ ] 6.4 Factory in `app/infrastructure/email/__init__.py`: `get_email_sender()` returns SMTP if configured, else Console.

## 7. Backend: application services

- [ ] 7.1 Create `app/application/services/auth_service.py` with:
  - `login(email, password) -> (access, refresh)` — raises `InvalidCredentialsError` on any failure path.
  - `refresh(refresh_token_raw) -> (access, refresh)` — validates + rotates atomically.
  - `logout(refresh_token_raw) -> None` — idempotent revoke.
  - `request_password_recovery(email) -> None` — always succeeds publicly.
  - `reset_password(token, new_password) -> None` — also revokes all the user's refresh tokens.
  - `get_current_user(access_token_raw) -> User` — used by the dependency.
- [ ] 7.2 Unit-test each service path with mocked repositories — happy + every documented error.

## 8. Backend: HTTP layer

- [ ] 8.1 Create `app/api/v1/dependencies.py` with `get_db_session`, `get_user_repository`, `get_refresh_token_repository`, `get_password_reset_token_repository`, `get_email_sender`, `get_auth_service`, `require_user`, `require_role(roles: list[str])`.
- [ ] 8.2 Create Pydantic schemas in `app/api/v1/schemas/auth.py`: `LoginRequest`, `LoginResponse`, `RefreshRequest`, `LogoutRequest`, `PasswordRecoveryRequest`, `PasswordResetRequest`, `MeResponse`.
- [ ] 8.3 Create `app/api/v1/routers/auth.py` with the six endpoints. Apply slowapi limits to `/login` and `/password-recovery`. Map application exceptions to RFC 7807 responses with stable `code` strings.
- [ ] 8.4 Mount the auth router into `api_v1_router` inside `app/api/v1/__init__.py`.
- [ ] 8.5 Add a global exception handler in `app/api/errors.py` mapping `InvalidCredentialsError`, `RefreshTokenRevokedError`, `RefreshTokenExpiredError`, `AccessTokenExpiredError`, `AccessTokenWrongTypeError`, `ResetTokenAlreadyUsedError`, `ResetTokenExpiredError`, `EmailAlreadyRegisteredError`, `PasswordTooShortError`, `RateLimitExceededError` to their HTTP codes. Wire it from `create_app()`.

## 9. Backend: seed-admin script

- [ ] 9.1 Create `app/scripts/__init__.py` and `app/scripts/seed_admin.py`. Parse args with `argparse`. Opens an async DB session, checks for existing admin, creates the user if none, prints success or refusal. Non-zero exit on refusal.

## 10. Backend: tests

- [ ] 10.1 Integration test for login: seed user via repository in fixture, hit `POST /api/v1/auth/login` with `httpx.AsyncClient`, assert 200 + tokens are valid JWTs + refresh row exists in DB.
- [ ] 10.2 Integration tests for refresh: happy path rotates pair; replay of revoked token logs WARNING + 401.
- [ ] 10.3 Integration test for logout: returns 204; subsequent refresh fails 401; replay returns 204.
- [ ] 10.4 Integration tests for password recovery: registered email → 202 + token row + sender called once; unknown email → 202 + no row + sender not called; response bodies byte-identical.
- [ ] 10.5 Integration test for password reset: valid token resets password + revokes all refresh tokens of the user; used token returns 400; expired token returns 400.
- [ ] 10.6 Integration tests for `GET /me`: 200 with user; 401 without header; 401 with refresh token used as access; 401 with expired access.
- [ ] 10.7 Integration test for rate limiting: 11 logins from same IP → 11th gets 429 with `Retry-After`.
- [ ] 10.8 Unit tests for `auth_service` happy + every error path (mocked repos).
- [ ] 10.9 Unit test for `seed_admin` happy + refusal-on-existing-admin (uses Testcontainers postgres or the dockerised one).
- [ ] 10.10 Run `uv run pytest --cov=app --cov-fail-under=80` locally and confirm green.

## 11. Frontend: dependencies, structure, design tokens

- [ ] 11.1 Verify all libs already in `frontend/package.json` (react-hook-form, zod, @hookform/resolvers, zustand, @tanstack/react-query, axios). Add `@radix-ui/react-dropdown-menu` and `@radix-ui/react-popover` (for accessible dropdown primitive) — these are part of the shadcn/ui pattern documented in `frontend-standards.mdc`. Run `pnpm install` and commit the lockfile.
- [ ] 11.2 Create directory tree under `frontend/src/features/auth/`: `api/`, `components/`, `pages/`, `hooks/`, `schemas.ts`, `types.ts`.
- [ ] 11.3 Create `src/lib/stores/auth-store.ts`: Zustand store with `{ accessToken, user, status }` + actions `setSession`, `clearSession`. No persistence middleware on the store itself — refresh-token persistence is its own concern (see 11.5).
- [ ] 11.4 Create `src/features/auth/types.ts`: `AuthUser` type matching `/me` shape (no password fields).
- [ ] 11.5 Create `src/lib/auth/token-storage.ts`: thin module owning the `localStorage` key for the refresh token (`adaasm.auth.refreshToken`). Functions `read`, `write`, `clear`. Tests cover the round-trip.
- [ ] 11.6 Design tokens [needs-figma]: re-fetch the Design Snapshot via `mcp__figma__get_design_context` for nodes `pMUgDI7rbRRzVWLCJhoVnY` `37:2` and `37:45`. Confirm: brand magenta `#e91e8c`, destructive red `#dc2626`, page bg `#fafafa`, text primary `#1a1a1a`, text secondary `#6b6b6b`, border `rgba(0,0,0,0.1)`, code chip bg `#f5f5f5`, radii (card 8 px, input/button/dropdown 6 px, chip 4 px), shadow recipes (login card subtle / dropdown elevated). If Figma is not available, pause and ask the user to reauth `/mcp`.
- [ ] 11.7 Extend `frontend/src/styles/globals.css` with CSS variables for the new tokens (`--brand`, `--brand-foreground`, `--destructive`, `--text-secondary`, etc.) for both light and (eventually) dark — keep the existing shadcn variables; add the new brand variables alongside.
- [ ] 11.8 Extend `frontend/tailwind.config.ts` `theme.extend.colors` to expose `brand` (mapping to `hsl(var(--brand))`) and a `text-secondary` token. Map `destructive` to `#dc2626` to match Figma.
- [ ] 11.9 Self-host the Inter (Black, Medium, Regular) and Menlo fonts: copy WOFF2 files to `frontend/public/fonts/`, add `@font-face` blocks in `globals.css`, set `font-family: Inter` on `body`. Document license attribution in `frontend/public/fonts/LICENSE.md`.

## 12. Frontend: API + interceptors

- [ ] 12.1 Extend `src/lib/api/client.ts` with the request interceptor (attach `Authorization` when access token present) and the response interceptor (single-flight refresh + retry; on failure clear store + navigate to `/login?next=...`). Comment the single-flight queue explicitly.
- [ ] 12.2 Create `src/features/auth/api/auth-api.ts`: `login(email, password)`, `refresh(refreshToken)`, `logout(refreshToken)`, `requestPasswordRecovery(email)`, `resetPassword(token, newPassword)`, `getMe()`.
- [ ] 12.3 Create `src/features/auth/hooks/use-me.ts`: TanStack Query hook hitting `/auth/me`, used to validate the in-memory access token on mount.
- [ ] 12.4 Bootstrap session on app load (in `src/main.tsx` or a `AuthBootstrap` component): if a refresh token exists in `localStorage`, attempt one refresh BEFORE rendering the router; populate the store on success; clear on failure.

## 13. Frontend: pages, routes, login screen (pixel-perfect to Figma 37:2)

- [ ] 13.1 Create `src/features/auth/schemas.ts`: zod schemas `loginSchema`, `forgotPasswordSchema`, `resetPasswordSchema`.
- [ ] 13.2 Create `src/features/auth/pages/LoginPage.tsx` [needs-figma `37:2`]: full-page `#fafafa` background, 448-px centred container with a `BrandLogo` ("singularthings" black + magenta), "ASM V2" h1, subtitle "Ingresa tus credenciales para continuar", form card (white, 1 px border `rgba(0,0,0,0.1)`, rounded 8 px, subtle shadow). Form: Email + Contraseña fields each with a leading 20-px icon (lucide `Mail` / `Lock`), right-aligned magenta link "¿Olvidaste tu contraseña?", full-width magenta "Iniciar sesión" submit (44 px, rounded 6 px). **Footer area is dev-only — render the top divider, "Usuarios de prueba:" label and the Menlo chip `admin@singularthings.io / admin123` on `#f5f5f5` ONLY when `import.meta.env.VITE_ENV === "development"`; in any other env the block is not rendered at all and the card shrinks accordingly.** Strings in Spanish to match the design. Reads `?next=` from the URL on success.
- [ ] 13.3 Create `src/features/auth/pages/ForgotPasswordPage.tsx`: form (email), submits to recovery endpoint, shows neutral confirmation message regardless. Reuse the same card visual language as `LoginPage` for consistency.
- [ ] 13.4 Create `src/features/auth/pages/ResetPasswordPage.tsx`: reads `?token=` from URL, shows error if missing, otherwise form (new password + confirm). Same card language.
- [ ] 13.5 Create `src/features/auth/components/RequireAuth.tsx`: route element. If store status `authenticated`, render `<Outlet />`. Otherwise navigate to `/login?next=<current path>`.
- [ ] 13.6 Update `src/App.tsx` to wire the new routes per the design (public + protected split).
- [ ] 13.7 Replace the placeholder Header content with the `UserMenuPill` component (see 13.8). Sidebar / layout container measurements stay as the bootstrap defined them.

## 13b. Frontend: User menu pill + logout dropdown (pixel-perfect to Figma 37:45)

- [ ] 13b.1 Create `src/components/ui/dropdown-menu.tsx` — shadcn/ui dropdown primitive on top of `@radix-ui/react-dropdown-menu`. Scaffolded manually per the shadcn pattern.
- [ ] 13b.2 Create `src/components/ui/avatar.tsx` — shadcn/ui avatar primitive used by the pill. Manual scaffold.
- [ ] 13b.3 Create `src/features/auth/components/UserMenuPill.tsx` [needs-figma `37:45`]: composes Avatar (32 px, `bg-brand` magenta, lucide `User` icon), two-line text (`full_name` 14 px medium, capitalised role 12 px medium `text-secondary`), and a 16 px chevron-down. Reads `user` from the auth store; renders nothing when `status !== "authenticated"`. Accessible button with `aria-haspopup="menu"` / `aria-expanded`.
- [ ] 13b.4 Create `src/features/auth/components/NotificationBell.tsx`: 36 px button with lucide `Bell` and an 8 px `bg-destructive` dot in the top-right corner (the dot is a non-functional placeholder for now — real notification state is a future US; the dot SHALL always show in this change to match the design). Document this placeholder behaviour in a code comment.
- [ ] 13b.5 Create `src/features/auth/components/UserMenuDropdown.tsx` [needs-figma `37:45`]: 256-px wide popover anchored under the pill. Header block (97 px) with `full_name` 16 px medium, `email` 14 px regular `text-secondary`, role text 12 px regular `text-secondary`; 1-px divider; logout `MenuItem` 48 px tall in `text-destructive` red with leading lucide `LogOut` icon and label "Cerrar sesión". Trap focus while open. Closes on Escape and outside-click via Radix defaults.
- [ ] 13b.6 Wire `UserMenuPill` + `UserMenuDropdown` into `src/app/layout/Header.tsx`. The Header right side now contains, left to right: a thin spacer, the `NotificationBell`, and the `UserMenuPill` that hosts the dropdown.
- [ ] 13b.7 Implement the logout action inside `UserMenuDropdown`: call `authApi.logout(refreshToken)` (best-effort), clear the Zustand store, clear `localStorage` via `token-storage.clear()`, navigate to `/login`.
- [ ] 13b.8 Verify pixel fidelity locally: build the app, navigate to `/` as a seeded admin, screenshot the Header at 1440-px viewport, place side-by-side with the Figma screenshot of `37:45`, document any spacing / colour drift and reconcile.

## 14. Frontend: tests

- [ ] 14.1 Unit tests for `token-storage` round-trip (`read`, `write`, `clear`).
- [ ] 14.2 Unit tests for the Zustand store reducers (`setSession`, `clearSession`).
- [ ] 14.3 Component test for `<LoginPage>` with MSW handler stubs: happy login → store populated + navigate to `?next` or `/`; 401 → inline error + password cleared. Assertions use accessible queries (`getByLabelText(/email/i)`, `getByRole("button", { name: /iniciar sesión/i })`). Includes two env-gated cases: render with `import.meta.env.VITE_ENV = "development"` → the "Usuarios de prueba" chip is present; render with `VITE_ENV = "production"` → the chip and its surrounding block are not in the DOM.
- [ ] 14.4 Component test for `<ForgotPasswordPage>`: submits and shows the neutral confirmation regardless of MSW response.
- [ ] 14.5 Component test for `<ResetPasswordPage>`: no token in URL → error state; with token → form, submit, navigate to `/login`.
- [ ] 14.6 Component test for `<RequireAuth>`: anonymous → redirect happens; authenticated → renders the outlet.
- [ ] 14.7 Interceptor test: simulate expired access → MSW returns 401 once, refresh returns 200, original retried — calling code sees one final 200; two 401s in a row → store cleared + redirect.
- [ ] 14.8 Component test for `<UserMenuPill>`: renders the user's full name and capitalised role; clicking opens the dropdown; Tab navigates to the logout item; pressing Escape closes the dropdown; clicking outside closes the dropdown.
- [ ] 14.9 Component test for `<UserMenuDropdown>` logout flow: clicking logout calls `authApi.logout`, clears the store, clears localStorage, and navigates to `/login`; logout when the backend returns network error still clears local state and navigates.
- [ ] 14.10 Vitest coverage `pnpm test:coverage` ≥ 80%.

## 15. Frontend: e2e smoke extension

- [ ] 15.1 Update `frontend/e2e/smoke.spec.ts` (or create `auth.spec.ts`) tagged `@smoke`: anonymous visit to `/` redirects to `/login`. Without backend running, this test can stub via Playwright route interception OR rely on the docker compose stack being up and use a seeded admin (preferred — closer to real). Document choice in the file.
- [ ] 15.2 Add an `@smoke` test for the happy login → land on placeholder shell flow (seeded admin via the compose stack). After landing, the test asserts that the Header shows "Admin User" and the role text.
- [ ] 15.3 Add an `@smoke` test for the logout flow: from the authenticated state, click the user pill, click "Cerrar sesión", verify the URL ends on `/login` and `localStorage` no longer contains the refresh token key.

## 16. Documentation

- [ ] 16.1 Update `ai-specs/specs/data-model.md`: replace the "not yet implemented" notes for `User`, `RefreshToken` with the column-level schema. Add `PasswordResetToken` with the same level of detail. Include the new `Introduced by: login-en-asm` and the migration filename.
- [ ] 16.2 Update `ai-specs/specs/api-spec.yml` to include all six `/auth/*` endpoints with request/response schemas and the RFC 7807 error codes.
- [ ] 16.3 Update `ai-specs/specs/development_guide.md`: add a "First-run: seed an administrator" section pointing at the `seed_admin` command; document the dev-only behaviour of `ConsoleEmailSender`; explain the localStorage refresh-token trade-off.
- [ ] 16.4 Update `.env.example` (already touched in 1.3 — verify the comments explain each new variable).

## 17. End-to-end verification

- [ ] 17.1 Fresh `.env`, `docker compose down -v && docker compose up -d --build`. All services healthy as before. Migration applies cleanly.
- [ ] 17.2 Seed an admin via the script. Confirm one admin row exists.
- [ ] 17.3 `curl -sS -X POST -H 'Content-Type: application/json' -d '{"email":"...","password":"..."}' http://localhost:8000/api/v1/auth/login` → 200 with both tokens.
- [ ] 17.4 Repeat with wrong password → 401 `INVALID_CREDENTIALS`. With unknown email → byte-identical 401.
- [ ] 17.5 Hit `GET /auth/me` with the access token → 200 with user info.
- [ ] 17.6 Open `http://localhost:5173/` in a fresh incognito → lands on `/login` (visual matches Figma `37:2`). Sign in with the seeded admin → placeholder shell renders with the `UserMenuPill` in the Header (visual matches Figma `37:45`). Click the pill → dropdown opens. Click "Cerrar sesión" → back on `/login`, `localStorage` clean.
- [ ] 17.7 Trigger `pre-commit run --all-files` → all hooks green.
- [ ] 17.8 Commit, push to `main` (per direct-to-main workflow). Verify both CI workflows pass on the push.
- [ ] 17.9 Archive the change with `openspec archive login-en-asm`.
