# cloud-deploy-pipeline Specification

## Purpose
GitHub Actions CI/CD that builds, tests, and deploys backend + frontend to the Azure production environment on every push to main, authenticated via OIDC federation (no long-lived secrets).

## Requirements

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

### Requirement: Images are pushed to Azure Container Registry

The system SHALL push backend images to `<acrLoginServer>/ada-asm-backend` where `<acrLoginServer>` is the login server of the per-environment ACR (e.g. `acradaasmdev.azurecr.io` for dev). Container Apps SHALL pull from this ACR using their system-assigned managed identity with the built-in `AcrPull` role on the ACR scope. The `deploy-backend.yml` GitHub Actions workflow SHALL authenticate to Azure via OIDC federation and push with `az acr login --name <acrName>`. No PAT, registry token, or admin password SHALL be stored in Key Vault or anywhere else for this purpose.

#### Scenario: Container Apps successfully pulls a new image from ACR via managed identity

- **WHEN** the deploy workflow pushes a new image to the per-environment ACR
- **AND** Container Apps is updated to that image tag
- **THEN** the Container App revision starts successfully on the first pull attempt
- **AND** the pull is authenticated via the Container App's system-assigned managed identity
- **AND** no `passwordSecretRef` appears in the `registries[]` array of the Container App configuration

#### Scenario: Workflow auth uses OIDC, not packages:write

- **WHEN** the `deploy-backend.yml` workflow runs
- **THEN** the workflow permissions block does NOT include `packages: write`
- **AND** the build job authenticates to ACR via `azure/login@v2` (OIDC) followed by `az acr login --name <acrName>`
- **AND** no `docker/login-action` step targets `ghcr.io`

### Requirement: The migration Container App Job runs against ACR-pulled images

The system SHALL execute the migration Container App Job AFTER pushing the new image to ACR and BEFORE updating the backend Container App revision. If the migration job exits non-zero, the backend revision MUST NOT be updated. The migration Job SHALL pull its image from ACR using its own system-assigned managed identity.

#### Scenario: Failed migration aborts deploy

- **WHEN** the migration Container App Job exits non-zero
- **THEN** the workflow fails before updating any Container App
- **AND** the new image tag remains in ACR but is not promoted to the backend revision
- **AND** the migration Job pull is authenticated via its own system MI on ACR

### Requirement: GHCR is no longer a deploy target

The system SHALL NOT push images to, or pull images from, `ghcr.io/tierraaudio/ada-asm-backend` once this change is applied. The corresponding `passwordSecretRef: ghcr-pull-token` SHALL be removed from every Container App and Container App Job in scope.

#### Scenario: No Container App references GHCR

- **WHEN** an operator runs `az containerapp show -n ca-ada-asm-<env>-backend -g rg-ada-asm-<env>` and inspects `properties.configuration.registries`
- **THEN** every entry has `server` ending in `.azurecr.io`
- **AND** no entry has `passwordSecretRef`
- **AND** every entry has `identity: 'system'`

