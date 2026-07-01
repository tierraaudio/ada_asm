<!--
scope:
  backend: true
  frontend: true
design-linked: false
-->

# Tasks — ingest-component-from-mpn

TDD throughout: write the failing test first, then the implementation. Reuse the saved probe JSON (`/tmp/*.json` captured during research, re-fetch if gone) as adapter fixtures. Baby steps — one task at a time.

## 1. Persistence: migrations + seed

- [x] 1.1 Alembic migration: add blended scalar columns to `components` (`lifecycle_status`, `last_buy_date`, `discontinued`, `end_of_life`, `moq`, `order_multiple`, `lead_time_days`, `unit_weight_kg`, `image_url`). Applies + reverses cleanly.
- [x] 1.2 Alembic migration: add family-provenance columns to `components` (`family_inferred_supplier`, `family_inferred_match_type`, `raw_category_id`, `raw_category_name`, `raw_tariff_code`, `family_confidence`, `family_needs_review`).
- [x] 1.3 Alembic migration: create `component_parameters`, `component_compliance`, `component_documents`, `component_cross_refs` tables with FKs + indexes.
- [x] 1.4 Alembic migration: create `component_supplier_payloads` (`component_id`, `supplier`, `raw_payload jsonb`, `fetched_at`).
- [x] 1.5 Alembic migration: create `component_family_rules` (`supplier`, `match_type`, `match_value`, `family`, `confidence`, `priority`, `enabled`, `notes`, unique index).
- [x] 1.6 Seed `component_family_rules` from the research starter table (DigiKey leaf ids, TME ids, Farnell HS prefixes, Mouser ES keywords for the 9 families). Idempotent seed.
- [x] 1.7 Update SQLAlchemy models + domain entities for all new columns/tables.

## 2. SupplierQuote enrichment + adapter fixes (TDD per adapter)

- [x] 2.1 Extend `SupplierQuote` with new fields + add `SupplierParameter` and `SupplierComplianceCode` value objects. Unit test the dataclasses.
- [x] 2.2 DigiKey adapter: descend `ChildCategories` to leaf, capture leaf+root `CategoryId`; switch first-match → `ExactMatches`/MPN filter. Test with `1N4148W` vs `2N7002` fixtures (distinct category ids).
- [x] 2.3 DigiKey adapter: extract parametrics (`Parameters[]`), compliance (`Classifications`), `PhotoUrl`, lifecycle, `Min`/lead-weeks→days, `raw_payload`. Tests.
- [x] 2.4 TME adapter: capture `category.id`; map lifecycle/moq/multiples/weight; `raw_payload`. Tests. (Parametrics via `/products/parameters` — optional, behind a flag; test the call shape.)
- [x] 2.5 Mouser adapter: keep localized category name; map compliance (ECCN/HTS/country), lifecycle, `Min`/`Mult`, `UnitWeightKg`, image; inspect `Errors[]` → `SupplierRateLimitedError`. Tests.
- [x] 2.6 Farnell adapter: send `versionNumber=1.4`+`responseGroup=large`; extract `tariffCode`+`displayName`+`datasheets[]`+image+`attributes[]` (compliance+params); handle root-key switch; `prices[].to` upper bound. Tests with the datasheet-bearing fixtures (LM358N etc.).

## 3. Family inference

- [x] 3.1 `component_family_rules` repository (lookup by supplier+match_type, load name_keyword rules into memory). Unit tests.
- [x] 3.2 NFKD-normalized keyword matcher (case+accent-insensitive substring). Unit tests.
- [x] 3.3 `FamilyInferenceService.resolve(quotes)`: signal-strength order, first-confident-wins, provenance, `needs_review` + log on miss. Unit tests over the seeded rules covering all 9 families + the BME280 conflict + no-match.
- [x] 3.4 `{family → SKU prefix}` map + sequence generator. Unit tests.

## 4. Lookup merge change

- [x] 4.1 Stop merging `family`/`family_hint` by presentation priority in `_merge_fields`; carry per-supplier `supplier_category_id`/`supplier_category_name`/`tariff_code` into `supplier_data[]`. Update `LookupResponse` schema. Tests assert family no longer decided by Mouser priority.

## 5. Datasheet archival

- [x] 5.1 `DatasheetStorage` protocol + filesystem driver (tests/local) + Azure Blob driver (managed identity, sha256 dedup). Unit tests on the filesystem driver.
- [x] 5.2 `DatasheetService.acquire`: candidate URL ordering (Farnell→DigiKey→manufacturer pattern→others), per-host UA table, redirects, `Content-Type==application/pdf` + `%PDF` magic-byte validation, alternate-UA retry on 403. Unit tests with mocked HTTP (respx) covering: valid PDF, HTML interstitial, 403-then-UA-retry, no-PDF link-only.
- [x] 5.3 Persist `component_documents` row (blob_path/source/sha256/...) on success; link-only on miss. Tests.
- [x] 5.4 `GET /api/v1/components/{id}/datasheet` endpoint (require_user): stream blob or 302 short SAS. Integration tests: 200 with PDF, 401 unauth, 404 no datasheet.

## 6. Ingestion service

- [x] 6.1 `ComponentIngestionService.ingest(mpn, overrides)`: orchestrate lookup→family→datasheet→build Component (blended cols + auto SKU + manual overrides)→persist component + parameters + compliance + documents + cross_refs + raw payloads. Returns `(component, IngestionReport)`. Unit/integration tests with patched adapters.
- [x] 6.2 Assemble the `IngestionReport` as the service runs (status, sources_consulted/succeeded/contributed, family block, datasheet block, fields_populated/missing, counts, manual_overrides_applied, warnings). Unit test the report mirrors what was stored (never over-claims).
- [x] 6.3 Duplicate-MPN guard (409 unless `force`); 404 no-match; 502 all-unavailable. Tests.
- [x] 6.3 Verify the ingested component is visible to the daily sync path (integration test: ingest → run sync logic → new supplier_prices/stocks rows).

## 7. API + CLI

- [x] 7.1 `POST /api/v1/components/ingest` router + `IngestComponentRequest` + `IngestComponentResponse{component, report}` schemas, wired to the service. Integration tests: 201 happy returns component+report, 400/401/404/409/502, manual-override application, report fields present.
- [x] 7.2 `python -m app.scripts.ingest_component <MPN> [--ubicacion --stock-inicial --holded-id --force]`: prints a human-readable rendering of the report. Tests: happy exit 0 + id + report summary, typed-error non-zero.

## 8. Infra (Azure)

- [x] 8.1 Bicep: storage module (private `datasheets` container) — reuse broker SA or dedicated; output account/container.
- [x] 8.2 Bicep: `Storage Blob Data Contributor` role for the backend Container App managed identity; env vars `DATASHEET_STORAGE_ACCOUNT`/`DATASHEET_CONTAINER`.
- [x] 8.3 Document/wire a prod one-off Container App Job for `ingest_component` (manual trigger).

## 9. Frontend (integrated from the start)

- [x] 9.1 `useIngestComponent` TanStack mutation hook + API client method. Tests.
- [x] 9.2 `ComponentEditPage` create mode: MPN field + "Ingestar" action → POST → navigate/prefill with what was auto-populated. Component tests (success, 404 not-found, 409 duplicate).
- [x] 9.3 Component detail: render `image_url`, `lifecycle_status` badge, archived datasheet link (protected endpoint), `family_needs_review` badge + inline family picker. Tests.

## 10. Documentation

- [x] 10.1 `api-spec.yml`: add `/components/ingest` (with `IngestComponentResponse{component, report}` + `IngestionReport` schema), `/components/{id}/datasheet`, new component fields, new schemas.
- [x] 10.2 `data-model.md`: document new columns + the 5 new tables + family-inference model.
- [x] 10.3 `development_guide.md`: ingest CLI usage (local docker exec + prod job), datasheet storage env vars, family-rules seeding/growing.

## 11. Integration validation

- [x] 11.1 Rebuild local stack; ingest a real MPN end-to-end (e.g. `LM358N` — has a Farnell datasheet); verify component created, family inferred, datasheet archived+served, blended fields populated, and it appears in a subsequent sync.
