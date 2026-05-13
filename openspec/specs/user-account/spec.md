# user-account Specification

## Purpose
TBD - created by archiving change login-en-asm. Update Purpose after archive.
## Requirements
### Requirement: User accounts are persisted with hashed passwords

The system SHALL persist `User` records with a unique email (case-insensitive), a password hash, a display name, a global role and an active flag. Passwords MUST be hashed with Argon2id before storage. Plaintext passwords MUST NEVER be persisted, logged or returned by any API.

#### Scenario: Creating a user stores an Argon2id hash, not the plaintext

- **WHEN** a `User` is created with password `S3cret-passphrase!`
- **THEN** the persisted `password_hash` column starts with the Argon2id prefix (`$argon2id$`)
- **AND** the persisted row contains no column equal to the plaintext password
- **AND** no log line emitted during creation contains the plaintext password

#### Scenario: Email uniqueness is case-insensitive

- **WHEN** a `User` exists with email `Founder@Example.com`
- **AND** an attempt is made to create another user with email `founder@example.com`
- **THEN** the database insert fails with a unique-constraint violation
- **AND** the API surfaces a 409 RFC 7807 error with code `EMAIL_ALREADY_REGISTERED`

#### Scenario: Email format is validated before persistence

- **WHEN** a `User` creation is requested with `email = "not-an-email"`
- **THEN** the request is rejected with HTTP 422
- **AND** no row is inserted

### Requirement: A user can have its password reset via a single-use token

The system SHALL support resetting a `User`'s password using a single-use token delivered via email. The reset token MUST: be cryptographically random with at least 256 bits of entropy, be stored only as an Argon2id hash, expire within a configurable TTL (default 1 hour), and be invalidated after first use OR after expiry, whichever comes first.

#### Scenario: A valid unused token resets the password

- **WHEN** a valid, unused, unexpired reset token is submitted with a new password meeting the password policy
- **THEN** the user's `password_hash` is updated
- **AND** the reset token's `used_at` column is set to the current time
- **AND** all of the user's active refresh tokens are revoked (logging the user out of every session)

#### Scenario: A token cannot be used twice

- **WHEN** a reset token has already been used (its `used_at` is set)
- **AND** the same token is submitted again with a new password
- **THEN** the request is rejected with HTTP 400 and code `RESET_TOKEN_ALREADY_USED`
- **AND** the user's password is NOT changed

#### Scenario: An expired token is rejected

- **WHEN** a reset token's `expires_at` is in the past
- **AND** the token is submitted with a new password
- **THEN** the request is rejected with HTTP 400 and code `RESET_TOKEN_EXPIRED`

### Requirement: A user has a global role used by authorisation

Every `User` SHALL carry a `global_role` field with one of two values: `admin` or `user`. The default for newly created users is `user`. The role is included in every issued access token's `roles` claim. The role is the only authorisation surface in this change; per-project roles are scaffolded in the token payload but not enforced.

#### Scenario: Issued access tokens include the user's global role in claims

- **WHEN** a user with `global_role = "admin"` logs in successfully
- **THEN** the issued access token's payload includes `"roles": ["admin"]`
- **AND** the issued access token's payload includes `"project_scopes": ["*"]`

#### Scenario: Newly created users default to the 'user' role

- **WHEN** a new user is created without an explicit role
- **THEN** the persisted `global_role` is `"user"`

### Requirement: An administrator can be seeded into a fresh database

The system SHALL provide a one-shot command `python -m app.scripts.seed_admin --email <e> --password <p>` that creates an active `User` with `global_role = "admin"` if no admin exists yet. Re-running the command with the same email when an admin already exists MUST exit non-zero and print a clear message.

#### Scenario: Seeding the first admin on an empty database

- **WHEN** the database has zero users
- **AND** the operator runs `python -m app.scripts.seed_admin --email founder@example.com --password 'long-passphrase-here-please'`
- **THEN** the command exits with code 0
- **AND** a single `User` row exists with `email = "founder@example.com"`, `global_role = "admin"`, `is_active = true`, and an Argon2id `password_hash`

#### Scenario: Re-seeding refuses when an admin already exists

- **WHEN** at least one `User` with `global_role = "admin"` already exists
- **AND** the operator runs the seed command
- **THEN** the command exits non-zero
- **AND** prints a message naming the existing admin email(s)

### Requirement: Passwords meet a minimum strength policy

The system SHALL reject any password shorter than 12 characters or longer than 128 characters at every entry point (seed command, password reset, future change-password endpoint). The error MUST identify the violated rule.

#### Scenario: Short password is rejected

- **WHEN** a password of length 11 is submitted to any password-setting flow
- **THEN** the request is rejected with HTTP 422 and code `PASSWORD_TOO_SHORT`
- **AND** no password hash is computed or stored

