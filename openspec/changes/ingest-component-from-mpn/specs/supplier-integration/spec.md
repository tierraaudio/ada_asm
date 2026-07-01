## MODIFIED Requirements

### Requirement: Adapters return a normalised SupplierQuote value object

The system SHALL define `SupplierQuote` in `app/domain/entities/supplier_quote.py` with fields: `supplier: str`, `mpn: str`, `manufacturer: str | None`, `name: str | None`, `description: str | None`, `family_hint: str | None`, `supplier_category_id: str | None`, `supplier_category_name: str | None`, `tariff_code: str | None`, `datasheet_url: str | None`, `image_url: str | None`, `package: str | None`, `stock: int | None`, `lifecycle_status: str | None`, `moq: int | None`, `order_multiple: int | None`, `lead_time_days: int | None`, `price_breaks: list[SupplierPriceBreak]`, `parameters: list[SupplierParameter]`, `compliance: list[SupplierComplianceCode]`, `supplier_sku: str | None`, `supplier_product_url: str | None`, `raw_payload: dict | None`, `last_seen_at: datetime`. `SupplierPriceBreak` SHALL contain `quantity: int`, `price_eur: Decimal | None`, `price_original: Decimal`, `currency_original: str` (ISO 4217). `SupplierParameter` SHALL contain `key: str | None`, `label: str`, `value: str`, `unit: str | None`. `SupplierComplianceCode` SHALL contain `code_type: str`, `code_value: str`. Adapters MUST return `None` (not raise) when the supplier responds with no match for the queried MPN. Fields the supplier does not expose SHALL be `None`/empty, never fabricated.

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

#### Scenario: Adapter captures the stable category id when the supplier exposes one

- **WHEN** the DigiKey adapter parses a product whose category chain leaf is `CategoryId=280`
- **THEN** the returned `SupplierQuote.supplier_category_id` equals `"280"`
- **AND** `supplier_category_name` carries the leaf category name

#### Scenario: Adapter preserves the raw payload for later re-parsing

- **WHEN** any adapter returns a quote
- **THEN** `raw_payload` holds the supplier's original product object so doc-only fields can be re-parsed without a new API call

### Requirement: Each adapter extracts the richest category signal it can

The system's adapters SHALL extract the strongest available category signal per supplier so family inference is robust: DigiKey SHALL descend `ChildCategories` to the LEAF and capture both leaf and root `CategoryId` (not only the root `Category.Name`); TME SHALL capture `category.id` (not only the name); Mouser SHALL capture the localized leaf `Category` name; Farnell SHALL extract the `tariffCode` and `displayName` from the `large` response group (sending `versionInfo.versionNumber` so the richer field set is returned). Adapters SHALL inspect their own error envelope: Mouser over-limit is reported as HTTP 200 with an `Errors[]` entry (not 429) and SHALL be mapped to the typed rate-limit error.

#### Scenario: DigiKey distinguishes diodes from transistors

- **WHEN** the DigiKey adapter parses `1N4148W` (chain `19 > 2042 > 2085 > 280`) and `2N7002` (chain `19 > 2045 > 2088 > 278`)
- **THEN** their `supplier_category_id` values differ (`280` vs `278`)
- **AND** family inference can distinguish `Diodos` from `Transistores`

#### Scenario: Farnell yields a category signal instead of None

- **WHEN** the Farnell adapter parses a product with `tariffCode="85411000"`
- **THEN** the returned quote carries `tariff_code="85411000"` and a non-null `supplier_category_name`
- **AND** the quote no longer reports a null family signal for every part

#### Scenario: Mouser over-limit maps to the typed rate-limit error

- **WHEN** the Mouser API returns HTTP 200 with a `TooManyRequests` entry in `Errors[]`
- **THEN** the adapter raises `SupplierRateLimitedError`
