## Context

The repository currently has standards (`ai-specs/specs/backend-standards.mdc`, `frontend-standards.mdc`), Docker scaffolding (`backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`), pre-commit configuration and an overview document — but no runnable code. The first user story (`Login en ASM 1.0`) cannot be implemented or validated end-to-end until the stack boots and a CI pipeline can gate changes.

The constraint that makes this change worth a design document — rather than a single trivial commit — is that it touches **five concurrent moving parts**: Python tooling (`uv` + Alembic + Celery), Node tooling (`pnpm` + Vite + Tailwind + shadcn), the existing Docker Compose orchestration, the GitHub Actions CI surface, and two new documentation artifacts under `ai-specs/specs/`. The ordering of those parts matters (Compose depends on Alembic, frontend Dockerfile depends on `package.json`, CI depends on lockfiles, etc.), so a single PR with a defined sequence is safer than ad-hoc commits.

## Goals / Non-Goals

**Goals:**

- After merge, `cp .env.example .env && docker compose up --build` brings the full stack to a healthy state on a fresh clone.
- `GET /api/v1/health` returns 200 from a real FastAPI process.
- `http://localhost:5173/` serves the bundled Vite + React + Tailwind shell with a placeholder `DashboardLayout`.
- Alembic baseline migration applies cleanly and is reversible.
- Celery worker and beat connect to Redis and remain running with no registered tasks.
- Two GitHub Actions workflows (`backend.yml`, `frontend.yml`) run on PRs and gate merges to `main`.
- A new developer can follow `development_guide.md` to reach a green health check without reading anything else.

**Non-Goals:**

- No business endpoints (no `/projects`, `/modules`, `/components`, `/auth`).
- No SQLAlchemy models or Pydantic schemas for business entities.
- No Celery tasks. The factory is set up; the task registry stays empty.
- No production deploy workflow. CI only validates PRs and pushes to `main`.
- No integration with Holded, KiCAT or supplier APIs.
- No design tokens extracted from Figma (deferred to the first UI-heavy User Story).
- No authentication wiring beyond declaring the env contract (`JWT_SECRET`). Login flow is the first User Story.

## Decisions

### D1. Package manager for backend: `uv`

`uv` is already referenced in `backend/Dockerfile` and `backend-standards.mdc`. It is materially faster than pip/Poetry, has a deterministic lockfile (`uv.lock`), and integrates cleanly with the multi-stage Docker build.

- **Alternative considered**: Poetry. Rejected — slower resolver, heavier image, no compelling feature win for this project's scale.
- **Alternative considered**: plain `pip-tools`. Rejected — weaker lockfile semantics, more glue code in CI.

### D2. Package manager for frontend: `pnpm`

`pnpm` is already referenced in `frontend/Dockerfile`, `.pre-commit-config.yaml` and `frontend-standards.mdc`. Faster install, stricter lockfile, content-addressable store — wins for CI cache hit rate.

- **Alternative considered**: npm. Acceptable but slower and looser. Rejected for consistency with the standards already committed.
- **Alternative considered**: yarn. Rejected — no upside, more friction with corepack vs pnpm.

### D3. Alembic baseline migration enables extensions only

The first migration installs `pgcrypto` (for `gen_random_uuid()`) and `ltree` (for the asset hierarchy) but does NOT create any business tables. Each User Story will add its own migrations.

- **Why**: Keeps this change minimal and clearly delimited; the migration is reversible without any data loss; future USs do not need to fight a "pre-existing" schema.
- **Alternative considered**: Create empty placeholder tables for `User`, `Project`, etc. Rejected — they would lack columns and constraints, becoming a footgun that conflicts with future USs.

### D4. Migrations run as a one-shot `migrate` service in Compose

The `docker-compose.yml` already defines a `migrate` service that runs `alembic upgrade head` and exits. `backend`, `celery_worker` and `celery_beat` depend on `migrate` completing successfully before they start.

- **Why**: Deterministic ordering, no race conditions, no need for entrypoint scripts in `backend/Dockerfile`.
- **Alternative considered**: Run migrations from inside the `backend` startup. Rejected — couples concerns and makes parallel scaling unsafe.

### D5. Health endpoint at `/api/v1/health`

Versioned from the start. The endpoint returns `{ "status": "ok", "version": "...", "timestamp": "..." }`. No DB or Redis ping in this change (those are deferred to a richer readiness check in a later US).

- **Alternative considered**: Unversioned `/health`. Rejected — the standards mandate `/api/v1/*` versioning and being consistent from day 1 avoids a later breaking move.

### D6. Frontend build embeds `VITE_API_URL` at build time, not runtime

Vite resolves `import.meta.env.VITE_API_URL` at build time. The Compose service passes it as a build arg. For local dev this is fine; for prod we will produce one image per environment, OR introduce a runtime config at first deploy. That is deferred — out of scope.

- **Alternative considered**: Inject runtime config via a generated `/env.js` served by nginx. Rejected for now — adds complexity for zero current benefit. To revisit when deploys exist.

### D7. CI uses GitHub Actions with path filters and dependency caches

Backend and frontend each get their own workflow. Path filters (`paths: ['backend/**']` / `paths: ['frontend/**']`) avoid running the wrong workflow on unrelated PRs. Caches keyed on the relevant lockfile hash (`uv.lock`, `pnpm-lock.yaml`) for the dependency store; an extra cache for Playwright browsers.

- **Alternative considered**: One mega-workflow. Rejected — harder to read, harder to skip selectively, slower median feedback.
- **Alternative considered**: Reusable workflows. Premature for two pipelines.

### D8. Playwright smoke in this change asserts only the placeholder shell

The `@smoke` set in this change verifies that the placeholder `DashboardLayout` renders. As USs land, they extend the smoke set with their own critical flows.

- **Why**: We need *some* e2e signal from day 1 to know the build artefact actually runs in a browser. A single render check is enough.

### D9. `data-model.md` is a forward-looking catalogue, not a schema

This change documents the entities listed in `docs/overview.md` (`User`, `Project`, `Module`, `Component`, `PriceSnapshot`, `RefreshToken`) with a one-paragraph description each and a pointer to the User Story that will own the table definition. Columns are NOT defined here.

- **Why**: Each US owns its own schema; pretending we know all columns today produces churn. The catalogue prevents naming drift between USs.

### D10. Branch-protection rule for `main` is documented, not automated

We document in `development_guide.md` that the two CI workflows must be configured as required status checks on `main`. The actual click in the GitHub UI is operator action — not something the change ships as code.

- **Alternative considered**: Set the branch-protection rule via `gh` CLI or a one-shot workflow. Rejected — out of scope for this first change; the rule belongs to the repo's governance config, not to source.

## Risks / Trade-offs

- **Risk**: shadcn/ui scaffolding requires an interactive `pnpm dlx shadcn-ui add ...`. → **Mitigation**: in this change we commit only the minimum shadcn primitives the placeholder shell needs (Button, Card or none), pre-scaffolded manually following the shadcn templates. We do NOT run the interactive CLI as part of the build.
- **Risk**: Cache key drift can produce stale CI installs. → **Mitigation**: cache keys include the SHA256 of `uv.lock` / `pnpm-lock.yaml`; any change invalidates them automatically.
- **Risk**: `VITE_API_URL` baked at build time will be wrong if used in a deploy environment. → **Mitigation**: documented limitation in `development_guide.md`; flagged as an explicit Open Question to revisit at first deploy.
- **Risk**: Multi-stage Docker images for `backend` and `frontend` are not exercised today — first real run could surface bugs. → **Mitigation**: a manual `docker compose up --build` is part of the change's Definition of Done; the smoke Playwright test runs against the served build.
- **Risk**: Pre-commit hooks (`mypy`, `eslint`, `tsc`) will run on an empty codebase. → **Mitigation**: pin minimum scopes so they execute against the skeleton's files; verify `pre-commit run --all-files` passes locally before merge.
- **Trade-off**: We boot Celery worker + beat even though no tasks exist yet. They consume small idle resources. → Worth it because: (a) we validate the Compose wiring once, (b) the first task-owning US doesn't need to debug infra.

## Migration Plan

Deployment is a merge to `main`. There is no production environment yet. Rollback is `git revert`.

For the local developer experience:

1. After merge, run `git pull`.
2. `cp .env.example .env`.
3. `docker compose down -v` if you had a previous skeleton-less stack (no data loss — there was no data).
4. `docker compose up --build`.
5. Verify `http://localhost:8000/api/v1/health` returns 200 and `http://localhost:5173` shows the placeholder shell.

## Open Questions

- **Frontend runtime config**: when we add the first deploy environment, do we switch to runtime config (`/env.js`) or build one image per env? Decision deferred to the first US that touches deploy.
- **Coverage measurement on a near-empty codebase**: Vitest and pytest will report 100% coverage on trivial code. The 80% gate is documented now but may behave oddly until real code exists. We accept this; the gate is meaningful from the first US onward.
- **Playwright in CI on a placeholder**: the smoke check may be considered noise. Decision: keep it so future USs inherit a working e2e plumbing rather than having to plumb it themselves.
