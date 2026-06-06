## Context

ADA ASM tracks electronic components with `supplier_prices` and `supplier_stocks` tables that already model historical snapshots, but these are populated by hand today. The catalogue has grown enough that hand-entering five suppliers' worth of prices per component is no longer viable. Five suppliers are fixed by procurement policy: Mouser, DigiKey, TME, Farnell, RS Online. The first four expose self-serve free APIs (key by web form, no human approval). RS Online requires a sales-rep approval to receive an App ID, so it must be deferrable behind a feature flag without a code change.

Celery and Celery Beat are already wired (`backend/app/infrastructure/celery_app.py`) with `acks_late=True`, `worker_prefetch_multiplier=1`, `task_default_queue="default"`, and an empty `beat_schedule={}`. The `celery_worker` and `celery_beat` containers are running in `docker-compose.yml`. Redis is already running (port 16379) and used as both the Celery broker and result backend; we'll reuse it for the cache and the per-supplier token-bucket rate limiter.

Operators also need an on-demand way to pre-fill the "Nuevo componente" form when they type an MPN. The frontend integration is out of scope for this change — we only ship the backend endpoint.

## Goals / Non-Goals

**Goals:**

- A single Protocol `SupplierAdapter` so adding a sixth supplier later is a one-file change.
- A daily Celery Beat job that walks the existing catalogue per enabled supplier, upserts append-only history rows, and never silently fails (every error is recorded in `supplier_sync_errors`).
- A synchronous `GET /api/v1/components/lookup?mpn=` endpoint that merges fields from all enabled suppliers in priority order to pre-fill a new component, with a short Redis cache so reopening the form doesn't re-hammer the APIs.
- Per-supplier feature flag (`SUPPLIER_SYNC_ENABLED_SUPPLIERS`) so RS Online ships disabled and is toggled on via env var when credentials arrive.
- All prices normalised to EUR at storage time (with the original price + currency preserved for traceability).

**Non-Goals:**

- No frontend work. The form pre-fill UI is a follow-up US.
- No deep BOM-aware sync (this change syncs leaf components; modules/projects don't gain a new sync surface).
- No automated retention/pruning of `supplier_sync_errors` (a separate cron is a follow-up).
- No support for suppliers beyond the five fixed ones.
- No image asset ingestion from supplier APIs.
- No realtime stock updates / webhooks — daily batch is enough for the procurement cadence.

## Decisions

### Adapter Protocol (one Protocol, five implementations)

Defined a single `SupplierAdapter` Protocol in `app/domain/repositories/supplier_adapter.py`:

```python
class SupplierAdapter(Protocol):
    code: str  # 'mouser' | 'digikey' | 'tme' | 'farnell' | 'rs'

    async def fetch_by_mpn(self, mpn: str) -> SupplierQuote | None: ...
```

Each adapter lives in `app/infrastructure/suppliers/{supplier}.py` and is registered through a simple factory `app/infrastructure/suppliers/registry.py` that reads `SUPPLIER_SYNC_ENABLED_SUPPLIERS` from settings and returns only the configured + enabled instances.

**Alternative considered**: ABC base class with shared HTTP plumbing. Rejected because each supplier's auth flow is different enough (DigiKey OAuth2 token refresh vs. Mouser query-string key vs. TME HMAC-signed POST vs. Farnell GET param) that the "shared" base would be 80% per-supplier overrides. A thin Protocol + per-supplier modules is simpler.

### MPN as canonical key (no per-supplier SKU index)

Our `Component.mpn` column is already the canonical identifier. We do **not** maintain a cross-reference table mapping `(component_id, supplier) → supplier_sku`. Instead, every adapter accepts a raw MPN and queries its native field:

| Supplier | Search field | MPN field in response |
|---|---|---|
| Mouser | `SearchByPartRequest.mouserPartNumber` (the field name is misleading — Mouser's API also matches by MPN) | `ManufacturerPartNumber` |
| DigiKey | KeywordSearch v4 `keywords` or `manufacturerProductNumber` | `ManufacturerProductNumber` |
| TME | `Products/Search` `SearchPlain` | `OriginalSymbol` (NOT `Symbol`, which is TME's own SKU) |
| Farnell | `keywordSearch` `term=any:<MPN>` | `translatedManufacturerPartNumber` |
| RS | `searchTerm=<MPN>` | `mpn` |

Supplier SKU is captured on each `supplier_prices` row (`supplier_sku` column already exists) for traceability, but is not used as a lookup key.

**Alternative considered**: maintaining a `component_supplier_sku` join table. Rejected because every supplier's MPN search returns the SKU as a side-effect, so the join table would be a derived cache with no source-of-truth benefit, and would force a backfill migration.

### Daily sync as Beat task + chord-fanout

The Beat schedule registers a single entry:

```
'supplier-sync-daily': {
  'task': 'app.infrastructure.tasks.supplier_sync.run_daily_sync',
  'schedule': crontab(hour=settings.supplier_sync_daily_hour_utc, minute=0),
}
```

`run_daily_sync` is the orchestrator: for each enabled supplier, it creates a `supplier_sync_runs` row (`status='running'`), splits the component IDs into chunks of 50, dispatches one `sync_supplier_chunk(supplier, component_ids, run_id)` per chunk, and uses a Celery `chord` to finalise the run row when all sub-tasks complete.

**Alternative considered**: one Beat entry per supplier (5 entries). Rejected because it makes per-supplier failures harder to correlate into a single "daily run" and complicates the admin view.

**Alternative considered**: synchronous loop inside one task. Rejected because a single supplier outage would stall the whole job, and Celery's per-chunk retry semantics (`acks_late=True`) are exactly what we want for unreliable third-party APIs.

### Rate limiting via Redis token-bucket (shared module)

A small helper at `app/infrastructure/rate_limit.py`:

```python
async def acquire(bucket: str, limit_per_minute: int) -> None: ...
```

Implemented as a Lua script (atomic check-and-decrement) against keys `rate_limit:{bucket}`. Each adapter calls `acquire(f"supplier:{self.code}", supplier_limit)` before every HTTP call. If quota is exhausted, the helper sleeps until the next refill window (max 60s) — for the lookup endpoint, this means a worst-case ~60s latency that we deem acceptable because (a) cache hits dominate and (b) rate limits are generous enough that hitting them during a manual lookup means something is very wrong.

**Alternative considered**: per-process in-memory limiter. Rejected because the daily sync fans out across multiple Celery worker processes that must share quota.

### Lookup endpoint: progressive merge, not first-hit

The endpoint walks `SUPPLIER_LOOKUP_PRIORITY` and merges every successful quote. The merge rule is "first non-null wins per field" — meaning a later supplier can fill in a `package` or `datasheet_url` that the higher-priority supplier left null. This gives us the best possible pre-filled form even when one supplier has partial data.

**Alternative considered**: stop at first hit. Rejected because in practice Mouser sometimes has the price but DigiKey has the better datasheet URL; an operator who has to copy-paste the missing fields anyway defeats the purpose.

### EUR normalisation with cached daily FX

Adapters that return non-EUR prices (Mouser → USD, sometimes DigiKey → USD/GBP) convert at fetch time using a daily-cached FX rate stored in Redis under `fx:{ccy}:{date_iso}` (TTL 36h). The original price and currency are preserved on the `supplier_prices` row (`price_original`, `currency_original` columns to be added) so re-conversion later is possible.

If the FX rate cannot be fetched (third-party outage), the row is stored with `price_eur=NULL` and the original fields populated. The daily sync logs a `FX_UNAVAILABLE` error per affected component into `supplier_sync_errors`.

**FX source**: the European Central Bank daily reference rates (`https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`) — free, no auth, deterministic schema. Cached for ~24h.

### Redis cache for lookup endpoint

Key: `supplier_lookup:{lower(mpn)}`, value: gzipped JSON of the merged `LookupResponse`, TTL `SUPPLIER_LOOKUP_CACHE_TTL_SECONDS` (default 900s = 15 min). `?force_refresh=true` bypasses. This keeps the form responsive when the operator opens/closes it repeatedly while typing.

**Cache invalidation**: none beyond TTL — we accept that the operator may see a 15-minute-old snapshot, which is well within the staleness window of a "pre-fill the form" use case.

## Risks / Trade-offs

- **DigiKey 1000 req/day cap** → A full catalogue sync that exceeds 1000 components will exhaust the quota. Mitigation: chunk size of 50 + per-supplier daily cap awareness; if the catalogue grows past 1000, we request a quota increase from DigiKey (their FAQ says larger amounts are sales-approved). Track via `supplier_sync_runs.components_processed`.
- **RS Online has no self-serve key** → Ships disabled. Mitigation: feature flag respects `SUPPLIER_SYNC_ENABLED_SUPPLIERS`; flipping it on once the App ID arrives is a config change, no redeploy of code.
- **Supplier MPN ambiguity** → Same MPN can resolve to two distinct parts at two suppliers (suffix variants, packaging). Mitigation: the lookup endpoint returns each supplier's quote intact in `supplier_data[]`, so a disambiguation UI later can let the operator pick; the merged `fields` use first-non-null priority for now.
- **Currency conversion drift** → Daily-rounded FX rates cause sub-1% drift vs. live rates. Mitigation: documented behaviour; preserve original price + currency for re-conversion.
- **Celery chord finalisation hangs** → If one chunk task is killed (OOM, worker restart) the chord callback never fires and the run row stays in `status='running'`. Mitigation: a per-run timestamp watchdog in the same task (set a soft `time_limit` of 30 min per chunk, hard 45 min) plus a follow-up cleanup task (out of scope here, tracked separately).
- **Adapter version drift** → Suppliers occasionally change response shapes (Mouser added v2 fields in 2024, DigiKey moved from v3 to v4). Mitigation: each adapter is its own module with its own fixtures; a contract-test suite per adapter against frozen fixtures catches regressions.
- **Lookup endpoint latency under cache miss** → Worst case = 5 sequential API calls. At ~300ms each = ~1.5s. Mitigation: short cache TTL (15 min) covers the "form open-close-open" pattern; we don't parallelise the merge because the priority semantics demand sequential traversal (and parallelising would worsen burst rate-limit behaviour anyway).

## Migration Plan

1. Migration `XXXX_supplier_sync_tables.py`: add `supplier_sync_runs`, `supplier_sync_errors`, and `components.last_supplier_sync_at`, `supplier_prices.price_original` (numeric(12,4) nullable), `supplier_prices.currency_original` (varchar(3) nullable). Reversible.
2. Deploy backend with `SUPPLIER_SYNC_ENABLED_SUPPLIERS=""` (empty list — Beat task runs but no-ops). Confirms Beat wiring without touching external APIs.
3. Add Mouser key to env, set `SUPPLIER_SYNC_ENABLED_SUPPLIERS=mouser`. Run `POST /api/v1/supplier-sync/runs?supplier=mouser` and inspect `GET /supplier-sync/runs/{id}`. If clean, leave it on for the next daily cycle.
4. Repeat step 3 for DigiKey, TME, Farnell one at a time. Each onboarding produces a single supplier run we can inspect before adding the next.
5. RS Online: deferred until App ID arrives. Toggling is a single env var change.

**Rollback**: set `SUPPLIER_SYNC_ENABLED_SUPPLIERS=""` to stop syncs without redeploying. The Beat schedule entry can also be removed by reverting the `celery_app.py` change. The migration is fully reversible.

## Open Questions

- **DigiKey OAuth2 client credentials vs. authorization code flow?** v4 supports both. Decision: use client credentials (machine-to-machine), refresh token cached in Redis.
- **Should `supplier_sync_errors` rows be retained forever?** Initial design: yes, retention is a follow-up US. If volume becomes a concern, add a daily pruning task.
- **EUR FX source fallback?** ECB only. If ECB goes down, we accept `price_eur=NULL`. A secondary source (e.g. exchangerate.host) could be added later.
- **Should the lookup endpoint surface partial-failure info to the FE?** The `sources_consulted` vs. `sources_succeeded` arrays already communicate this; the FE can render a "1 of 4 suppliers responded" hint if it wants to.
