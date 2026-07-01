## ADDED Requirements

### Requirement: The system acquires the datasheet PDF through a prioritized fallback chain

The system SHALL attempt to obtain a downloadable datasheet PDF for an ingested MPN by trying sources in order and stopping at the first that yields a valid PDF: (1) the Farnell datasheet URL when present, (2) the DigiKey datasheet URL when it resolves to a direct PDF, (3) a deterministic manufacturer URL pattern derived from the manufacturer, (4) the manufacturer/distributor URL discovered via an aggregator as a fetch pointer. When no source yields a PDF, the system SHALL persist the best-known datasheet URL as a link only and continue (datasheet archival never blocks component creation).

#### Scenario: Farnell direct PDF is preferred

- **WHEN** the Farnell quote contains a `datasheets[].url` that returns `Content-Type: application/pdf`
- **THEN** that PDF is downloaded and archived
- **AND** later sources in the chain are not attempted

#### Scenario: Non-PDF responses are skipped

- **WHEN** a candidate datasheet URL returns `text/html` (e.g. a bot-challenge or interstitial page)
- **THEN** that source is treated as a miss and the next source is tried

#### Scenario: No PDF available falls back to link only

- **WHEN** no source in the chain yields a valid PDF
- **THEN** the component stores the best-known `datasheet_url` (external link)
- **AND** no blob is stored and component creation still succeeds

### Requirement: Datasheet downloads are validated before archival

The system SHALL follow redirects on every candidate URL and treat a download as valid only when the final response Content-Type is `application/pdf` AND the body begins with the `%PDF` magic bytes. The downloader SHALL apply a per-host User-Agent strategy (some manufacturer hosts require a non-browser UA, others a browser UA) and retry with an alternate UA on a 403 before giving up on that source.

#### Scenario: Magic-byte validation rejects a mislabeled PDF

- **WHEN** a URL returns `Content-Type: application/pdf` but the body does not start with `%PDF`
- **THEN** the download is rejected as invalid and the next source is tried

#### Scenario: Per-host UA retry recovers a 403

- **WHEN** a manufacturer host returns 403 to the default User-Agent
- **THEN** the downloader retries with the alternate User-Agent for that host
- **AND** archives the PDF if the retry succeeds

### Requirement: Archived datasheets are stored deduplicated in private Azure Blob storage

The system SHALL store each downloaded datasheet in a private Azure Blob container keyed by content hash (`datasheets/<sha256>.pdf`) so identical PDFs shared across MPNs are stored once. The system SHALL record on the component (or a `component_documents` row) the `blob_path`, `source_url`, `source`, `sha256`, `content_type`, and `fetched_at`. Blob access SHALL use the backend's managed identity with a Storage Blob Data role — never an account key or connection string.

#### Scenario: Identical PDFs are stored once

- **WHEN** two different MPNs resolve to the byte-identical datasheet PDF
- **THEN** only one blob `datasheets/<sha256>.pdf` exists
- **AND** both components reference the same blob path

#### Scenario: Provenance is recorded

- **WHEN** a datasheet is archived
- **THEN** the stored record includes the source URL, source supplier/manufacturer, sha256, and fetch timestamp

### Requirement: Archived datasheets are served only to authenticated users

The system SHALL expose the archived datasheet through the backend (`GET /api/v1/components/{id}/datasheet`) protected by `require_user`, streaming the private blob or redirecting to a short-lived read-only user-delegation SAS. The blob container SHALL NOT allow anonymous public access.

#### Scenario: Authenticated user retrieves the datasheet

- **WHEN** an authenticated user requests `GET /api/v1/components/{id}/datasheet` for a component with an archived PDF
- **THEN** the response delivers the PDF (stream or short-lived SAS redirect)

#### Scenario: Unauthenticated request is rejected

- **WHEN** the datasheet endpoint is called without a valid bearer token
- **THEN** the response is HTTP 401
- **AND** the blob is not exposed anonymously
