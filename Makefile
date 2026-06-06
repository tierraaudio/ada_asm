.PHONY: help up down logs build daily-sync seed-admin test test-backend test-frontend

help:
	@echo "ada_asm — common dev targets"
	@echo ""
	@echo "  make up              Bring the whole stack up (background)."
	@echo "  make down            Stop the stack."
	@echo "  make logs            Tail backend + worker logs."
	@echo "  make build           Rebuild backend + frontend images."
	@echo "  make daily-sync      Run the daily supplier sync ONCE against the local stack."
	@echo "                       (Replaces the deleted celery_beat container.)"
	@echo "  make seed-admin      Seed the initial admin user from .env values."
	@echo "  make test            Run backend + frontend test suites."
	@echo "  make test-backend    Run pytest against the local Postgres + Redis."
	@echo "  make test-frontend   Run vitest."

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f backend celery_worker

build:
	docker compose build

# The change `cloud-deployment-azure` removed the celery_beat container.
# In the cloud, the daily sync runs from a KEDA cron Container App Job at
# 03:00 UTC. Locally we invoke the same entry-point script manually with
# this target.
daily-sync:
	docker compose exec backend python -m app.scripts.cron_run_daily_sync

# Convenience wrapper around the seed-admin script. Picks email + password
# from .env (SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD).
seed-admin:
	docker compose exec backend python -m app.scripts.seed_admin

test: test-backend test-frontend

test-backend:
	cd backend && DATABASE_URL="postgresql+asyncpg://ada_asm:ada_asm@localhost:15432/ada_asm" \
		CELERY_BROKER_URL="redis://localhost:16379/0" \
		CELERY_RESULT_BACKEND="redis://localhost:16379/1" \
		JWT_SECRET="test-secret-do-not-use-in-prod" \
		PYTHONPATH=. .venv/bin/python -m pytest tests/ -q

test-frontend:
	cd frontend && pnpm test --run
