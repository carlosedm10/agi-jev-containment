# HackSpain 2026 — The One Doc

This repo is the local **hackspain** product stack for the 2026 hackathon: a FastAPI API, a React SPA (Vite, not initialized yet), and Postgres. The participant **hackspain** CLI is a separate binary; its command surface lives in [docs/cli.md](cli.md) and must stay aligned with [hackspain.app/cli](https://hackspain.app/cli).

## The layers

```
browser :3000  →  frontend-hackspain (Vite :5173)  →  backend-hackspain :8000
                                                      →  postgres-hackspain :5432
```

- **frontend/** — React/Vite UI, host port 3000. **Empty until `bun create vite`.** Compose still expects `frontend/package.json`.
- **backend/** — FastAPI app (`app.main:app`), uv, SQLAlchemy, Alembic. **CORS allows only `http://localhost:3000`.**
- **postgres-hackspain** — Postgres 16. Backend waits on a healthy `pg_isready`. Named volume `postgres_data_hackspain`.

Compose network is `appnet_hackspain`. Services are named `backend-hackspain`, `frontend-hackspain`, `postgres-hackspain`.

## The taxonomy

These names repeat in compose, Makefile targets, and env vars.

| Name | Covers | Where it lives |
|---|---|---|
| **Item** | Placeholder domain (list endpoint, no real persistence yet) | `backend/app/items/` |
| **health** | Liveness JSON `{status: ok}` | `GET /health` on the API |
| **hackspain CLI** | Participant terminal client (not this repo's code) | [docs/cli.md](cli.md) |

## How it's built

One path for local work:

```
make build/up → compose → uvicorn (reload) + bun dev + postgres
              → Alembic uses DATABASE_URL on the compose hostname
```

GitHub Actions copies `.env_template` to `.env`, then only `make build`, `make up`, `make lint`, `make test`, `make down`.

### The principles that matter

- **Make is the public interface** — CI and humans run the same verbs (`lint`, `test`, `migrate`). Do not duplicate tool commands in workflow YAML.
- **Secrets stay in gitignored `.env`** — `.envrc` only loads; new keys are documented in `.env_template`.
- **Backend venv lives outside the bind mount** — `UV_PROJECT_ENVIRONMENT=/opt/venv` so `./backend:/app` does not wipe dependencies on the host.
- **CLI commands are not invented here** — the binary is unpublished in this tree; [docs/cli.md](cli.md) tracks the official surface.

## How data flows

Settings (`DATABASE_URL`, `SECRET_KEY`, `DEBUG`) come from the process environment. Compose injects `DATABASE_URL` with host `postgres-hackspain` (not `localhost`). Pydantic settings also accept a `.env` next to the process cwd (`/app` in the container), and ignore extra keys such as `POSTGRES_*`.

- **Reads**: `GET /health` hits no database. `GET /api/items/` opens a SQLAlchemy session via `get_db` and currently returns `[]` without querying.
- **Writes**: none shipped. `Item` is mapped (`items` table: id, name) and Alembic imports it in `alembic/env.py`, but `alembic/versions/` has no revisions, so `make migrate` is a no-op until the first autogenerate.
- **Sync / background**: none.

### Entities

- **Item**: scaffold entity for the first feature package (router, schema, model, colocated tests).

### One example, end to end

1. Copy `.env_template` → `.env` and `direnv allow` (or export the same keys).
2. `make build` starts Postgres, then uvicorn on `:8000`, then the frontend container on `:3000` (fails today: no `frontend/package.json`).
3. Browser or `curl` `GET http://localhost:8000/health` → `{"status":"ok"}`.
4. `GET http://localhost:8000/api/items/` → `[]` (session opened, table unused).
5. OpenAPI UI is at `http://localhost:8000/docs`.

## Key decisions and caveats (why it is this way)

- **Compose hostname in `DATABASE_URL`**: the API talks to `postgres-hackspain`, not `localhost`. Host-side tools that are not on `appnet_hackspain` must use `localhost:5432` instead.
- **CORS pinned to the Vite origin**: `http://localhost:3000` only — other origins are rejected on purpose until a real frontend origin exists.
- **Feature packages own their tests**: pytest `testpaths = ["app"]`; tests sit under `app/<feature>/tests/`, not a top-level `backend/tests/`.
- **`make lint` / `make test` exec into running containers**: they are not `run --rm`. The stack must already be up (CI does `make up` first).

## Where the details live

- [docs/cli.md](cli.md) — participant CLI commands, flags, exit codes.
- The code — `backend/app/` (API), `compose.yaml` + `docker/` (runtime), root `Makefile` (verbs).
- Known gaps vs this doc: [INCONSISTENCIES.md](../INCONSISTENCIES.md).
