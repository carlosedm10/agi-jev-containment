# ------------------------------ Docker Compose ------------------------------ #
.PHONY: build up down restart

build:
	@echo ":: build: ."
	docker compose up --build -d --force-recreate
	@echo "Backend: http://localhost:8000/"
	@echo "OpenAPI: http://localhost:8000/docs"
	@echo "Frontend: http://localhost:3000/"

up:
	@echo ":: up: ."
	docker compose up -d --force-recreate
	@echo "Backend: http://localhost:8000/"
	@echo "OpenAPI: http://localhost:8000/docs"
	@echo "Frontend: http://localhost:3000/"

down:
	@echo ":: down: ."
	docker compose down --remove-orphans

restart:
	@echo ":: restart: ."
	docker compose restart

# ----------------------------- Backend Package Management ----------------------------- #
.PHONY: uv-lock uv-add uv-update uv-remove uv-lock-regenerate

# Usage:
#   make uv-add PKG="package[extras]==version"
#   make uv-update
#   make uv-update PKG=foo
#   make uv-remove PKG=foo
uv-lock:
	docker compose run --rm backend-hackspain uv lock

uv-add:
	docker compose run --rm backend-hackspain uv add $(PKG)

uv-update:
ifeq ($(PKG),)
	docker compose run --rm backend-hackspain uv lock --upgrade
else
	docker compose run --rm backend-hackspain uv lock --upgrade-package $(PKG)
endif

uv-remove:
	docker compose run --rm backend-hackspain uv remove $(PKG)

uv-lock-regenerate:
	docker compose run --rm backend-hackspain uv lock --refresh

# ----------------------------- Frontend Package Management ----------------------------- #
.PHONY: bun-install bun-add bun-update bun-remove bun-lock-regenerate

# Usage:
#   make bun-install
#   make bun-add PKG=package
#   make bun-update PKG=package
#   make bun-remove PKG=package
bun-install:
	docker compose exec -T frontend-hackspain bun install

bun-add:
	docker compose exec -T frontend-hackspain bun add $(PKG)

bun-update:
	docker compose exec -T frontend-hackspain bun update $(PKG)

bun-remove:
	docker compose exec -T frontend-hackspain bun remove $(PKG)

bun-lock-regenerate:
	docker compose exec -T frontend-hackspain bun install --lockfile-only

# ----------------------------- Terminals ----------------------------- #
.PHONY: backend-shell frontend-shell postgres-shell

backend-shell:
	docker compose exec backend-hackspain sh

frontend-shell:
	docker compose exec frontend-hackspain sh

postgres-shell:
	docker compose exec postgres-hackspain psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-hackspain}

# ----------------------------- Debugging ----------------------------- #
.PHONY: logs-backend logs-frontend logs-db logs

# App logs never include the database — that is logs-db.
logs-backend:
	docker compose logs -f backend-hackspain

logs-frontend:
	docker compose logs -f frontend-hackspain

logs-db:
	docker compose logs -f postgres-hackspain

logs:
	docker compose logs -f backend-hackspain frontend-hackspain

# ----------------------------- FastAPI / Alembic ----------------------------- #
.PHONY: migrate alembic-revision

# migrate is deliberately bare — the verb the framework's own docs use.
migrate:
	docker compose exec -T backend-hackspain uv run alembic upgrade head

alembic-revision:
	docker compose exec -T backend-hackspain uv run alembic revision --autogenerate -m "$(MSG)"

# ----------------------------- Code Formatting ----------------------------- #
.PHONY: lint-backend lint-frontend lint format-backend format-frontend format lint-fix-backend lint-fix-frontend lint-fix

# Usage:
#   make format-backend / make format-frontend / make format
#   make lint-fix-backend / make lint-fix-frontend / make lint-fix
#   make lint
lint-backend:
	docker compose exec -T backend-hackspain uv run ruff check .

lint-frontend:
	docker compose exec -T frontend-hackspain bun run lint

lint:
	make lint-backend
	make lint-frontend

format-backend:
	docker compose exec -T backend-hackspain uv run ruff format .

format-frontend:
	docker compose exec -T frontend-hackspain bun run format

format:
	make format-backend
	make format-frontend

lint-fix-backend:
	docker compose exec -T backend-hackspain uv run ruff check --fix .

lint-fix-frontend:
	docker compose exec -T frontend-hackspain bun run lint --fix

lint-fix:
	make lint-fix-backend
	make lint-fix-frontend

# ----------------------------- Testing ----------------------------- #
.PHONY: test-backend test-frontend test

test-backend:
	docker compose exec -T backend-hackspain uv run pytest $(TEST)

test-frontend:
	docker compose exec -T frontend-hackspain bun run test

test:
	make test-backend
	make test-frontend

# ----------------------------- Experiments ----------------------------- #
.PHONY: bench bench-analyze bench-plots

# Subset: make bench ARGS="pipeline slow_burn_50"
bench:
	docker compose exec -T backend-hackspain uv run python /experiments/bench.py $(ARGS)

bench-analyze:
	docker compose exec -T backend-hackspain uv run python /experiments/analysis.py $(ARGS)

bench-plots:
	docker compose exec -T backend-hackspain uv run python /experiments/plots.py

# ----------------------------- ⛔️ DANGER ZONE ⛔️ ----------------------------- #
.PHONY: clean clean-builder

# NUCLEAR: drops named volumes, database included. `make up` + `make migrate` rebuilds from zero.
clean:
	docker compose down --volumes --remove-orphans

clean-builder: clean
	docker builder prune -f
