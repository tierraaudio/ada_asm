## ADDED Requirements

### Requirement: The system infers the internal family from heterogeneous supplier taxonomies

The system SHALL provide a `FamilyInferenceService` that maps the category signals of the four suppliers onto one of the fixed internal families (`Diodos`, `Transistores`, `Microcontroladores`, `Sensores`, `Condensadores`, `Resistencias`, `Conectores`, `Fuentes de alimentación`, `Módulos`). The internal family set is the canonical taxonomy; each supplier's native taxonomy is translated INTO it via rules, never used directly as the stored family. The service SHALL run separately from the presentation merge — it receives every responding supplier's raw category signal, not a single merged value.

#### Scenario: A diode resolves to Diodos from any supplier

- **WHEN** DigiKey returns leaf `CategoryId=280`, or TME returns `category.id=112791`, or Farnell returns `tariffCode` prefix `8541 1`, or Mouser returns a category name containing "diodo"
- **THEN** the inferred family is `Diodos`

#### Scenario: The stored family is always an internal family value

- **WHEN** any component is ingested and a family is inferred
- **THEN** `Component.family` is exactly one of the nine internal family strings (never a raw supplier category name)

### Requirement: Family inference resolves by signal strength, not presentation priority

The system SHALL resolve a single family per component by evaluating each responding supplier's signal in confidence order — DigiKey leaf `category_id`, then TME `category_id`, then Farnell `tariff_code` prefix, then Mouser category-name keyword — and taking the first confident match. This order is independent of (and may invert) the presentation merge priority used for `name`/`description`/`package`/price.

#### Scenario: DigiKey stable id beats Mouser localized name

- **WHEN** DigiKey's leaf category maps to `Transistores` and Mouser's localized category name would keyword-match `Diodos` for the same MPN
- **THEN** the inferred family is `Transistores` (DigiKey's stable id wins despite Mouser being higher in presentation priority)

#### Scenario: Lower-confidence supplier used when higher ones are silent

- **WHEN** only Mouser returns data and its category name keyword-matches `Condensadores`
- **THEN** the inferred family is `Condensadores`

### Requirement: Unmapped or ambiguous categories leave the family empty for manual review

The system SHALL leave `Component.family` empty and set a `needs_review` flag when no supplier signal produces a confident match. The system SHALL NOT store a silent best-guess in that case. Every unmapped category signal (supplier + category_id/name/tariff) SHALL be logged so the rules table can be grown.

#### Scenario: No rule match flags for review

- **WHEN** a component is ingested whose supplier categories match no rule in `component_family_rules`
- **THEN** `Component.family` is empty
- **AND** the component's `family_needs_review` flag is true
- **AND** the unmapped category signal is logged

#### Scenario: Provenance is stored for audit

- **WHEN** a family is inferred from DigiKey leaf `CategoryId=280`
- **THEN** the component stores the winning `raw_category_id`, `raw_category_name`, the deciding `family_inferred_supplier` and `family_inferred_match_type`
- **AND** these allow re-classification in bulk without re-calling the supplier APIs

### Requirement: Family rules live in an editable seed table, not hard-coded

The system SHALL store family mapping rules in a `component_family_rules` table (`supplier`, `match_type` ∈ {`category_id`, `tariff_prefix`, `name_keyword`}, `match_value`, `family`, `confidence`, `priority`, `enabled`, `notes`) seeded via migration with the mappings derived from the supplier research. Rules SHALL be addable without code deploy. `name_keyword` matches SHALL be evaluated case- and accent-insensitive (NFKD-normalized substring).

#### Scenario: A new rule changes inference without a deploy

- **WHEN** an operator inserts a `component_family_rules` row mapping a new DigiKey `category_id` to `Sensores`
- **THEN** a subsequent ingestion of a component in that category infers `Sensores`
- **AND** no code change or deploy was required

#### Scenario: Keyword matching ignores case and accents

- **WHEN** a Mouser category name is "Condensadores de cerámica multicapa" and a rule has `match_value="condensador"`
- **THEN** the rule matches (accent- and case-insensitive)
