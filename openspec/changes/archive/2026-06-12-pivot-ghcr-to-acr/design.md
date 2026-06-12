## Context

The dev bootstrap of `cloud-deployment-azure` parked Container Apps and 3 Jobs in `ImagePullBackOff` for hours. Two GHCR auth quirks were the root cause:

- **Org-scoped private package**: A classic PAT with `read:packages` returns a token whose effective grants are evaluated per-package. For packages under the `tierraaudio` org, the PAT owner must also be a collaborator on the specific package — a non-obvious manual UI step missing from the runbook. The placeholder Bicep username `tierraaudio-bot` was never wired to an actual GitHub user.
- **Public-visibility race**: After flipping the package to "Public", GHCR's anonymous token endpoint kept returning 401 for the next reproductions of `docker pull`. Propagation is opaque (no API to verify) and was still not effective when this change was scoped.

Each rotation also requires writing the PAT into Key Vault, then force-updating every Container App + Job because Container Apps caches the resolved secret value at revision creation. A second-order issue: the system-assigned MIs on each app/job did not automatically receive `Key Vault Secrets User`, so the first deploy from Bicep silently fell back to the cached value and surfaced as a `FetchingKeyVaultSecretFailed` log only.

Azure Container Registry (ACR) replaces this pipeline with a registry that authenticates Container Apps via the system MI directly. No KV secret, no PAT in the runbook, no GitHub package visibility.

## Goals / Non-Goals

**Goals:**
- Container Apps + Jobs pull from `acradaasmdev.azurecr.io` via system-assigned managed identity, with no `passwordSecretRef`.
- A single Bicep deploy (`az deployment group create`) from a clean RG produces a working pull on the first revision.
- The `deploy-backend.yml` workflow builds + pushes to ACR via OIDC; `packages: write` permission is removed.
- The in-flight dev image (`8a210087…`) is migrated into ACR without a fresh build cycle, so dev recovers within minutes.
- Documentation in `development_guide.md` states the new pattern so prod can be brought up the same way later.

**Non-Goals:**
- Prod environment cutover. Prod is a separate change; this work only touches `rg-ada-asm-dev`.
- ACR replication, geo-redundancy, or Premium SKU features (Basic SKU is sufficient for €35/mo dev floor and a single region).
- ACR tasks / build-in-registry — GitHub Actions remains the builder.
- Image signing / Notary / content trust.
- Retention policies on ACR (Basic SKU does not support them; revisit if/when we move to Standard).
- Deleting the `ghcr.io/tierraaudio/ada-asm-backend` package on the GitHub side (left for a follow-up after a grace period).

## Decisions

### D1 — ACR Basic SKU in the same RG
Use Basic SKU (`acradaasmdev`), in `rg-ada-asm-dev`, same region as Container Apps (`westeurope`).

**Why**: Basic is €4.20/mo, 10 GB included, no replication. Container Apps + ACR in the same region eliminates egress charges and gives the fastest pulls. ACR-name globally unique → use `acradaasmdev` (no hyphens; ACR names must be alphanumeric).

**Alternatives considered**:
- Premium SKU with geo-replication (overkill for dev; ≈€500/mo just for the registry).
- Shared ACR across dev + prod (rejected: violates the "dev never touches prod resources" rule the user stated explicitly earlier in the session).

### D2 — System-assigned MI + `AcrPull` role, no admin user
Disable ACR admin user (`adminUserEnabled: false`). Each Container App and Job has a system-assigned MI; grant `AcrPull` on the ACR scope to each.

**Why**: The whole point of the pivot is to remove long-lived registry secrets. Admin user re-introduces a password we'd have to store somewhere. System MI auth is the recommended pattern in Microsoft's Container Apps docs.

**Alternatives considered**:
- User-assigned MI shared across all 5 resources (cleaner but requires extra UAMI Bicep + assignment on each `containers.identity.userAssignedIdentities` map — more moving parts for the same security posture).
- ACR token (scope: `repositories/ada-asm-backend:pull`) stored as a KV secret (re-introduces the rotation problem we're eliminating).

### D3 — UAMI gets `AcrPush` for CI pushes via OIDC
The existing `id-deploy-ada-asm-dev` UAMI (already federated with GitHub Actions OIDC) gets `AcrPush` on the ACR scope. The workflow does `az acr login --name acradaasmdev` after `azure/login@v2`.

**Why**: OIDC federation is already configured (the workflow uses it for `az containerapp` updates). Adding `AcrPush` is a single role assignment in Bicep, no new credentials.

**Alternatives considered**:
- Service principal with client secret in GHA secrets (worse: long-lived secret, manual rotation).
- ACR repository-scoped token stored as a GHA secret (same downside).

### D4 — Registry block on Container Apps uses `identity: 'system'`
Container Apps' `registries[]` entry is `{ server: '<acrLoginServer>', identity: 'system' }`. No `passwordSecretRef`. Bicep modules drop the entire `ghcr.io` registry entry and the `ghcr-pull-token` secret from the `secrets` array.

**Why**: Avoids the secret-cache invalidation problem entirely. Azure resolves the MI token at pull time.

**Trade-off**: The first deploy is order-sensitive — the `AcrPull` role MUST exist before Container Apps tries the first pull, otherwise the first revision fails identically to today's symptoms. Bicep `dependsOn` covers this in the same deployment; a half-applied deploy (role assignment created but Container App rolled back) would leave a stale assignment but no app — harmless, idempotent on re-apply.

### D5 — `az acr import` for the existing dev image
Use `az acr import --source ghcr.io/tierraaudio/ada-asm-backend:8a210087… --image ada-asm-backend:8a210087…` to copy the existing artifact server-side, tagged both with the SHA and `dev-latest`.

**Why**: A fresh CI build round-trip is 7-10 min (already paid that bill twice this session). `az acr import` is server-to-server, ≈30s, and works against the now-public GHCR source.

**Alternatives considered**:
- Re-trigger the workflow with the new push path. Discarded: blocks recovery on yet another CI cycle and a workflow we still need to edit.
- Build locally and `docker push` to ACR. Discarded: my Mac is arm64; the production image is amd64. `az acr import` is the right tool.

### D6 — Cleanup ordering
Order of operations to avoid windows where pull is broken:
1. Create ACR + role assignments (no impact on running infra).
2. `az acr import` the image.
3. Update Bicep modules (registries block + secrets list) and `az deployment group create` — this updates Container Apps + Jobs to the new registry config in one transaction.
4. Smoke `curl /api/v1/health` against the FQDN.
5. Only after green: delete `ghcr-pull-token` from KV and update `keyvault.bicep` so the next clean re-apply doesn't re-seed it.

**Why**: Steps 1-3 are additive / atomic at the resource level; step 5 is destructive and only fires after the new path is proven.

## Risks / Trade-offs

- **[Risk] First deploy from a clean RG can race on role assignment vs. Container App provisioning.** → **Mitigation**: Bicep `dependsOn` between the role assignment resource and the Container App resource. Re-applying is idempotent.
- **[Risk] If `acradaasmdev` is taken globally**, the deploy fails. → **Mitigation**: ACR names are globally unique; if collision, fall back to `acradaasm<5-char-suffix>` using `uniqueString(resourceGroup().id)`. Update Bicep param + add a fallback in `main.bicep`.
- **[Trade-off] Basic SKU has no retention policy.** → Old image tags accumulate. **Mitigation**: low traffic in dev; we periodically `az acr repository delete --untagged`. Not a real cost issue under 10 GB.
- **[Risk] ACR import from GHCR fails if GHCR public visibility regresses.** → **Mitigation**: if `az acr import` fails, fall back to building locally with `--platform linux/amd64` and `az acr build` (server-side build).
- **[Risk] The deploy UAMI does not yet have `AcrPush`.** → **Mitigation**: the migration script grants this BEFORE the workflow is updated, so the first push lands cleanly. Documented in tasks.

## Migration Plan

1. **Bicep ground work** (additive, no impact): create `acr.bicep`, wire role assignments, deploy.
2. **Image migration**: `az acr import` the existing `8a210087…` tag + add `dev-latest` alias.
3. **Switch Bicep modules** (`container_apps.bicep`, `container_jobs.bicep`, `keyvault.bicep`) to drop GHCR + add ACR — single `az deployment group create` applies everything.
4. **Smoke** the backend FQDN.
5. **Update GHA workflow** (`deploy-backend.yml`) — first run after this proves end-to-end push + deploy.
6. **Tear down GHCR coupling**: delete `ghcr-pull-token` from KV, remove from `keyvault.bicep`.

**Rollback**: if step 3 fails, the old GHCR-based revisions are still present in the Container Apps revision history. `az containerapp revision activate` on the previous revision restores service while we debug; the GHCR pull credentials are still intact until step 6.

## Open Questions

- **Q1**: Do we keep `mcr.microsoft.com/k8se/quickstart:latest` as the `backendImage` default in `main.bicep`, or move it to `acradaasmdev.azurecr.io/ada-asm-backend:bootstrap`? Current preference: keep MCR placeholder so a brand-new env can `az deployment group create` without first having pushed any image to ACR; CI overrides on every real deploy. Decide before writing tasks.
- **Q2**: Should ACR adopt private endpoint + VNet integration for prod? Out of scope here, but worth flagging when prod is provisioned.
