# Design — ingest-component-from-mpn

Backed by live-probe research: `research/supplier-api-blended-research.md` (datasheet matrix + blended fields) and `research/family-inference-design.md` (category taxonomies + seed mapping). All field paths and gotchas below are evidenced there.

## Architecture overview

```
HTTP POST /components/ingest ┐
                            ├─► ComponentIngestionService.ingest(mpn, manual_overrides)
CLI ingest_component <MPN>  ┘        │
                                     ├─1─ lookup_by_mpn(mpn)            # existing service, all enabled suppliers
                                     │       └─ returns merged presentation fields + per-supplier SupplierQuote[] (now richer)
                                     ├─2─ FamilyInferenceService.resolve(quotes)   # separate from presentation merge
                                     ├─3─ DatasheetService.acquire(quotes, manufacturer)  # fallback chain → Blob (best-effort)
                                     ├─4─ build Component + blended columns + manual overrides + auto SKU
                                     ├─5─ persist: component, component_parameters, component_compliance,
                                     │            component_documents, component_cross_refs, supplier raw_payload
                                     └─6─ return created component (daily sync picks it up automatically)
```

One application service, two entrypoints (HTTP + CLI) sharing it — same pattern as the existing seed scripts vs API.

## 1. SupplierQuote enrichment + adapter fixes

`SupplierQuote` gains: `supplier_category_id`, `supplier_category_name`, `tariff_code`, `image_url`, `lifecycle_status`, `moq`, `order_multiple`, `lead_time_days`, `parameters: list[SupplierParameter]`, `compliance: list[SupplierComplianceCode]`, `raw_payload: dict`. New value objects `SupplierParameter{key,label,value,unit}` and `SupplierComplianceCode{code_type,code_value}`.

Per-adapter changes (evidenced in research):
- **DigiKey** (`digikey.py:267`): descend `Category.ChildCategories[0]` to the LEAF, capture leaf+root `CategoryId`. Use `ExactMatches[]`/MPN filter instead of first-match. Parametrics from `Parameters[]` (stable `ParameterId`). Classifications → compliance. `PhotoUrl` → image. Lead `ManufacturerLeadWeeks` (string→int×7→days). Keep enrichment endpoints (`/pricing`,`/media`,`/substitutions`) OPTIONAL/on-demand (quota: 5-7 calls/part).
- **TME** (`tme.py:284`): capture `category.id`. Parametrics need the extra `/products/parameters` call (batch by `symbols[]`). No compliance/export in V2. Token TTL 300s — cache.
- **Mouser** (`mouser.py:159`): keep localized `Category` name; map `ProductCompliance`/`TradeCompliance` (ECCN/HTS/country); `LifecycleStatus`; `Min`/`Mult`; `UnitWeightKg`. Inspect `Errors[]` for `TooManyRequests` → `SupplierRateLimitedError`.
- **Farnell** (`farnell.py:227`): send `versionInfo.versionNumber=1.4`, `responseGroup=large`; extract `tariffCode`+`displayName`+`datasheets[]`+`image`+`attributes[]` (compliance+params live here, mixed). Handle the root-key switch (`keywordSearchReturn` vs others). `prices[].to=999999999`=∞.

The lookup merge keeps presentation fields by priority but NO LONGER decides `family`.

## 2. FamilyInferenceService

Pure service, input = `list[SupplierQuote]`, output = `(family: str|None, provenance)`. Algorithm:

1. For each quote, in supplier confidence order `[digikey, tme, farnell, mouser]`, compute a candidate family by querying `component_family_rules`:
   - DigiKey/TME → `match_type='category_id'` on `supplier_category_id` (leaf first, root fallback for DigiKey).
   - Farnell → `match_type='tariff_prefix'` longest-prefix match on `tariff_code`.
   - Mouser → `match_type='name_keyword'` NFKD-normalized substring on `supplier_category_name`.
2. First confident candidate wins (signal-strength priority, inverts presentation priority).
3. No candidate → `family=None`, `needs_review=True`, log the unmapped `(supplier, signal)`.
4. Always record provenance: winning supplier, match_type, raw_category_id/name/tariff, confidence.

`component_family_rules` seeded via migration from the starter table in the research doc (DigiKey leaf ids, TME ids, Farnell HS prefixes, Mouser ES keywords for the 9 families). `name_keyword` rules loaded into memory, evaluated by normalized substring. Rules editable in DB → no redeploy. **Módulos** is under-seeded (only DigiKey/Farnell) — seed by keyword, grow from logs.

SKU prefix derives from the resolved family via a fixed `{family → prefix}` map (`Diodos→DIO`, `Transistores→TRN`, `Microcontroladores→MCU`, `Sensores→SEN`, `Condensadores→CAP`, `Resistencias→RES`, `Conectores→CON`, `Fuentes de alimentación→PWR`, `Módulos→MOD`, none→`CMP`), sequence = next free integer for that prefix.

## 3. DatasheetService (best-effort, never blocks ingest)

`acquire(quotes, manufacturer) -> ArchivedDoc | LinkOnly | None`:
1. Build candidate URL list in order: Farnell `datasheets[].url` → DigiKey `DatasheetUrl` → manufacturer pattern (`{manufacturer → url template}`: TI `ti.com/lit/ds/symlink/<part>.pdf`, onsemi `<part>-d.pdf`, Espressif, ST [mark hard]) → other suppliers' URLs.
2. For each: `httpx` GET with redirects, per-host User-Agent table (TI/Espressif any-UA; onsemi curl-UA; Mouser/DigiKey-CDN browser-UA; ST → skip/headless), retry alternate UA on 403.
3. Validate: final `Content-Type==application/pdf` AND body starts `%PDF`. Else next.
4. On first valid PDF: sha256 → upload to Blob `datasheets/<sha256>.pdf` if absent (dedup) → write `component_documents` row (blob_path, source_url, source, sha256, content_type, fetched_at).
5. No PDF → store best-known URL as link-only document, `blob_path=NULL`.

**Azure**: private container `datasheets` on a Storage Account (reuse the broker SA or a dedicated one); backend Container App managed identity gets `Storage Blob Data Contributor`. Serving: `GET /components/{id}/datasheet` (require_user) streams the blob or 302s to a short user-delegation SAS (signed via managed identity, minutes TTL). Bicep: storage module + role assignment + `DATASHEET_STORAGE_ACCOUNT`/`DATASHEET_CONTAINER` env. Local dev: Azurite or a filesystem fallback driver behind a `DatasheetStorage` protocol so tests/local don't need Azure.

## 4. Persistence

New columns on `components` (per specs). New tables: `component_parameters`, `component_compliance`, `component_documents`, `component_cross_refs`, `component_family_rules`. Per-offer `raw_payload jsonb` — store on a `supplier_offers` row or extend the existing supplier-price/stock write path; decide in tasks (lean: a `component_supplier_payloads` table `{component_id, supplier, raw_payload jsonb, fetched_at}`). All via Alembic migrations that apply+reverse cleanly.

## 5. API + CLI

- `POST /api/v1/components/ingest` → `IngestComponentRequest{mpn, ubicacion?, stock_inicial?, holded_id?, force?}` → 201 `IngestComponentResponse{component: ComponentResponse, report: IngestionReport}`. Errors reuse existing typed exceptions (`ComponentMpnNotFoundError`, `SupplierLookupUnavailableError`, `ComponentMpnAlreadyRegisteredError`). The `IngestionReport` is assembled by the service as it runs (it already has every datum) — a frontend-friendly summary, not re-derived:

```jsonc
{
  "component": { /* ComponentResponse incl. new fields */ },
  "report": {
    "status": "ok",                                  // ok | ok_with_warnings
    "mpn": "NE555P",
    "sku": "DIO-204",
    "sources_consulted":  ["mouser","digikey","tme","farnell"],
    "sources_succeeded":  ["mouser","digikey","tme"],
    "sources_contributed":["mouser","digikey"],      // whose data actually landed
    "family": {
      "inferred": "Diodos",                          // or null
      "needs_review": false,
      "decided_by": "digikey",
      "match_type": "category_id",
      "raw_category": "Single Diodes (280)",
      "confidence": 100
    },
    "datasheet": {
      "outcome": "archived",                         // archived | link_only | none
      "source": "farnell",
      "url": "https://www.farnell.com/datasheets/...pdf",
      "blob_path": "datasheets/<sha256>.pdf",        // null when link_only/none
      "size_bytes": 262144
    },
    "fields_populated": ["name","description","manufacturer","package","image_url",
                          "lifecycle_status","country_of_origin","moq","lead_time_days"],
    "fields_missing":   ["unit_weight_kg"],
    "counts": { "price_breaks": 8, "supplier_stock_rows": 3, "parameters": 12,
                "compliance_codes": 4, "cross_refs": 2, "documents": 1 },
    "manual_overrides_applied": ["location","stock"],
    "warnings": ["RS disabled (credentials missing)"]
  }
}
```

The CLI prints a human-readable rendering of the same report. The service returns `(component, report)` so both entrypoints share one assembler.
- `GET /api/v1/components/{id}/datasheet` → stream/redirect.
- `python -m app.scripts.ingest_component <MPN> [flags]` → calls the same service in a DB session, prints id / typed error code. Prod: one-off Container App Job using the backend image.

## 6. Frontend (integrated from the start)

- `ComponentEditPage` create mode: an MPN field with an "Ingestar" action that calls `POST /components/ingest`, then navigates to the created component (or pre-fills + shows what was auto-populated). TanStack hook `useIngestComponent`.
- Component detail: render `image_url`, `lifecycle_status` badge, archived datasheet link (via the protected endpoint), and a `needs_review` badge on family when empty, with an inline family picker to fix it (which can also propose a `component_family_rules` row).
- Spanish copy; English code.

## 7. Phasing (tasks order)

1. Migrations: new columns + 5 tables + seed `component_family_rules`.
2. `SupplierQuote` + value objects; adapter enrichment + category fixes (TDD per adapter with fixtures from the saved probe JSON).
3. `FamilyInferenceService` + rules repo (unit tests over the seed).
4. Lookup merge: stop merging family; carry per-supplier category signals.
5. `DatasheetService` + `DatasheetStorage` protocol (filesystem driver for tests; Blob driver for prod) + serving endpoint.
6. `ComponentIngestionService` orchestration + persistence of blended tables.
7. API endpoint + CLI script.
8. Infra: bicep storage module + RBAC + env wiring; prod Container App Job.
9. Frontend: ingest flow + detail fields + family review badge.
10. Docs: api-spec.yml, data-model.md, development_guide.md.

## Decisions / trade-offs

- **Family resolved by signal-strength, not presentation priority** — fixes the live bug where Mouser's localized name beats DigiKey's stable id. Separate service keeps the presentation merge untouched for name/price.
- **Rules in DB seed table, not code** — only the slice we stock needs mapping; grows from logged misses without redeploy.
- **Datasheet archival best-effort** — never blocks component creation; link-only fallback. Only Farnell gives reliably-direct PDFs server-side; ST needs headless (deferred — link-only for ST parts initially).
- **DigiKey enrichment endpoints on-demand, not per-sync** — quota (5-7 calls/part, ~150 parts/day cap). Ingest does the full picture once; daily sync stays 1 call (price/stock/lifecycle).
- **`raw_payload` JSONB** — preserves dozens of doc-only fields cheaply; avoids schema churn for fields we may surface later.
