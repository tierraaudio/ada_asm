## REMOVED Requirements

### Requirement: Images are pushed to GHCR, not Azure Container Registry

**Reason**: GHCR auth has been a blocker for the dev bootstrap (org-scoped PAT permissions are not deterministic; public-visibility propagation is opaque). Azure Container Registry integrates natively with Container Apps' system-assigned managed identity, eliminating the long-lived PAT and the Key Vault secret cache invalidation problem.

**Migration**: Replaced by the new requirement "Images are pushed to Azure Container Registry" below.

## ADDED Requirements

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
