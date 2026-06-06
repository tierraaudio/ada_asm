## Why

Components already model historical `supplier_prices` and `supplier_stocks`, but nothing populates them — an operator must hand-enter every supplier price and stock level, which is unsustainable as the catalogue grows. We have a fixed set of five suppliers (Mouser, DigiKey, TME, Farnell, RS Online), four of which offer self-serve free APIs we can wire today; the fifth (RS) needs a sales-rep approval but should ship behind a feature flag so we can switch it on without code changes. Additionally, when an operator creates a new component, they should be able to type an MPN and have the form pre-filled from whichever supplier knows the part — eliminating the typical "open five tabs, copy datasheet URL, copy package, copy price-break" ritual.

This change introduces an adapter pattern per supplier, a daily Celery sync of the existing catalogue, and an on-demand `GET /components/lookup?mpn=` endpoint that merges fields from all suppliers in priority order. All five Celery primitives (`celery_worker`, `celery_beat`, broker, backend) are already running — the scheduler's `beat_schedule` is empty and ready to receive the new task.

## What Changes

- **NEW** adapter Protocol `SupplierAdapter` + per-supplier modules in `app/infrastructure/suppliers/` (Mouser, DigiKey, TME, Farnell, RS).
- **NEW** value object `SupplierQuote` with normalised fields (manufacturer, name, datasheet_url, package, stock, price_breaks in EUR, supplier_sku, supplier_product_url, last_seen_at).
- **NEW** Celery Beat job `app.infrastructure.tasks.supplier_sync.run_daily_sync` scheduled at `0 ${SUPPLIER_SYNC_DAILY_HOUR_UTC} * * *` (default 03:00 UTC). Fans out per-supplier sub-tasks that walk components in chunks, call `fetch_by_mpn`, and upsert append-only history rows.
- **NEW** endpoint `GET /api/v1/components/lookup?mpn=...&force_refresh=...` — walks suppliers in `SUPPLIER_LOOKUP_PRIORITY` order (default Mouser → DigiKey → TME → Farnell → RS), merges fields progressively (later suppliers only fill nulls), preserves each supplier's raw quote in `supplier_data[]`. Redis-cached for 15 min.
- **NEW** tables `supplier_sync_runs` (per-run audit telemetry) and `supplier_sync_errors` (per-component failures).
- **NEW** admin endpoints `GET /api/v1/supplier-sync/runs`, `GET /api/v1/supplier-sync/runs/{id}/errors`, `POST /api/v1/supplier-sync/runs?supplier=...`.
- **NEW** Redis-backed token-bucket rate limiter at `app/infrastructure/rate_limit.py` shared by all adapters.
- **NEW** settings: per-supplier credentials, `SUPPLIER_SYNC_ENABLED_SUPPLIERS` (default `mouser,digikey,tme,farnell` — RS off), `SUPPLIER_SYNC_DAILY_HOUR_UTC`, `SUPPLIER_LOOKUP_CACHE_TTL_SECONDS`, `SUPPLIER_LOOKUP_PRIORITY`.
- No frontend work in this change. The `/components/new` form pre-fill integration is a follow-up US.

## Capabilities

### New Capabilities
- `supplier-integration`: adapter pattern per supplier (Mouser/DigiKey/TME/Farnell/RS) exposing a common `fetch_by_mpn` interface, with EUR price normalisation, per-supplier rate limiting, and feature-flag enable/disable. Also covers the `SupplierQuote` value object and the MPN field mapping table (each supplier names the MPN differently in its API).
- `supplier-sync-cron`: daily Celery Beat job that iterates the existing catalogue per enabled supplier, upserts append-only `supplier_prices` + `supplier_stocks` history rows, captures per-run telemetry in `supplier_sync_runs`, per-component errors in `supplier_sync_errors`, and exposes admin endpoints to inspect runs and trigger ad-hoc syncs.
- `component-mpn-lookup`: synchronous `GET /api/v1/components/lookup?mpn=` endpoint that walks suppliers in priority order, merges fields progressively, returns a single payload to pre-fill the "Nuevo componente" form, and caches results in Redis for 15 min.

### Modified Capabilities
- `component-catalog`: existing `supplier_prices` and `supplier_stocks` tables are now written to automatically by the daily sync (append-only history preserved). `Component.last_supplier_sync_at` is the new column used to record the latest successful sync. No breaking changes to existing endpoints.

## Impact

- **Backend code**:
  - New: `app/infrastructure/suppliers/{base,mouser,digikey,tme,farnell,rs}.py`, `app/infrastructure/rate_limit.py`, `app/infrastructure/tasks/supplier_sync.py`, `app/domain/entities/supplier_quote.py`, `app/domain/entities/supplier_sync_run.py`, `app/domain/entities/supplier_sync_error.py`, `app/domain/repositories/supplier_adapter.py`, `app/infrastructure/repositories/supplier_sync_run_repository.py`, `app/api/v1/routers/components_lookup.py`, `app/api/v1/routers/supplier_sync.py`, `app/api/v1/schemas/lookup.py`, `app/api/v1/schemas/supplier_sync.py`.
  - Modified: `app/infrastructure/celery_app.py` (add `beat_schedule` entry), `app/core/config.py` (new env vars), `app/main.py` (mount routers), `app/infrastructure/db/models/component.py` (add `last_supplier_sync_at`).
- **Database**: 2 new tables (`supplier_sync_runs`, `supplier_sync_errors`), 1 new column (`components.last_supplier_sync_at`). Alembic migration up + down.
- **External APIs**: Mouser Search API, DigiKey Product Information v4, TME Products/Search, Farnell keywordSearch — all called from inside `celery_worker`. RS Online behind feature flag until App ID arrives.
- **Infrastructure**: Celery `beat_schedule` populated for the first time (until now empty). Redis used for cache + token buckets.
- **Docs**: `data-model.md` (new entities), `api-spec.yml` (4 new endpoints + schemas), `development_guide.md` (supplier sync section + new env vars table).
- **Tests**: pytest 80% gate. New `tests/fixtures/suppliers/{supplier}/by_mpn/*.json` fixture set per adapter.
- **No frontend changes** in this US.
