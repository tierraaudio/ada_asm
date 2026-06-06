## ADDED Requirements

### Requirement: The system exposes a pluggable SupplierAdapter Protocol

The system SHALL define a `SupplierAdapter` Protocol in `app/domain/repositories/supplier_adapter.py` with a stable `code: str` attribute (one of `"mouser" | "digikey" | "tme" | "farnell" | "rs"`) and an async method `fetch_by_mpn(mpn: str) -> SupplierQuote | None`. Each supplier SHALL ship an implementation in `app/infrastructure/suppliers/<supplier>.py`. A registry at `app/infrastructure/suppliers/registry.py` SHALL return only the adapters that are both configured (credentials present) AND enabled via `SUPPLIER_SYNC_ENABLED_SUPPLIERS`.

#### Scenario: Adapter without credentials is silently skipped

- **WHEN** the registry is invoked with `SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser,rs"` but `RS_API_KEY` is not set
- **THEN** the registry returns only the Mouser adapter
- **AND** the backend logs an INFO line `supplier.rs.skipped reason=missing_credentials`

#### Scenario: Adapter disabled by flag is not returned

- **WHEN** `MOUSER_API_KEY` is set but `SUPPLIER_SYNC_ENABLED_SUPPLIERS="digikey,tme"`
- **THEN** the registry does not return the Mouser adapter

### Requirement: Adapters return a normalised SupplierQuote value object

The system SHALL define `SupplierQuote` in `app/domain/entities/supplier_quote.py` with fields: `supplier: str`, `mpn: str`, `manufacturer: str | None`, `name: str | None`, `description: str | None`, `family_hint: str | None`, `datasheet_url: str | None`, `package: str | None`, `stock: int | None`, `price_breaks: list[SupplierPriceBreak]`, `supplier_sku: str | None`, `supplier_product_url: str | None`, `last_seen_at: datetime`. `SupplierPriceBreak` SHALL contain `quantity: int`, `price_eur: Decimal | None`, `price_original: Decimal`, `currency_original: str` (ISO 4217). Adapters MUST return `None` (not raise) when the supplier responds with no match for the queried MPN.

#### Scenario: Adapter returns None on supplier 404

- **WHEN** an adapter calls its supplier API and the supplier returns "no results"
- **THEN** `fetch_by_mpn` returns `None`
- **AND** no exception is raised

#### Scenario: Adapter normalises prices to EUR using cached FX

- **WHEN** the supplier returns a price of `5.00 USD` and the cached EUR/USD daily rate is `0.92`
- **THEN** the returned `SupplierPriceBreak` has `price_eur = 4.60`, `price_original = 5.00`, `currency_original = "USD"`

#### Scenario: Adapter preserves original price when FX is unavailable

- **WHEN** the supplier returns a price in USD and the FX cache is empty AND the FX source is unreachable
- **THEN** the returned `SupplierPriceBreak` has `price_eur = None`, `price_original` and `currency_original` populated

### Requirement: Each adapter resolves the MPN using the supplier's native field

The system's adapters SHALL search by MPN using each supplier's own field naming, summarised in the following table. The canonical key in our database remains `Component.mpn`.

| Supplier | Search field | MPN field in response |
|---|---|---|
| Mouser | `SearchByPartRequest.mouserPartNumber` (accepts MPN) | `ManufacturerPartNumber` |
| DigiKey | KeywordSearch v4 `keywords` or `manufacturerProductNumber` | `ManufacturerProductNumber` |
| TME | `Products/Search` `SearchPlain` | `OriginalSymbol` |
| Farnell | `keywordSearch` `term=any:<MPN>` | `translatedManufacturerPartNumber` |
| RS | `searchTerm=<MPN>` | `mpn` |

#### Scenario: TME adapter uses OriginalSymbol not Symbol

- **WHEN** the TME adapter receives a response where `Symbol="TME-12345"` and `OriginalSymbol="NBC12429FAR2G"`
- **THEN** the returned `SupplierQuote.mpn` equals `"NBC12429FAR2G"`
- **AND** `supplier_sku` equals `"TME-12345"`

### Requirement: Adapters respect per-supplier rate limits via Redis token bucket

The system SHALL implement `app/infrastructure/rate_limit.py` with an async `acquire(bucket: str, limit_per_minute: int) -> None` helper backed by an atomic Redis Lua script keyed on `rate_limit:{bucket}`. Each adapter MUST call `acquire(f"supplier:{self.code}", supplier_limit)` before every outbound HTTP call. When the bucket is exhausted, the helper SHALL block until the next refill window (max 60 seconds).

#### Scenario: Within quota the request proceeds immediately

- **WHEN** the Mouser bucket has 30 tokens and 1 token is requested
- **THEN** `acquire` returns within 50ms

#### Scenario: Over quota the request waits for refill

- **WHEN** the Mouser bucket is empty
- **THEN** `acquire` blocks until the bucket refills, never exceeding 60 seconds

### Requirement: All supplier credentials are read from settings

The system SHALL extend `app/core/config.py` with: `MOUSER_API_KEY: str | None`, `DIGIKEY_CLIENT_ID: str | None`, `DIGIKEY_CLIENT_SECRET: str | None`, `DIGIKEY_OAUTH_TOKEN_URL: str` (default DigiKey production URL), `TME_TOKEN: str | None`, `TME_APP_SECRET: str | None`, `FARNELL_API_KEY: str | None`, `FARNELL_STORE_ID: str` (default `"uk.farnell.com"`), `RS_API_KEY: str | None`, `SUPPLIER_SYNC_ENABLED_SUPPLIERS: list[str]` (default `["mouser","digikey","tme","farnell"]`), `SUPPLIER_LOOKUP_PRIORITY: list[str]` (default `["mouser","digikey","tme","farnell","rs"]`), `SUPPLIER_LOOKUP_CACHE_TTL_SECONDS: int` (default `900`), `SUPPLIER_SYNC_DAILY_HOUR_UTC: int` (default `3`).

#### Scenario: Missing key disables that supplier without crashing

- **WHEN** `SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser,digikey"` but `DIGIKEY_CLIENT_SECRET=""`
- **THEN** the application boots successfully
- **AND** only the Mouser adapter is registered
