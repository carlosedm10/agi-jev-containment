# HackSpain 2026 — The One Doc

This repo is the local **hackspain** product stack for the 2026 hackathon: a FastAPI API, a React SPA (Vite), and Postgres. The participant **hackspain** CLI is a separate binary; its command surface lives in [docs/cli.md](cli.md) and must stay aligned with [hackspain.app/cli](https://hackspain.app/cli).

## The layers

```
browser :3000  →  frontend-hackspain (Vite :5173)  →  backend-hackspain :8000
                                                      →  postgres-hackspain :5432
```

- **frontend/** — React/Vite UI, host port 3000. Compose maps `3000:5173` and expects `frontend/package.json`.
- **backend/** — FastAPI app (`app.main:app`), uv, SQLAlchemy, Alembic. **CORS allows only `http://localhost:3000`.**
- **postgres-hackspain** — Postgres 18. Backend waits on a healthy `pg_isready`. Named volume `postgres_data_hackspain`.

Compose network is `appnet_hackspain`. Services are named `backend-hackspain`, `frontend-hackspain`, `postgres-hackspain`.

## The taxonomy

These names repeat in compose, Makefile targets, and env vars.

| Name | Covers | Where it lives |
|---|---|---|
| **Item** | Placeholder domain (list endpoint, no real persistence yet) | `backend/app/items/` |
| **Action Graph** | Sparse L1+ event chain; `jev` scores short-term burst ∥ long-term history | `backend/app/graph/` · [docs/Graph.md](Graph.md) |
| **health** | Liveness JSON `{status: ok}` | `GET /health` on the API |
| **hackspain CLI** | Participant terminal client (not this repo's code) | [docs/cli.md](cli.md) |
| **Agent monitoring** | Host-side capture of a sandboxed agent run | [docs/AgentMonitoring.md](AgentMonitoring.md) |
| **Actions** | `jev` intent → levels 1–5 → deterministic playbooks | [docs/Actions.md](Actions.md) |
| **jev** | Classifier: event type + chain intent + discrete level | Called from the monitoring host, not the sandbox |
| **HappyRobot evals** | Paired safe, unsafe, and covert agent traces across single and longitudinal sessions | `backend/app/evals/` · [docs/HappyRobotEvals.md](HappyRobotEvals.md) |

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
- **Agent run (product path, not shipped yet)**: sandbox JSONL (complete) → `jev` scores short-term burst ∥ long-term key-node history → graph materializes only level ≥ 1 → dispatcher runs the [actions playbook](Actions.md). On this laptop that is tag / Helmcode supervisor / `docker pause` + close ports / disconnect `agentnet` / stop the agent compose. Ideal mapping (IAM, IGW, swarm) is in that same doc. L4–L5 also page Guli Moreno via HappyRobot, in parallel with the cut.

### Entities

- **Item**: scaffold entity for the first feature package (router, schema, model, colocated tests).

### One example, end to end

1. Copy `.env_template` → `.env` and `direnv allow` (or export the same keys).
2. `make build` starts Postgres, then uvicorn on `:8000`, then the frontend container on `:3000`.
3. Browser or `curl` `GET http://localhost:8000/health` → `{"status":"ok"}`.
4. `GET http://localhost:8000/api/items/` → `[]` (session opened, table unused).
5. OpenAPI UI is at `http://localhost:8000/docs`.

## Key decisions and caveats (why it is this way)

- **Compose hostname in `DATABASE_URL`**: the API talks to `postgres-hackspain`, not `localhost`. Host-side tools that are not on `appnet_hackspain` must use `localhost:5432` instead.
- **CORS pinned to the Vite origin**: `http://localhost:3000` only — other origins are rejected on purpose until a real frontend origin exists.
- **Tests live next to the code they cover**: feature tests under `app/<feature>/tests/`; health lives in `app/tests/`. Not a top-level `backend/tests/`.
- **`make lint` / `make test` run inside already-up containers**: the stack must be up first. `make build` builds AND starts it (`docker compose up --build -d`), so CI only needs `make build` — no separate `make up` step.
- **Postgres data volume mounts at `/var/lib/postgresql`, not `/var/lib/postgresql/data`**: postgres 18+ images store data in `/var/lib/postgresql/<major>/docker` and the entrypoint hard-fails on any mount at the old `/data` path — even an empty volume. Bumping the major version still needs a dump-and-restore or volume reset (`docker compose down -v`).
- **Frontend image must not copy host `node_modules`**: root `.dockerignore` excludes `frontend/node_modules` so `COPY frontend/ .` cannot overwrite the Linux install with Darwin Rollup binaries. Recreate the anonymous `/code/node_modules` volume after a bad copy (`docker compose up --renew-anon-volumes`).
- **`PYTHONPATH=/app` on the backend**: Alembic is invoked as a venv entrypoint (`uv run alembic`), which does not put the bind-mounted `app/` package on `sys.path`. Uvicorn's `app.main:app` import still works because `uv run` adds the project cwd.
- **Compose build cache is env-injected**: `cache_from`/`cache_to` interpolate `CACHE_FROM`/`CACHE_TO`; CI sets them to the GitHub Actions cache (`type=gha`), local builds default to throwaway `/tmp` dirs. Only one CI workflow exists (`ci.yml`) — it covers push and PRs to `main`, with in-progress runs cancelled on new commits.
- **`jev` sets the level; playbooks execute it**: criticality is intent of the *chain*, not of one event. L3–L5 are prewritten host-side scripts, never an LLM choosing the cut. This project: pause the sandbox, close its ports, cut `agentnet` egress, stop the agent compose. Ideal: IAM revoke, detach IGW, kill the swarm. The L2 Helmcode supervisor may only request a re-score.
- **Graph is sparse; context is short ∥ long**: only level ≥ 1 becomes a node (JSONL keeps everything). On every event, `jev` gets the recent burst and the key-node history in parallel — a streak of bad nodes is dangerous; a mild node after earlier problems still counts for more. How those are mixed is `jev`'s job.
- **Levels only escalate; L1 is sticky**: a run never auto-downgrades. After L1, later `jev` calls get `prior_level=1`. L1–L3 are one agent; L4–L5 are the environment. Agent sandboxes must sit on a separate network (`agentnet`) from the product compose stack so L4 does not black-hole the viewer.
- **L4/L5 page Guli in parallel with the cut**: HappyRobot outbound voice is notification, not authorization. Missing `ONCALL_PHONE` still executes infra.
- **Long memory is evidence, never authority**: evals preserve source, trust, time, and corrections across sessions. Historical context may inform a decision, but repetition, a summary, or a prior success cannot grant identity or permission. Every adversarial journey has a nearby safe control so stricter monitoring does not hide false positives.

## Where the details live

- [docs/cli.md](cli.md) — participant CLI commands, flags, exit codes.
- [docs/Graph.md](Graph.md) — action graph spec (sparse L1+ nodes, short/long context, save/load). Code: `backend/app/graph/`.
- [docs/AgentMonitoring.md](AgentMonitoring.md) — sandbox capture signals.
- [docs/Actions.md](Actions.md) — levels 1–5, playbooks, pager, build order.
- [docs/HappyRobotEvals.md](HappyRobotEvals.md) — HappyRobot use-case map, adversarial methodology, and the synthetic corpus contract.
- The code — `backend/app/` (API), `compose.yaml` + `docker/` (runtime), root `Makefile` (verbs).
