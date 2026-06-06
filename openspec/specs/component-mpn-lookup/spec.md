# component-mpn-lookup Specification

## Purpose
Synchronous `GET /api/v1/components/lookup?mpn=` endpoint that walks enabled suppliers in priority order, merges fields progressively, returns a single payload to pre-fill the "Nuevo componente" form, and caches results in Redis for 15 minutes.

## Requirements

### Requirement: Authenticated users can look up a component by MPN across all enabled suppliers

The system SHALL expose `GET /api/v1/components/lookup?mpn=<mpn>&force_refresh=<bool>` (auth `require_user`) that walks the enabled suppliers in `SUPPLIER_LOOKUP_PRIORITY` order (default `mouser,digikey,tme,farnell,rs`) and returns a merged `LookupResponse`. The endpoint MUST trim and lower-case the MPN for comparison purposes; the stored MPN is preserved verbatim. `mpn` is required, min length 3, max 60 characters.

#### Scenario: Validation rejects short MPNs

- **WHEN** an authenticated user GETs `/api/v1/components/lookup?mpn=ab`
- **THEN** the response is HTTP 422 with `code="VALIDATION_ERROR"`

#### Scenario: Missing auth returns 401

- **WHEN** the endpoint is called without a valid session token
- **THEN** the response is HTTP 401

### Requirement: The lookup merges supplier quotes progressively, higher priority wins per field

The system SHALL iterate suppliers in priority order and accumulate a single `fields` object such that for each scalar field (`name`, `description`, `manufacturer`, `family_hint`, `datasheet_url`, `package`, `current_price_per_100_eur`) the first non-null value encountered is kept and not overwritten by later suppliers. Each supplier's intact quote MUST be appended to `supplier_data[]` regardless of whether its fields ended up "winning" in the merge.

#### Scenario: Higher priority supplier wins on overlapping fields

- **WHEN** Mouser returns `{"name": "X", "datasheet_url": null}` and DigiKey returns `{"name": "Y", "datasheet_url": "https://..."}` for the same MPN
- **THEN** the merged `fields.name` equals `"X"` (Mouser)
- **AND** `fields.datasheet_url` equals the DigiKey URL (Mouser had null, DigiKey filled)
- **AND** `supplier_data` contains two entries, one per supplier, each preserving its own raw fields

#### Scenario: Disabled suppliers are skipped silently

- **WHEN** `SUPPLIER_LOOKUP_PRIORITY="mouser,digikey,tme,farnell,rs"` but `SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser,digikey"`
- **THEN** the merge consults only Mouser and DigiKey
- **AND** `sources_consulted` equals `["mouser","digikey"]`

### Requirement: The response distinguishes consulted vs succeeded suppliers

The `LookupResponse` SHALL include both `sources_consulted: string[]` (every enabled supplier that was contacted) and `sources_succeeded: string[]` (the subset that returned a non-error result, including 404-style no-match). `missing_fields: string[]` SHALL list the keys of `fields` that ended up null after the merge.

#### Scenario: Sources arrays report accurately

- **WHEN** the lookup hits Mouser (success), DigiKey (HTTP 500), TME (success)
- **THEN** `sources_consulted` equals `["mouser","digikey","tme"]`
- **AND** `sources_succeeded` equals `["mouser","tme"]`
- **AND** the response is still HTTP 200 because at least one supplier returned data

### Requirement: The lookup caches results in Redis for 15 minutes

The system SHALL cache the merged `LookupResponse` in Redis under key `supplier_lookup:{lower(mpn)}` for `SUPPLIER_LOOKUP_CACHE_TTL_SECONDS` (default 900). `?force_refresh=true` MUST bypass the cache (both read AND write — the new result replaces the cached value).

#### Scenario: Second call within TTL returns cached payload without hitting suppliers

- **WHEN** the operator calls `GET /api/v1/components/lookup?mpn=NBC12429FAR2G` twice in 30 seconds
- **THEN** the second call returns within ~20ms
- **AND** no supplier HTTP request is made on the second call (verifiable via supplier rate-limit counters)

#### Scenario: force_refresh bypasses the cache

- **WHEN** the operator calls the endpoint with `force_refresh=true` after a recent cached call
- **THEN** every enabled supplier is consulted again
- **AND** the cache entry is overwritten

### Requirement: 404 vs 502 distinguish no-match from total transport failure

The system SHALL return HTTP 404 with `code="COMPONENT_MPN_NOT_FOUND"` when at least one supplier was consulted successfully but none returned data for the MPN. The system SHALL return HTTP 502 with `code="SUPPLIER_LOOKUP_UNAVAILABLE"` when every consulted supplier raised a transport error (timeout, 5xx, auth failure). Both responses use RFC 7807.

#### Scenario: No supplier has the MPN

- **WHEN** all enabled suppliers respond with "no results" for an unknown MPN
- **THEN** the response is HTTP 404 with `code="COMPONENT_MPN_NOT_FOUND"`

#### Scenario: All suppliers fail with transport errors

- **WHEN** every enabled supplier raises a `SupplierError` (HTTP 5xx, timeout, auth failure)
- **THEN** the response is HTTP 502 with `code="SUPPLIER_LOOKUP_UNAVAILABLE"`
- **AND** `detail` in Spanish summarises which suppliers failed

### Requirement: The response payload shape is stable and documented

The `LookupResponse` JSON SHALL conform to:

```
{
  "mpn": string,
  "found": boolean,
  "fields": {
    "name": string | null,
    "description": string | null,
    "manufacturer": string | null,
    "family_hint": string | null,
    "datasheet_url": string | null,
    "package": string | null,
    "current_price_per_100_eur": number | null
  },
  "supplier_data": [
    {
      "supplier": "mouser" | "digikey" | "tme" | "farnell" | "rs",
      "supplier_sku": string | null,
      "supplier_product_url": string | null,
      "stock": integer | null,
      "price_breaks": [
        {"quantity": integer, "price_eur": number | null, "price_original": number, "currency_original": string}
      ]
    }
  ],
  "sources_consulted": string[],
  "sources_succeeded": string[],
  "missing_fields": string[]
}
```

#### Scenario: Response always includes all top-level keys

- **WHEN** the lookup returns HTTP 200 with `found=true`
- **THEN** every top-level key (`mpn`, `found`, `fields`, `supplier_data`, `sources_consulted`, `sources_succeeded`, `missing_fields`) is present in the JSON
