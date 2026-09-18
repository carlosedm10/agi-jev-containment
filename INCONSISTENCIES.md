# HackSpain 2026 — Known Inconsistencies

Findings from a code audit (2026-09-18), grouped by priority. Each verified by reading the code. Fix opportunistically; delete entries as they land.

## Should fix

1. **`GET /api/items/` does not use the database** — `backend/app/items/router.py` injects `get_db` then returns `[]`. The `Item` model is never queried.
2. **No Alembic revisions** — `backend/alembic/versions/` is empty (`.gitkeep` only). `make migrate` upgrades nothing; the `items` table is not created.

## Worth a look

3. **Compose Postgres sets both `image` and `build`** — `compose.yaml` `postgres-hackspain` uses `postgres:16-alpine` and `docker/postgresql.Dockerfile` (which is `FROM postgres:16-alpine`). Redundant; easy to drift.

## Checked and clean

- **Frontend image builds** — `frontend/package.json` and `bun.lock` exist; `docker/frontend.Dockerfile` COPY succeeds.
- **`GET /health`** — `backend/app/main.py` returns `{"status": "ok"}` with no DB; covered by `app/tests/test_health.py`.
- **CI env bootstrap** — `.github/workflows/ci.yml` runs `cp .env_template .env` before `make build`.
- **CORS origin** — `allow_origins=["http://localhost:3000"]` matches the compose host mapping `3000:5173`.
