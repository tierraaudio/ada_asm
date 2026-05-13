## Context

We have a bootable but anonymous skeleton: backend serves `/api/v1/health`, frontend renders a placeholder shell on `/`, no users, no protected endpoints. The first User Story is "Login en ASM 1.0" — Notion calls for `user + pass + password recovery`, plus the explicit hint that tech must allow per-project roles in the future.

The product is internal asset management. The user base is small (single-digit operators), the trust boundary is "behind the VPN" once we deploy. We are NOT building a public-facing consumer auth surface. That informs almost every choice below.

The backend standards we wrote (`ai-specs/specs/backend-standards.mdc`) already committed us to JWT (HS256) with refresh tokens + Argon2id. This document explains the concrete shape and the subtle decisions inside.

## Goals / Non-Goals

**Goals:**

- End-to-end working login (BE + FE) on `main`, exercised by tests + a Playwright smoke flow.
- A token shape that already carries per-project authorisation claims so the future RBAC change is data + middleware, not refactor.
- Defensive credential handling — Argon2id, uniform 401, per-IP rate limit, hashed refresh + reset tokens at rest.
- Idiomatic FastAPI dependencies (`require_user`, `require_role`) so future endpoints opt in by adding a single `Depends(...)`.
- FE auth UX with explicit "log me out of all devices" behaviour built into password resets.
- `MODIFIED` spec workflow exercised once on `runnable-skeleton` (placeholder shell now behind auth) so the openspec mechanic is proven on a real PR.

**Non-Goals:**

- No per-project RBAC enforcement (no `Project` exists yet to scope against).
- No social login, no OIDC, no SAML, no MFA.
- No CSRF protection — refresh token rides in JSON request bodies, not cookies, and access tokens are sent as `Authorization` headers.
- No production SMTP wiring. `ConsoleEmailSender` is the default; a stub `SmtpEmailSender` is added but disabled.
- No `POST /auth/signup`. Admins seed or create users.
- No "log me out of every device" UI button — the underlying mechanism (revoke-all-refresh on password reset) exists but no dedicated endpoint yet.
- No password strength scoring (zxcvbn). Just length 12-128.

## Decisions

### D1. JWT format: HS256 with the two-token pattern (access + refresh)

- **Access tokens**: HS256, TTL 15 minutes (configurable). Carry `sub`, `email`, `roles`, `project_scopes`, `iat`, `exp`, `jti`, `type: "access"`. **Not** persisted server-side.
- **Refresh tokens**: HS256, TTL 14 days (configurable). Carry `sub`, `iat`, `exp`, `jti`, `type: "refresh"`. Persisted as an **Argon2id hash** of the `jti` (NOT the full token) in `refresh_tokens` to support revocation and replay detection without storing the token itself.

Wait — clarifying: we store an Argon2id hash of the **token's signed serialised string** (or the `jti`). Concretely we hash the `jti` (a UUIDv4 is enough entropy) — this keeps the lookup deterministic on refresh while still preventing a DB leak from yielding usable tokens. See task list for the exact implementation.

- **Alternative considered: RS256**. Rejected for v1 — single service, no need to distribute a public key for verification yet. Switching is a configuration change later.
- **Alternative considered: opaque (random-string) tokens with server-side lookup on every request**. Rejected — every request hits the DB, doesn't scale. JWT-validated locally is faster and matches the FastAPI dependency pattern.

### D2. Refresh-token rotation is mandatory

Every `/auth/refresh` call:
1. Validates the presented refresh token (signature + expiry + revocation check by `jti` lookup).
2. Atomically revokes the presented token (`revoked_at = now()`) AND inserts a new refresh-token row.
3. Returns the new pair.

- **Why**: enables replay detection. If a revoked token is replayed, we know the token leaked and we treat it as a strong signal (log `WARNING auth.refresh.replay`; the user remains logged in via their *active* refresh token, but we have a paper trail). A more aggressive policy — revoke the entire user's session family on replay — is deferred to a later hardening change.

### D3. Refresh token lives in `localStorage`; access token lives in memory

The classic three-way trade-off:
- **All in memory**: refresh on hard-reload becomes impossible (the user would have to log in again).
- **All in `localStorage`**: vulnerable to XSS — any injected script reads the access token and impersonates the user for its TTL.
- **HttpOnly cookies**: best XSS protection but requires CSRF protection + cookie domain juggling for cross-origin during dev.

We pick the middle path: **access token in memory only** (15-minute TTL — limited blast radius even if it leaks), **refresh token in `localStorage`** so hard-reload can recover the session. The 14-day refresh token IS attractive to XSS, so the assumption is "our app does not have XSS holes". Tailwind + React + strict CSP (future) is the mitigation. Documented as a known trade-off in `development_guide.md`.

- **Alternative considered: HttpOnly cookies for both**. Rejected for v1 due to dev-mode cross-origin friction and CSRF surface; revisit when we deploy publicly.

### D4. Database storage for tokens — hash the secret part, not the JWT body

- `refresh_tokens.token_hash` stores `argon2id(jti)`. Lookup on refresh: extract `jti` from the validated JWT, search by `argon2id_verify(jti, row.token_hash)` filtered by `user_id` to bound the search. Pragmatic alternative: store a non-cryptographic hash (`sha256(jti)`) since `jti` is already 128 bits of entropy from a CSPRNG and Argon2id is overkill for already-high-entropy values. We use **`sha256(jti)`** for refresh tokens (DB-friendly, indexable) and **`argon2id(token)`** only for password-reset tokens (lower entropy in the user-visible URL form). See task list — this is the implementation choice we go with.
- **Why this split**: password-reset tokens travel by email and may be observed in transit / by malware; Argon2id slows offline brute force. Refresh tokens have 128-bit `jti` + are short-lived; sha256 is enough.

### D5. Password storage — Argon2id with sane parameters

`passlib[argon2]` with the library's modern defaults (time_cost=3, memory_cost=64 MiB, parallelism=4). The CI runner can verify a single login within 200 ms, which is within our latency budget. Operators can tune via the `app/infrastructure/security.py` constants if needed.

- **Alternative considered: bcrypt**. Rejected — Argon2id is the modern recommendation and `passlib` already supports it.

### D6. Uniform error responses on credential paths

For login, refresh, and `/me` we return RFC 7807 with a stable `code`. We deliberately collapse "email unknown / password wrong / inactive user" into one code (`INVALID_CREDENTIALS`) with one message, so the endpoint is not a username-enumeration oracle. Internal logs distinguish the cases with debug-level details bound to `request_id`.

### D7. Password recovery endpoint never reveals account existence

`POST /auth/password-recovery` returns the **same** HTTP 202 body whether or not the email is registered. The `EmailSender` is called only in the registered + active branch. The reset link URL we put in the email is constructed by the FE-served base URL passed in via the `FRONTEND_BASE_URL` config (new var in `.env.example`).

### D8. Rate limiting — slowapi, per IP

We add `slowapi` and apply limits only to `/auth/login` and `/auth/password-recovery`. Default `10/minute/IP`. Backed by an in-memory store in this change; the lib supports Redis as a backend so we can scale to multi-worker without code change later — only a config flip.

- **Alternative considered: do it in a reverse proxy (nginx) layer**. Deferred — we don't have an nginx between the backend and the world today, and adding one is its own change.

### D9. `EmailSender` Protocol with two implementations

```python
class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body_text: str, body_html: str | None = None) -> None: ...
```

- `ConsoleEmailSender` — default. `INFO`-level log line containing the address + body. **No** real email is dispatched in dev / CI.
- `SmtpEmailSender` — configured via `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`. Disabled unless `SMTP_HOST` is set. Not exercised in tests of this change beyond a unit test on the constructor.

The choice is wired in `app/infrastructure/email/__init__.py` and injected via FastAPI `Depends(...)`. Tests inject a fake.

### D10. FE — single auth store, multiple route guards

A single Zustand store (`useAuthStore`) holds `{ accessToken, user, status }`. A single component `<RequireAuth>` wraps protected routes. `App.tsx` becomes:

```tsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
  <Route path="/reset-password" element={<ResetPasswordPage />} />
  <Route element={<RequireAuth />}>
    <Route path="/" element={<DashboardLayout><PlaceholderPage /></DashboardLayout>} />
  </Route>
</Routes>
```

On boot (`main.tsx`), we attempt one refresh from `localStorage` before rendering the router — that way a hard refresh of an authenticated user does not flash the login page.

### D11. FE — axios interceptor refresh queue

When N concurrent requests are in flight and the access token expires, only ONE refresh call should fire; the other requests must queue and replay with the new token. The interceptor maintains a single in-flight promise; concurrent 401s `await` the same promise. Documented in code with a small comment because it is the most subtle bit of the FE.

### D12. Modify `runnable-skeleton` spec rather than replace

Per openspec, when you change a previously shipped behaviour you write a `MODIFIED` delta with the full new requirement body. The placeholder shell requirement is materially changing (was: always renders on `/`; becomes: renders on `/` only when authenticated, otherwise redirects). The delta lives in `specs/runnable-skeleton/spec.md` of this change. After archive, the canonical `openspec/specs/runnable-skeleton/spec.md` will reflect the new behaviour.

## Risks / Trade-offs

- **Risk**: refresh token in `localStorage` is XSS-attractive. → **Mitigation**: short access-token TTL caps the blast radius if an XSS leaks the access token; refresh tokens can be revoked at any time via `/auth/logout`; documented trade-off; the project does not render untrusted HTML and uses React's auto-escaping. Revisit when we deploy publicly (move to HttpOnly cookies + CSRF).
- **Risk**: in-memory rate-limit store breaks across multiple worker processes. → **Mitigation**: development runs a single worker; production deploy will configure slowapi with the existing Redis instance — config change, not code change.
- **Risk**: `ConsoleEmailSender` looks like email actually went out in dev — operators could be confused. → **Mitigation**: the log line is tagged `email.console.delivery` with a clear `dev-only=true` field; `development_guide.md` documents the behaviour explicitly.
- **Risk**: `citext` extension adds a dependency on PostgreSQL-specific functionality, ruling out SQLite for local dev forever. → **Mitigation**: we already require PostgreSQL via docker compose, and dropping that pretence makes data-model decisions cleaner.
- **Trade-off**: We hash refresh tokens with sha256 not Argon2id (D4). Faster lookups, no security loss given 128 bits of CSPRNG entropy. If a future audit insists on Argon2id everywhere, the migration is a single backfill column.
- **Trade-off**: We don't yet implement "log me out of every device" as a user-facing button. The plumbing (`revoke_all_refresh_tokens(user_id)`) is in the service for password-reset use; the UI surface is a follow-up.

## Migration Plan

1. Merge the change to `main` (direct-to-main workflow).
2. Pull latest, rebuild: `docker compose up -d --build`.
3. The migration creates `users`, `refresh_tokens`, `password_reset_tokens` tables and enables `citext`.
4. **One-time operator action**: seed the first admin:
   ```
   docker compose run --rm backend python -m app.scripts.seed_admin --email <you@example.com> --password '<long passphrase>'
   ```
5. Open `http://localhost:5173`, get redirected to `/login`, sign in.

Rollback path: `git revert` the merge commit. The migration's `downgrade()` drops the three tables and the `citext` extension (in reverse order).

## Open Questions

- **FRONTEND_BASE_URL for email links**: for local dev this is `http://localhost:5173`. For deploy we'll need a real domain. Not blocking — the variable lives in `.env.example` and gets set at deploy time.
- **JWT secret rotation**: today, rotating `JWT_SECRET` immediately invalidates every issued token. We don't yet have a key-id / `kid` claim or multi-secret support. Will revisit before we have many users.
- **Whether to log the user agent / IP into `refresh_tokens`**: privacy-vs-debuggability trade-off. Current decision: log them but make sure they don't end up in any user-facing surface. Revisit at GDPR review.
- **Long-running tab token refresh**: a tab that stays open for 15 days will outlive its refresh token. We do not yet have a "session expired, please re-login" UX beyond redirecting to `/login` on the next 401. Acceptable for v1.
