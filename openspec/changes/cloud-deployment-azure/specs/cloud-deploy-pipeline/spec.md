## ADDED Requirements

### Requirement: GitHub Actions deploys via OIDC federated identity

The system SHALL authenticate GitHub Actions to Azure using Workload Identity Federation — NOT a long-lived service principal client secret. The Azure App Registration's Federated Identity Credential SHALL trust GitHub's OIDC issuer for the specific `repo:tierraaudio/ada_asm:ref:refs/heads/main` subject (extensible to additional branches via Bicep parameters).

#### Scenario: No client secret exists in GitHub Secrets

- **WHEN** an operator inspects `Settings → Secrets and variables → Actions` on the repo
- **THEN** no secret with key `AZURE_CLIENT_SECRET` (or any equivalent name) is present
- **AND** the deploy workflows authenticate via the `azure/login@v2` action with `client-id` + `tenant-id` + `subscription-id` inputs (all public) and the OIDC `id-token: write` permission

#### Scenario: A push from a fork cannot deploy

- **WHEN** a contributor opens a PR from a fork
- **THEN** the deploy workflows do not run on PR triggers
- **AND** the OIDC subject claim filter rejects any token issued for `pull_request` events

### Requirement: Three workflows govern the deploy lifecycle

The system SHALL ship three GitHub Actions workflows under `.github/workflows/`:

- `deploy-backend.yml` — triggers on `push` to `main` touching `backend/**` OR manual `workflow_dispatch`.
- `deploy-frontend.yml` — triggers on `push` to `main` touching `frontend/**` OR manual `workflow_dispatch`.
- `deploy-infra.yml` — manual `workflow_dispatch` ONLY (infra changes require explicit invocation).

#### Scenario: A backend-only change deploys only the backend

- **WHEN** a commit changes only files under `backend/**` and pushes to `main`
- **THEN** `deploy-backend.yml` runs
- **AND** `deploy-frontend.yml` does NOT run

#### Scenario: An infra change requires manual dispatch

- **WHEN** a commit changes files under `infra/azure/**` and pushes to `main`
- **THEN** neither `deploy-backend.yml` nor `deploy-frontend.yml` runs automatically
- **AND** an operator must open `Actions → deploy-infra.yml → Run workflow` to apply the change
- **AND** the workflow executes `az deployment group what-if` first and presents the diff before applying

### Requirement: Backend deploys are gated by a successful migration job

The system SHALL execute the migration Container App Job AFTER pushing the new image to GHCR and BEFORE updating the backend Container App revision. If the migration job exits non-zero, the backend revision MUST NOT be updated.

#### Scenario: A successful migration promotes the new revision

- **WHEN** the deploy-backend workflow pushes image `ghcr.io/tierraaudio/ada-asm-backend:<sha>`
- **AND** invokes the migrate job with that image
- **AND** the job exits 0
- **THEN** the workflow updates `ca-ada-asm-backend-<env>` to a new revision with the same image
- **AND** sets traffic to 100% on the new revision

#### Scenario: A failed migration leaves the old revision serving

- **WHEN** the migrate job exits non-zero
- **THEN** the workflow fails with a clear error
- **AND** `ca-ada-asm-backend-<env>` still serves the previous revision
- **AND** the new image tag remains in GHCR but is not promoted

### Requirement: Frontend deploys go to the Static Web App via the official action

The system SHALL use `Azure/static-web-apps-deploy@v1` with the OIDC-issued deployment token (NOT a long-lived API token stored in GitHub Secrets). The workflow SHALL run vitest with the 80% coverage gate, then build the SPA with `VITE_API_URL=https://api.ada.tierra.audio` and `VITE_APP_INSIGHTS_CONNECTION_STRING` from the workflow's OIDC-authenticated Key Vault fetch.

#### Scenario: Failed FE tests block the deploy

- **WHEN** vitest exits non-zero
- **THEN** the workflow fails before the SWA deploy step
- **AND** the SPA in production is unchanged

### Requirement: Backend tests + linters run before image build

The system SHALL run ruff, mypy, and pytest (with the 80% coverage gate) before building the backend image. If any step fails the image is NOT built and the deploy is aborted.

#### Scenario: Failed backend tests block the image build

- **WHEN** pytest exits non-zero
- **THEN** the `docker build` step does not run
- **AND** GHCR does not receive a new image tag

### Requirement: Images are pushed to GHCR, not Azure Container Registry

The system SHALL push backend images to `ghcr.io/tierraaudio/ada-asm-backend` and frontend images (if ever needed; the SPA itself is static) to `ghcr.io/tierraaudio/ada-asm-frontend`. Container Apps pulls from GHCR using a PAT stored in Key Vault as `ghcr-pull-token`.

#### Scenario: Container Apps successfully pulls a new image from GHCR

- **WHEN** the deploy workflow pushes a new image to GHCR
- **AND** Container Apps is updated to that image tag
- **THEN** the Container App revision starts successfully
- **AND** the pull is authenticated via the `ghcr-pull-token` Key Vault secret
