## ADDED Requirements

### Requirement: A user can exchange email + password for an access token and a refresh token

The system SHALL accept `POST /api/v1/auth/login` with a JSON body `{ "email": "...", "password": "..." }` and respond with both an **access token** (short-lived) and a **refresh token** (long-lived) when the credentials are valid and the user is active. The response MUST NOT differentiate between "email not found", "password wrong" or "user not active" in its public message — all three return HTTP 401 with code `INVALID_CREDENTIALS`. Internal logs MAY (and SHOULD) distinguish the cases for operators.

#### Scenario: Valid credentials issue both tokens

- **WHEN** `POST /api/v1/auth/login` is called with the email + password of an active user
- **THEN** the response is HTTP 200 with a JSON body containing `access_token`, `refresh_token`, `token_type: "bearer"`, and `expires_in` (seconds until the access token expires)
- **AND** the access token decodes to a JWT with claims `sub`, `email`, `roles`, `project_scopes`, `iat`, `exp`, `jti`, `type: "access"`
- **AND** the refresh token decodes to a JWT with `type: "refresh"` and the same `sub`
- **AND** a row is inserted in `refresh_tokens` whose `token_hash` matches the issued refresh token

#### Scenario: Invalid credentials return a uniform 401

- **WHEN** `POST /api/v1/auth/login` is called with an email that is not registered
- **THEN** the response is HTTP 401 with `code: "INVALID_CREDENTIALS"`
- **WHEN** the same endpoint is called with a registered email and a wrong password
- **THEN** the response is HTTP 401 with `code: "INVALID_CREDENTIALS"`
- **AND** the response bodies for both cases are byte-identical (no information leak)

#### Scenario: An inactive user cannot log in

- **WHEN** a user with `is_active = false` submits valid credentials
- **THEN** the response is HTTP 401 with `code: "INVALID_CREDENTIALS"` (same as above)

### Requirement: A refresh token can be exchanged for a new access token, rotating the refresh

The system SHALL accept `POST /api/v1/auth/refresh` with `{ "refresh_token": "..." }` and respond with a new access token AND a new refresh token. The presented refresh token MUST be revoked atomically with issuing the new pair. Using a revoked refresh token MUST return 401 with code `REFRESH_TOKEN_REVOKED`.

#### Scenario: Valid refresh token rotates to a new pair

- **WHEN** a valid, unexpired, unrevoked refresh token is submitted to `/api/v1/auth/refresh`
- **THEN** the response is HTTP 200 with a new `access_token` and a new `refresh_token`
- **AND** the presented refresh token's row has `revoked_at` set to the current time
- **AND** the new refresh token's row is `revoked_at = NULL`

#### Scenario: Reusing a revoked refresh token is rejected

- **WHEN** a refresh token that has already been rotated (its `revoked_at` is set) is submitted again
- **THEN** the response is HTTP 401 with `code: "REFRESH_TOKEN_REVOKED"`
- **AND** the system logs a `WARNING` line tagged `auth.refresh.replay` with the `sub` and `jti` (without leaking the token itself)

#### Scenario: Expired refresh token is rejected

- **WHEN** a refresh token whose `expires_at` is in the past is submitted
- **THEN** the response is HTTP 401 with `code: "REFRESH_TOKEN_EXPIRED"`

### Requirement: A user can log out, revoking the supplied refresh token

The system SHALL accept `POST /api/v1/auth/logout` with `{ "refresh_token": "..." }` and revoke the corresponding refresh token. The endpoint MUST be idempotent — replaying it with an already-revoked or unknown token still returns 204.

#### Scenario: Logout revokes the refresh token

- **WHEN** a valid refresh token is submitted to `/api/v1/auth/logout`
- **THEN** the response is HTTP 204
- **AND** that refresh token's `revoked_at` is set in the database
- **AND** a subsequent `POST /api/v1/auth/refresh` with that same token returns 401 `REFRESH_TOKEN_REVOKED`

#### Scenario: Logout is idempotent

- **WHEN** logout is called with an unknown or already-revoked refresh token
- **THEN** the response is HTTP 204 (never 401 / 404)
- **AND** no database row is mutated for the unknown case

### Requirement: An access token authenticates protected endpoints via a FastAPI dependency

The system SHALL provide a FastAPI dependency `require_user` that extracts the access token from the `Authorization: Bearer ...` header, validates its signature, type, and expiry, loads the corresponding `User`, and injects it into the route handler. Protected endpoints MUST use this dependency.

#### Scenario: `GET /api/v1/auth/me` returns the current user

- **WHEN** `GET /api/v1/auth/me` is called with a valid access token
- **THEN** the response is HTTP 200 with `{ id, email, full_name, global_role, is_active, created_at }`
- **AND** the response body contains no `password_hash` field

#### Scenario: Missing Authorization header returns 401

- **WHEN** `GET /api/v1/auth/me` is called with no `Authorization` header
- **THEN** the response is HTTP 401 with `code: "UNAUTHENTICATED"`

#### Scenario: Expired access token is rejected

- **WHEN** `GET /api/v1/auth/me` is called with an access token whose `exp` is in the past
- **THEN** the response is HTTP 401 with `code: "ACCESS_TOKEN_EXPIRED"`

#### Scenario: A refresh token cannot be used as an access token

- **WHEN** `GET /api/v1/auth/me` is called with a token whose `type` claim is `"refresh"`
- **THEN** the response is HTTP 401 with `code: "ACCESS_TOKEN_WRONG_TYPE"`

### Requirement: A password recovery email can be requested

The system SHALL accept `POST /api/v1/auth/password-recovery` with `{ "email": "..." }`, ALWAYS return HTTP 202, and — if the email belongs to an active user — issue a single-use password reset token and dispatch it via the configured `EmailSender`. The response body MUST be byte-identical whether or not the email exists, so the endpoint cannot be used as an email-enumeration oracle.

#### Scenario: Recovery for a registered email enqueues an email and persists the token

- **WHEN** `POST /api/v1/auth/password-recovery` is called with the email of an active user
- **THEN** the response is HTTP 202 with body `{ "status": "accepted" }`
- **AND** a row is inserted in `password_reset_tokens` for that user with a future `expires_at`
- **AND** the configured `EmailSender` is called exactly once with the user's email and a body containing the reset link

#### Scenario: Recovery for an unknown email returns the same response without side effects

- **WHEN** the endpoint is called with an email that is not registered
- **THEN** the response is HTTP 202 with the same body as the previous scenario
- **AND** no `password_reset_tokens` row is inserted
- **AND** the `EmailSender` is not called

### Requirement: A password reset token can be redeemed for a new password

The system SHALL accept `POST /api/v1/auth/password-reset` with `{ "token": "...", "new_password": "..." }`. On success the user's password is updated and ALL refresh tokens for that user are revoked.

#### Scenario: Successful reset revokes all active sessions

- **WHEN** a valid, unused, unexpired reset token is redeemed with a password meeting policy
- **THEN** the response is HTTP 204
- **AND** the user's `password_hash` is updated
- **AND** every previously active refresh token for that user has `revoked_at` set

### Requirement: Credential endpoints are rate-limited per source IP

The system SHALL apply per-IP rate limiting to `POST /api/v1/auth/login` and `POST /api/v1/auth/password-recovery`. The default limit is 10 requests per minute per IP (configurable via `LOGIN_RATE_LIMIT_PER_MINUTE`). Over-limit requests return HTTP 429 with code `RATE_LIMIT_EXCEEDED` and a `Retry-After` header.

#### Scenario: Exceeding the login rate limit returns 429

- **WHEN** the same source IP issues 11 login requests within 60 seconds
- **THEN** the 11th response is HTTP 429
- **AND** the response includes a `Retry-After` header with an integer number of seconds
