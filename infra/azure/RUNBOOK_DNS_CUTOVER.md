# DNS cutover runbook — `ada.tierra.audio`

One-time procedure executed during the prod cutover. After this, `ada.tierra.audio` and `api.ada.tierra.audio` serve from the new Azure infra and the legacy `134.0.10.173` A record is gone.

## Pre-cutover (24h before)

1. **Lower the TTL on the existing `ada` A record to 300s.** This bounds the worst-case cache lifetime once we delete it tomorrow.
   ```bash
   az network dns record-set a update \
     --resource-group rg-tierra-audio-dns \
     --zone-name tierra.audio \
     --name ada \
     --set "ttl=300"
   ```
2. **Confirm the prod stack is healthy in `dev`:**
   - `https://ada-dev.tierra.audio` loads the SPA.
   - `https://api.ada-dev.tierra.audio/api/v1/health` returns 200.
   - Application Insights shows live traces.
3. **Provision prod** with `legacyARecordCleanup=false`:
   ```bash
   az deployment group create \
     --resource-group rg-ada-asm-prod \
     --template-file infra/azure/main.bicep \
     --parameters infra/azure/parameters.prod.bicepparam \
     --parameters postgresAdminPassword=$(az keyvault secret show --vault-name kv-ada-asm-prod --name postgres-admin-password --query value -o tsv)
   ```
   This creates the prod Container Apps + Postgres + Redis + SWA + Key Vault + DNS records (the `ada` CNAME is NOT created yet because the legacy A record still exists at that name).
4. **Trigger the first prod backend + frontend deploys** via `Actions → deploy-backend → Run workflow → environment=prod` and likewise for `deploy-frontend`.
5. **Seed the prod admin user**:
   ```bash
   az containerapp job start --resource-group rg-ada-asm-prod --name caj-ada-asm-prod-seed-admin
   ```
6. **Smoke verify** with the temporary URL on the backend Container App (visible via `az containerapp show … --query properties.configuration.ingress.fqdn`).

## Cutover (T=0)

1. **Re-apply the Bicep with `legacyARecordCleanup=true`** — this runs the deployment script that deletes the legacy A record AND creates the `ada` CNAME pointing at SWA:
   ```bash
   az deployment group create \
     --resource-group rg-ada-asm-prod \
     --template-file infra/azure/main.bicep \
     --parameters infra/azure/parameters.prod.bicepparam \
     --parameters postgresAdminPassword=$(az keyvault secret show --vault-name kv-ada-asm-prod --name postgres-admin-password --query value -o tsv) \
     --parameters legacyARecordCleanup=true
   ```
2. **Wait for the SWA managed cert to issue.** The `asuid.ada` TXT record was already created in step 3 of the pre-cutover; once Azure sees both that TXT and the CNAME, it provisions the cert (~5-15 min).
   ```bash
   az staticwebapp hostname show \
     --name stapp-ada-asm-prod \
     --hostname ada.tierra.audio \
     --query "{state:status, error:error}"
   # Wait until state == 'Ready'.
   ```
3. **Similarly wait for the ACA managed cert** on `api.ada.tierra.audio`.

## Verification

```bash
# DNS propagation from multiple resolvers
for r in 1.1.1.1 8.8.8.8 9.9.9.9 80.58.61.250; do
  echo "=== $r ==="
  dig @$r ada.tierra.audio +short
  dig @$r api.ada.tierra.audio +short
done

# Expect both to return CNAMEs into the azurestaticapps.net / azurecontainerapps.io
# default hostnames. No 134.0.10.173 anywhere.
```

```bash
# HTTPS smoke tests
curl -fsS -o /dev/null -w "%{http_code}\n" https://ada.tierra.audio/
curl -fsS -o /dev/null -w "%{http_code}\n" https://api.ada.tierra.audio/api/v1/health
# Both should return 200.

# Cert chain
openssl s_client -connect ada.tierra.audio:443 -servername ada.tierra.audio </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -subject -issuer
```

## Rollback

If the cutover fails (e.g. cert won't issue, SPA won't load), restore the legacy A record:

```bash
az network dns record-set a add-record \
  --resource-group rg-tierra-audio-dns \
  --zone-name tierra.audio \
  --record-set-name ada \
  --ipv4-address 134.0.10.173

az network dns record-set cname delete \
  --resource-group rg-tierra-audio-dns \
  --zone-name tierra.audio \
  --name ada --yes
```

Worst-case downtime is one TTL window (300s, lowered in the pre-cutover).

## Post-cutover

1. Reset TTLs to a sane long value (3600s) on the new CNAMEs:
   ```bash
   az network dns record-set cname update --resource-group rg-tierra-audio-dns --zone-name tierra.audio --name ada --set ttl=3600
   az network dns record-set cname update --resource-group rg-tierra-audio-dns --zone-name tierra.audio --name api.ada --set ttl=3600
   ```
2. Monitor App Insights dashboard `dashboard-ada-asm-prod` for the next 24h.
3. Confirm the next 03:00 UTC daily sync fires successfully via `GET /api/v1/supplier-sync/runs?supplier=mouser&limit=1` (or by querying `supplier_sync_runs` directly in Postgres).
