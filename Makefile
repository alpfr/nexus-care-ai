# Nexus Care AI — developer shortcuts.
#
# Usage from repo root:
#     make help              # list available commands
#     make install           # install all backend + frontend deps
#     make db-up             # start local Postgres
#     make db-migrate        # apply pending migrations
#     make db-seed           # seed a sandbox tenant + supervisor user
#     make api               # run the FastAPI dev server
#     make web               # run the Next.js dev server (when scaffolded)
#     make test              # run the backend test suite
#
# Most targets assume you've sourced .env first:  set -a; source .env; set +a

DATABASE_URL ?= postgresql+psycopg://nexus:nexus@localhost:5433/nexus_care

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
.PHONY: install
install: install-backend install-frontend ## Install all dependencies.

.PHONY: install-backend
install-backend: ## Install Python dependencies via uv.
	uv sync

.PHONY: install-frontend
install-frontend: ## Install frontend dependencies via bun.
	cd apps/web && bun install

# ---------------------------------------------------------------------------
# Database (local dev)
# ---------------------------------------------------------------------------
.PHONY: db-up
db-up: ## Start the local Postgres container.
	docker compose up -d db
	@echo "Waiting for Postgres to be ready..."
	@until docker compose exec -T db pg_isready -U nexus -d nexus_care >/dev/null 2>&1; do \
		sleep 1; \
	done
	@echo "Postgres is ready on localhost:5433."

.PHONY: db-down
db-down: ## Stop the local Postgres container (data persists).
	docker compose down

.PHONY: db-reset
db-reset: ## Stop Postgres and DELETE all data, then bring it back up + migrate + seed.
	docker compose down -v
	$(MAKE) db-up
	$(MAKE) db-migrate
	$(MAKE) db-seed

.PHONY: db-migrate
db-migrate: ## Apply pending Alembic migrations.
	DATABASE_URL='$(DATABASE_URL)' uv run alembic upgrade head

.PHONY: db-revision
db-revision: ## Create a new auto-generated migration. MSG="describe change"
	@if [ -z "$(MSG)" ]; then \
		echo "Usage: make db-revision MSG=\"describe change\""; \
		exit 1; \
	fi
	DATABASE_URL='$(DATABASE_URL)' uv run alembic revision --autogenerate -m "$(MSG)"

.PHONY: db-downgrade
db-downgrade: ## Roll back one migration.
	DATABASE_URL='$(DATABASE_URL)' uv run alembic downgrade -1

.PHONY: db-seed
db-seed: ## Seed local DB with a sandbox tenant + supervisor user.
	DATABASE_URL='$(DATABASE_URL)' uv run python scripts/seed_sandbox.py

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
.PHONY: api
api: ## Run the FastAPI dev server (auto-reload).
	NEXUS_API_DATABASE_URL='$(DATABASE_URL)' \
	uv run fastapi dev services/api/src/nexus_care_api/app.py --port 8001

.PHONY: web
web: ## Run the Next.js dev server (lands in tranche 3).
	cd apps/web && bun run dev

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
.PHONY: lint
lint: ## Run linters.
	uv run ruff check .
	uv run ruff format --check .

.PHONY: format
format: ## Auto-format code.
	uv run ruff format .
	uv run ruff check --fix .

.PHONY: typecheck
typecheck: ## Run mypy on the backend.
	uv run mypy services packages

.PHONY: test
test: ## Run the backend test suite.
	uv run pytest

.PHONY: test-fast
test-fast: ## Run the backend test suite, skipping integration/e2e.
	uv run pytest -m "not integration and not e2e"

# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------
.PHONY: clean
clean: ## Remove caches and build artifacts.
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv apps/web/node_modules apps/web/.next
