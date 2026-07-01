## MODIFIED Requirements

### Requirement: The lookup merges supplier quotes progressively, higher priority wins per field

The system SHALL iterate suppliers in priority order and accumulate a single `fields` object such that for each PRESENTATION scalar field (`name`, `description`, `manufacturer`, `datasheet_url`, `package`, `current_price_per_100_eur`) the first non-null value encountered is kept and not overwritten by later suppliers. The `family` SHALL NOT be resolved by this presentation merge — it is computed separately by `FamilyInferenceService` from every responding supplier's raw category signal (see capability `family-inference`), because the presentation priority order (Mouser first) inverts the category signal-strength order (DigiKey/TME stable ids first). Each supplier's intact quote MUST be appended to `supplier_data[]` regardless of whether its fields ended up "winning" in the merge, and each quote SHALL carry its raw category signal (`supplier_category_id`, `supplier_category_name`, `tariff_code`).

#### Scenario: Higher priority supplier wins on overlapping presentation fields

- **WHEN** Mouser returns `{"name": "X", "datasheet_url": null}` and DigiKey returns `{"name": "Y", "datasheet_url": "https://..."}` for the same MPN
- **THEN** the merged `fields.name` equals `"X"` (Mouser)
- **AND** `fields.datasheet_url` equals the DigiKey URL (Mouser had null, DigiKey filled)
- **AND** `supplier_data` contains two entries, one per supplier, each preserving its own raw fields

#### Scenario: Family is not decided by presentation priority

- **WHEN** Mouser's localized category name would keyword-match `Diodos` but DigiKey's stable leaf category maps to `Transistores` for the same MPN
- **THEN** the resolved family is `Transistores` (signal-strength resolution), NOT Mouser's `Diodos`
- **AND** the per-supplier category signals are present in `supplier_data[]`

#### Scenario: Disabled suppliers are skipped silently

- **WHEN** `SUPPLIER_LOOKUP_PRIORITY="mouser,digikey,tme,farnell,rs"` but `SUPPLIER_SYNC_ENABLED_SUPPLIERS="mouser,digikey"`
- **THEN** the merge consults only Mouser and DigiKey
- **AND** `sources_consulted` equals `["mouser","digikey"]`
