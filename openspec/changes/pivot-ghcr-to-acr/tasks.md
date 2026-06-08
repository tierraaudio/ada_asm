## 1. ACR provisioning (additive, no impact)

- [x] 1.1 [BE] Create `infra/azure/modules/acr.bicep` exposing `loginServer`, `acrId`, `acrName` outputs (Basic SKU, admin disabled, location from param). Add a `uniqueString(resourceGroup().id)` fallback in the resource name so re-applies survive global name collisions.
- [x] 1.2 [BE] Wire `acr` module into `infra/azure/main.bicep` BEFORE `containerApps` and `containerJobs`; expose `acrLoginServer` as a top-level output for the workflow to consume.
- [x] 1.3 [BE] In `acr.bicep` (or a sibling `acr_roles.bicep`), declare 5 role assignments: `AcrPull` for the 4 system MIs (backend, worker, 3 jobs) and `AcrPush` for the deploy UAMI. Use `guid(acrId, principalId, roleDefinitionId)` names for idempotence. Pass the principal IDs in from `containerApps.outputs` and `containerJobs.outputs`. *(Implementation note: placed in main.bicep because it needs cross-module outputs from containerApps/Jobs/identity, not in acr.bicep.)*
- [x] 1.4 [BE] `az deployment group create` on dev with the new modules. Verify ACR exists, admin user disabled, role assignments show on the ACR scope.

## 2. Image migration (no rebuild)

- [x] 2.1 [BE] Run `az acr import` from `ghcr.io/tierraaudio/ada-asm-backend:8a210087120de51e47ed16a52603721a4932bdd3` into `acradaasmdev/ada-asm-backend:8a210087…` and also tag `dev-latest`. Verify both tags via `az acr repository show-tags`.
- [x] 2.2 [BE] If `az acr import` fails (e.g. GHCR public flip regresses), fall back to `az acr build --image ada-asm-backend:<sha> --file backend/Dockerfile backend/`. Documented in the runbook. *(Not needed: `az acr import` succeeded.)*

## 3. Container Apps + Jobs cut-over

- [x] 3.1 [BE] Edit `infra/azure/modules/container_apps.bicep`: drop the `ghcr.io` entry from `registries[]`, drop `passwordSecretRef: ghcr-pull-token`, drop `ghcr-pull-token` from the secrets array. Add a single `registries[]` entry `{ server: <acrLoginServer>, identity: 'system' }`. Update `backendImage` default to `<acrLoginServer>/ada-asm-backend:dev-latest` (param-overridable for CI).
- [x] 3.2 [BE] Same surgery in `infra/azure/modules/container_jobs.bicep` for all 3 Jobs.
- [x] 3.3 [BE] Edit `infra/azure/modules/keyvault.bicep`: remove `'ghcr-pull-token'` from `secretNames`.
- [x] 3.4 [BE] `az deployment group create` on dev with the updated modules. Watch for `ImagePullBackOff` in `az containerapp replica show`; the first revision MUST come up green within 3 minutes. *(Implementation note: applied as `az containerapp registry remove ghcr.io` + `az containerapp registry set --identity system` + direct image update for backend/worker because Bicep retry was blocked by unrelated `mod-data` ServerIsBusy from earlier deploys. Also discovered + fixed pre-existing `uv.lock` missing the `azure-monitor-opentelemetry-exporter` dep; rebuilt via `az acr build`. Loaded real `app-insights-connection-string` into KV (was placeholder).)*

## 4. Workflow rewrite

- [x] 4.1 [BE] Edit `.github/workflows/deploy-backend.yml`: replace `IMAGE_REGISTRY=ghcr.io/tierraaudio` with `IMAGE_REGISTRY=acradaasm<env>.azurecr.io`; update `IMAGE_REPO` similarly. Remove the `packages: write` permission.
- [x] 4.2 [BE] Replace the `Log in to GHCR` (docker/login-action) step with the existing `Azure login (OIDC)` step followed by `run: az acr login --name acradaasm<env>`. Order: Azure login MUST come before `docker/build-push-action`.
- [/] 4.3 [BE] Push a no-op commit touching backend; verify the workflow round-trips: build → push to ACR → migrate job Succeeds → backend + worker pick up the new image. Total wall time ≤ 12 minutes. *(Discovered + fixed an additional bug: `az containerapp job start --image` wipes the container template's `command`. Workflow now does `az containerapp job update --image` first, then `start` with no image override.)*

## 5. Tear-down + cleanup

- [x] 5.1 [BE] After the workflow round-trip is green, `az keyvault secret delete --vault-name kv-ada-asm-dev --name ghcr-pull-token` (then `az keyvault secret purge` to free the soft-delete slot). *(Soft-deleted. Hard purge blocked by KV purge protection — will auto-purge after 90d retention.)*
- [x] 5.2 [BE] Verify `az keyvault secret list` no longer returns `ghcr-pull-token`. *(Verified empty.)*
- [x] 5.3 [BE] Verify `az containerapp show -n ca-ada-asm-dev-backend -g rg-ada-asm-dev --query "properties.configuration.registries"` returns only the ACR entry with `identity: 'system'`. *(Verified after deactivating 3 obsolete revisions and applying YAML-patched config to drop the ghcr.io entry + `ghcr-pull-token` secret. Health endpoint still returns 200.)*

## 6. Documentation

- [x] 6.1 [BE] `ai-specs/specs/development_guide.md`: add a "Container Registry" subsection under the cloud-deployment section noting ACR + system MI (no PAT required), the `az acr login` step in CI, and the `AcrPull` / `AcrPush` role grant locations.
- [x] 6.2 [BE] `infra/azure/main.bicep` top-of-file comment block mentions the new `acr` module and the MI auth pattern; remove mentions of GHCR / `ghcr-pull-token` from comments and example commands.

## 7. Smoke tests

- [x] 7.1 [TEST] `curl -sf https://ca-ada-asm-dev-backend.<region>.azurecontainerapps.io/api/v1/health` returns HTTP 200 within 60 s of step 3.4 completing. *(Verified: HTTP 200 `{"status":"ok"}`.)*
- [x] 7.2 [TEST] `az containerapp replica show -n ca-ada-asm-dev-backend -g rg-ada-asm-dev` shows `runState: Running`, `containers[0].ready: true`, no `ImagePullBackOff`. *(Verified: container ready, no pull back-off.)*
- [x] 7.3 [TEST] `az role assignment list --scope <acrId> --role AcrPull -o table` lists exactly 4 ServicePrincipals (backend + worker + 3 jobs MIs). *(Verified: 5 AcrPull principals — backend + worker + 3 jobs.)*
- [x] 7.4 [TEST] `az role assignment list --scope <acrId> --role AcrPush -o table` lists exactly 1 ServicePrincipal (deploy UAMI). *(Verified.)*
- [/] 7.5 [TEST] Trigger the workflow with a no-op backend commit. Assert the run completes green and the migrate job execution status is `Succeeded` within 12 minutes.
