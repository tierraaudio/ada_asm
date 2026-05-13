# continuous-integration Specification

## Purpose
TBD - created by archiving change bootstrap-runnable-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Backend pull requests trigger an automated validation workflow

The repository SHALL define a GitHub Actions workflow at `.github/workflows/backend.yml` that runs on pull requests touching `backend/**` and on pushes to `main`. The workflow MUST execute, in order: dependency installation via `uv sync`, lint via `ruff check`, format check via `ruff format --check`, type check via `mypy app`, tests via `pytest`, and coverage enforcement at the 80% global threshold. Any failed step MUST fail the workflow.

#### Scenario: PR touching backend triggers the workflow

- **WHEN** a pull request is opened or updated with changes under `backend/**`
- **THEN** the `backend` workflow is queued and executes against the head commit

#### Scenario: PR not touching backend does not trigger the workflow

- **WHEN** a pull request modifies only files outside `backend/**`
- **THEN** the `backend` workflow is skipped or reported as `skipped` in the PR checks

#### Scenario: Coverage below threshold fails the workflow

- **WHEN** the backend test suite reports coverage below 80% for any of branches, functions, lines or statements
- **THEN** the `pytest` step exits with non-zero
- **AND** the workflow conclusion is `failure`

#### Scenario: Lint or type-check failure fails the workflow

- **WHEN** `ruff check` or `mypy app` reports any error
- **THEN** the workflow conclusion is `failure`
- **AND** subsequent steps do not run

### Requirement: Frontend pull requests trigger an automated validation workflow

The repository SHALL define a GitHub Actions workflow at `.github/workflows/frontend.yml` that runs on pull requests touching `frontend/**` and on pushes to `main`. The workflow MUST execute, in order: `pnpm install --frozen-lockfile`, `pnpm lint`, `pnpm typecheck`, `pnpm test:coverage` enforcing 80%, `pnpm build`, and a Playwright smoke run (`pnpm e2e --project=chromium --grep @smoke`). Any failed step MUST fail the workflow.

#### Scenario: PR touching frontend triggers the workflow

- **WHEN** a pull request is opened or updated with changes under `frontend/**`
- **THEN** the `frontend` workflow is queued and executes against the head commit

#### Scenario: Lockfile drift fails the workflow

- **WHEN** the committed `frontend/pnpm-lock.yaml` is out of sync with `frontend/package.json`
- **THEN** `pnpm install --frozen-lockfile` exits with non-zero
- **AND** the workflow conclusion is `failure`

#### Scenario: Production build is verified

- **WHEN** the frontend workflow runs the `pnpm build` step
- **THEN** the build completes successfully and the `dist/` directory is created
- **AND** TypeScript errors at build time fail the workflow

#### Scenario: Smoke e2e covers the placeholder shell

- **WHEN** the Playwright smoke set runs
- **THEN** at least one test verifies that the placeholder `DashboardLayout` renders against the built artifact

### Requirement: CI workflows must pass before merging to main

The repository SHALL configure the `backend` and `frontend` workflow conclusions as required status checks for the `main` branch via branch protection. A pull request MUST NOT be mergeable into `main` if either workflow is required for the changed paths and reports `failure` or `cancelled`.

#### Scenario: Failed required workflow blocks merge

- **WHEN** a PR's required workflow concludes as `failure`
- **THEN** the GitHub UI reports the PR as not mergeable until the workflow is rerun successfully

#### Scenario: Branch protection is documented

- **WHEN** the development guide is consulted
- **THEN** it explains which workflows are required and how to re-trigger a failed run

### Requirement: CI workflows cache dependencies for fast feedback

Both workflows SHALL cache language-specific dependency stores between runs to keep median PR feedback time short. The backend workflow MUST cache the uv virtual environment; the frontend workflow MUST cache the pnpm store and the Playwright browsers.

#### Scenario: Cache hit on unchanged lockfile

- **WHEN** a workflow runs twice in a row with no changes to `uv.lock` (backend) or `pnpm-lock.yaml` (frontend)
- **THEN** the second run reports a cache hit and skips full reinstallation

