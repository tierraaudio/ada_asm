## Why

The `cloud-deployment-azure` stack pulls backend images from GHCR, which during dev bootstrap exposed two blocking auth quirks: (1) org-scoped GHCR packages reject classic PATs that have `read:packages` scope but no explicit package-collaborator grant, and (2) GHCR's anonymous token endpoint refused pulls for hours after the package was flipped public in the UI. Each rotation also requires updating Key Vault + force-refreshing cached secrets across every Container App revision. Azure Container Registry (ACR) eliminates all three problems by integrating natively with Container Apps' system-assigned managed identities: no PAT, no secret, no propagation race.

## What Changes

- Add `infra/azure/modules/acr.bicep` creating ACR Basic SKU + `AcrPull` role assignments for the 4 Container App / Job system MIs and `AcrPush` for the deploy UAMI.
- Modify `container_apps.bicep` + `container_jobs.bicep` to drop `registries[ghcr.io]` blocks and `passwordSecretRef`; add an unauthenticated `registries[]` entry with `server: <acrLoginServer>` and `identity: 'system'`.
- Modify `keyvault.bicep` to remove `ghcr-pull-token` from the seeded `secretNames` list.
- **BREAKING (dev only)**: existing Container Apps revisions referencing GHCR will be replaced; old `ghcr-pull-token` KV secret is hard-deleted.
- `.github/workflows/deploy-backend.yml`: swap `Log in to GHCR` (docker/login-action) for an `Azure login (OIDC)` step + `az acr login --name acradaasmdev`; update `IMAGE_REGISTRY` + `IMAGE_REPO`; drop the `packages: write` permission.
- One-time bootstrap helper: `az acr import` the existing GHCR image `8a210087…` into ACR so the in-flight dev environment recovers without a fresh build.
- `ai-specs/specs/development_guide.md`: new "Container Registry" subsection documenting the ACR + MI pattern.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `cloud-deployment-azure`: container image source moves from GHCR to ACR; registry credentials block + Key Vault `ghcr-pull-token` secret are removed; system MIs gain `AcrPull` on the ACR scope.

## Impact

- **Bicep**: 1 new module (`acr.bicep`), 3 modified (`container_apps.bicep`, `container_jobs.bicep`, `keyvault.bicep`), main.bicep wires the new module + role assignments.
- **GitHub Actions**: `deploy-backend.yml` (auth path + registry URLs), reduced workflow permissions.
- **Azure**: new `acradaasmdev` ACR resource (≈€4/mo Basic SKU; fits the €35/mo dev floor); 5 new role assignments scoped to ACR; `ghcr-pull-token` secret deleted from `kv-ada-asm-dev`.
- **GitHub**: the `ghcr.io/tierraaudio/ada-asm-backend` package can be deprecated after a grace period (out of scope here).
- **Docs**: `development_guide.md` only; data-model + api-spec untouched (registry isn't in those surfaces).
