## ADDED Requirements

### Requirement: Components carry blended supplier-derived scalar fields

The system SHALL extend `components` with normalized scalar columns populated at ingest and refreshable by sync: `lifecycle_status` (normalized enum), `last_buy_date` (date, nullable), `discontinued` (bool), `end_of_life` (bool), `moq` (int, nullable), `order_multiple` (int, nullable), `lead_time_days` (int, nullable), `unit_weight_kg` (numeric, nullable), `image_url` (text, nullable). `country_of_origin` already exists and SHALL be populated at ingest. Values arriving in heterogeneous units across suppliers (e.g. lead time in days/weeks/localized strings) SHALL be normalized before storage; the raw value remains in the per-offer payload snapshot.

#### Scenario: Blended scalars are populated at ingest

- **WHEN** a component is ingested and DigiKey reports `ManufacturerLeadWeeks="6"` and a last-buy date
- **THEN** `lead_time_days` is `42` (normalized to days) and `last_buy_date` is set
- **AND** `country_of_origin` is populated when any supplier exposed it

#### Scenario: Missing blended fields stay null, never fabricated

- **WHEN** no supplier exposes a value for a blended field (e.g. TME exposes no compliance)
- **THEN** the corresponding column is null

### Requirement: Components store the inferred-family provenance

The system SHALL extend `components` with `family_inferred_supplier` (text, nullable), `family_inferred_match_type` (text, nullable), `raw_category_id` (text, nullable), `raw_category_name` (text, nullable), `raw_tariff_code` (text, nullable), `family_confidence` (smallint, nullable), and `family_needs_review` (bool, default false), so a mis-mapping is auditable and components can be re-classified in bulk without re-calling the supplier APIs.

#### Scenario: Provenance lets a rule fix re-classify in bulk

- **WHEN** an operator adds a `component_family_rules` row for a previously-unmapped `raw_category_id`
- **THEN** all components with that stored `raw_category_id` can be re-classified by a query
- **AND** no supplier API calls are needed

### Requirement: The system persists per-supplier parameters, compliance, documents, and cross-references

The system SHALL provide tables `component_parameters` (`component_id`, `supplier`, `param_key`, `param_label`, `param_value`, `param_unit`), `component_compliance` (`component_id`, `supplier`, `code_type`, `code_value`), `component_documents` (`component_id`, `supplier`, `doc_type`, `url`, `file_name`, `size_bytes`, `language`, `blob_path`, `sha256`, `content_type`, `fetched_at`), and `component_cross_refs` (`component_id`, `supplier`, `ref_type`, `ref_value`). These tables SHALL be populated at ingest from the blended supplier data. A component MAY have multiple documents (multiple datasheets/sources).

#### Scenario: Parametric specs are persisted at ingest

- **WHEN** a component is ingested and suppliers return parametric attributes (voltage, tolerance, package...)
- **THEN** rows are written to `component_parameters` keyed by the stable parameter id when available

#### Scenario: Multiple datasheets are supported

- **WHEN** a part has datasheet entries from more than one source
- **THEN** `component_documents` holds one row per document with its own provenance

### Requirement: Each supplier offer stores a raw payload snapshot

The system SHALL persist a per-offer `raw_payload` JSONB snapshot of the supplier's original product object alongside the parsed fields, including the effective locale/currency/tax context so prices are self-describing and reproducible. Doc-only fields not promoted to columns SHALL remain available in this snapshot for later re-parsing without a new API call.

#### Scenario: Raw payload is queryable without re-calling the API

- **WHEN** a doc-only field is later needed that was not promoted to a column
- **THEN** it can be read from the stored `raw_payload` JSONB without contacting the supplier
