# Contributing to ADA ASM

This guide covers the minimum local setup needed to work on the codebase. Detailed standards live in [`ai-specs/specs/`](ai-specs/specs/).

## Pre-commit hooks

The repository uses [pre-commit](https://pre-commit.com) to keep formatting, linting and basic security checks consistent.

### One-time install (per clone)

```bash
pip install pre-commit
pre-commit install
```

After this, every `git commit` runs the configured hooks. A failing hook aborts the commit — fix the issue, restage the change, and commit again.

### Running hooks manually

```bash
# Run all hooks on every file in the repo
pre-commit run --all-files

# Run a single hook
pre-commit run ruff --all-files
pre-commit run eslint --all-files
```

### What is enforced

See [`.pre-commit-config.yaml`](.pre-commit-config.yaml) for the canonical list. As of this writing:

- **Always**: trailing whitespace, end-of-file fixer, YAML/check, large-file guard, private-key detection, merge-conflict markers, case-conflict guard.
- **Backend** (`backend/**/*.py`): `ruff` lint + format, `mypy` strict.
- **Frontend** (`frontend/src/**`): `eslint`, `prettier --check`, `tsc --noEmit`.
- **Dockerfiles**: `hadolint`.

### Frontend hooks require `pnpm`

The frontend hooks delegate to the project's own `pnpm` so versions match `package.json`. Make sure `pnpm` is installed and `frontend/node_modules/` exists (`cd frontend && pnpm install`) before the first commit that touches `frontend/`.

## Running the stack

```bash
cp .env.example .env       # fill in JWT_SECRET, ports, etc.
docker compose up --build  # postgres + redis + backend + celery + frontend
```

Default ports (override via `.env`):

- Backend:  http://localhost:8000
- Frontend: http://localhost:5173
- Postgres: 5432
- Redis:    6379

## Commit messages

- English, imperative mood.
- Conventional format `<area>: <verb> <object>` is preferred (e.g. `auth: add password recovery flow`).
- Do not include automated co-author trailers.
