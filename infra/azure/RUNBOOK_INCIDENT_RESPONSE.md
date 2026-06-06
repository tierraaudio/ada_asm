# Incident response runbook

## When the 5xx alert fires

The `[prod] Backend 5xx rate above 5%` alert (`alert-ada-asm-prod-5xx-rate`) routes to `ops@tierra.audio` when the backend HTTP error rate exceeds 5% over a 5-minute window. Treat as **Severity 1**.

### Triage (first 5 minutes)

1. **Open the dashboard** `dashboard-ada-asm-prod` in the Azure portal — pinned to the resource group.
2. **Identify the failing route(s)**:
   ```kusto
   requests
   | where cloud_RoleName == 'ada-asm-backend'
   | where timestamp > ago(15m)
   | where toint(resultCode) >= 500
   | summarize count() by name
   | order by count_ desc
   ```
3. **Inspect the top exception**:
   ```kusto
   exceptions
   | where cloud_RoleName == 'ada-asm-backend'
   | where timestamp > ago(15m)
   | summarize count() by type, outerMessage
   | order by count_ desc
   ```
4. **Correlate with a recent deploy**:
   ```bash
   az containerapp revision list \
     --resource-group rg-ada-asm-prod \
     --name ca-ada-asm-prod-backend \
     --query "[].{name:name, created:properties.createdTime, traffic:properties.trafficWeight, active:properties.active}" \
     --output table
   ```
   If the spike correlates with the most recent revision, **roll back immediately** (see below).

### Common failure modes

| Symptom | Likely cause | Action |
| --- | --- | --- |
| All 5xx, "no available connections" | Postgres connection-pool exhaustion | Restart backend revision → reset pool. If persistent, scale Postgres to next SKU. |
| Sporadic 503 from `/api/v1/components/lookup` | One supplier API is timing out | Verify in `GET /api/v1/supplier-sync/runs?supplier=<code>` — the typed `SupplierTimeoutError` should be visible. Lookup is resilient (skips the bad supplier); 503 means EVERY supplier failed. |
| 500 from random routes after a deploy | Migration partially failed | Check `caj-ada-asm-prod-migrate` execution history. The deploy workflow gates on migration success, so this usually means a manual `az containerapp update` skipped the gate. |
| 500 from `/api/v1/auth/*` | JWT secret rotation gone wrong | Verify `JWT_SECRET` in Key Vault is non-empty and matches what `kv-ada-asm-prod` returns. Restart backend. |
| 503 from everywhere | Container App scale rule misfired | `az containerapp revision list` to see whether `replicas: 0`. Scale rule should pin `minReplicas=1` on prod — check Bicep wasn't accidentally redeployed with the dev params. |

### Rollback procedure

If the spike correlates with the most recent backend deploy:

```bash
# Find the previous active revision
PREVIOUS=$(az containerapp revision list \
  --resource-group rg-ada-asm-prod \
  --name ca-ada-asm-prod-backend \
  --query "sort_by([?properties.active==\`true\`], &properties.createdTime)[-2].name" \
  -o tsv)

# Flip 100% traffic to it
az containerapp ingress traffic set \
  --resource-group rg-ada-asm-prod \
  --name ca-ada-asm-prod-backend \
  --revision-weight "$PREVIOUS=100"
```

Verify the alert clears within the next evaluation window (5 min).

### Escalation

If the rollback doesn't resolve and the on-call can't identify the cause within 30 minutes:

1. Update the [Tierra Audio status page]() (placeholder — page not built yet).
2. Page Jon (admin@tierra.audio / `+34 XXX XXX XXX`).
3. Consider scaling Postgres / Redis to next SKU as a last-resort mitigation.

## Other alert types (future)

This runbook will grow as we add more alerts:
- Daily sync failure (no successful run in 25h)
- Redis cache hit ratio degradation (sustained <80%)
- Postgres CPU > 80% for 15 min

## Incident log

| Date | Severity | Root cause | Resolution time | Notes |
| --- | --- | --- | --- | --- |
| _(empty — first prod entry will go here)_ | | | | |
