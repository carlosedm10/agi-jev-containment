# HackSpain 2026 — The One Doc

This repo is the local **hackspain** product stack for the 2026 hackathon: a FastAPI API, a React SPA (Vite), and Postgres. The participant **hackspain** CLI is a separate binary; its command surface lives in [docs/cli.md](cli.md) and must stay aligned with [hackspain.app/cli](https://hackspain.app/cli).

## The layers

```
browser :3000  →  frontend-hackspain (Vite :5173)  →  backend-hackspain :8000
                                                      →  postgres-hackspain :5432
```

- **frontend/** — React/Vite UI, host port 3000. Compose maps `3000:5173` and expects `frontend/package.json`. Vite proxies `/api` to `backend-hackspain:8000`, so the browser talks to one origin. `/` is the white, Inter mock dashboard driven by `src/dashboard/demo.ts` (no backend), with React Flow, BeautifulUI protective traces, and an expandable log panel. `/live` is the projector view — only the React Flow graph, fed by `/api/graph/stream`, with each run's walked path animated and coloured by level; `/live?demo` swaps in the mock feed ([docs/Graph.md](Graph.md)).
- **backend/** — FastAPI app (`app.main:app`), uv, SQLAlchemy, Alembic. **CORS allows only `http://localhost:3000`.**
- **postgres-hackspain** — Postgres 18. Backend waits on a healthy `pg_isready`. Named volume `postgres_data_hackspain`.

Compose network is `appnet_hackspain`. Services are named `backend-hackspain`, `frontend-hackspain`, `postgres-hackspain`.

## The taxonomy

These names repeat in compose, Makefile targets, and env vars.

| Name | Covers | Where it lives |
|---|---|---|
| **Runs** | HTTP ingest + JSONL tape: `POST /api/runs/{run_id}/events`, run lookup, run list | `backend/app/runs/` |
| **Classification** | `jev` client, watcher client, two-tier pipeline (τ trigger, gate, degraded path) | `backend/app/classification/` |
| **Action Graph** | Sparse L1+ event chain; `jev` scores short-term burst ∥ long-term history; SSE feed of every change | `backend/app/graph/` · `frontend/src/graph/` · [docs/Graph.md](Graph.md) |
| **health** | Liveness JSON `{status: ok}` | `GET /health` on the API |
| **hackspain CLI** | Participant terminal client (not this repo's code) | [docs/cli.md](cli.md) |
| **Agent monitoring** | Host-side capture of a sandboxed agent run | [docs/AgentMonitoring.md](AgentMonitoring.md) |
| **Actions** | `jev` intent → levels 1–5 → deterministic playbooks | [docs/Actions.md](Actions.md) |
| **Demo scenarios** | Malicious-agent harness + the L1–L5 demo arcs | [docs/scenarios.md](scenarios.md) |
| **jev** | Classifier: chain intent → level 0–5 + confidence + intent choice | Called from `backend/app/classification/jev.py`, over HTTP from the monitoring host |

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

- **Reads**: `GET /health` hits no database. `GET /api/graph/stream` opens an SSE feed: one `snapshot` of the whole graph, then one `update` per graph mutation ([docs/Graph.md](Graph.md)). `GET /api/runs/{run_id}` returns the run's derived level and its materialized key nodes; `GET /api/runs` lists runs seen on the JSONL tape.
- **Writes**: `POST /api/runs/{run_id}/events` appends the event to the run's JSONL tape, runs the two-tier classification pipeline, and materializes a graph node for every classified event (level ≥ 1 makes it a key node). Postgres is currently unused by the product path: the graph is in-memory with a JSON snapshot, the tape is JSONL under `run_log_dir`, and there is no SQLAlchemy model — so `alembic/versions/` still has no revisions and `make migrate` remains a no-op.
- **Sync / background**: graph mutations fan out to every open SSE subscriber inside the mutation itself — a composite operation publishes one update, so no client ever sees a half-built run.
- **Agent run (product path)**: sandbox JSONL (complete) → `jev` scores short-term burst ∥ long-term key-node history → graph materializes one node per action → dispatcher runs the [actions playbook](Actions.md). On this laptop that is tag / Helmcode supervisor / `docker pause` + close ports / disconnect `agentnet` / stop the agent compose. Ideal mapping (IAM, IGW, swarm) is in that same doc. L4–L5 also page Guli Moreno via HappyRobot, in parallel with the cut.

### Entities

- **Run**: identified by `run_id` in the URL — no table. Run state (level, key nodes) is derived from the graph; the complete event tape is the JSONL file.
- **Node / Verdict**: a materialized graph node keeps `{level, score, intent, action_id}` per [docs/Graph.md](Graph.md); `jev`'s answer is a `Verdict` dataclass in `backend/app/classification/models.py`.

### One example, end to end

1. Copy `.env_template` → `.env` and `direnv allow` (or export the same keys).
2. `make build` starts Postgres, then uvicorn on `:8000`, then the frontend container on `:3000`.
3. Browser or `curl` `GET http://localhost:8000/health` → `{"status":"ok"}`.
4. `curl -X POST localhost:8000/api/runs/demo/events -H 'content-type: application/json' -d '{"event":"file_read","path":"/app/.env"}'` → verdict JSON. With no `TYPESAFE_API_KEY` this returns a clean degraded verdict (level unchanged, `degraded: true`), and the event still lands on the tape — not a 500.
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
- **One node per action; key nodes are level ≥ 1**: every classified event becomes a node, so the graph is the run's complete action sequence. `key_nodes()` (level ≥ 1) is the flagged subset — that's the `long_term` history. On every event, `jev` gets the recent burst (tape) and the key-node history in parallel — a streak of bad nodes is dangerous; a mild node after earlier problems still counts for more. How those are mixed is `jev`'s job.
- **The graph is pushed, not polled**: SSE, one-way, whole graph (all runs). `revision` increments by one per published change, so a client detects a gap by arithmetic; a slow client (64 queued updates) is disconnected instead of being buffered, and reconnects with a fresh snapshot. There is no replay log — a snapshot is always cheaper than a history nobody read.
- **The dashboard is mock-only for now**: `frontend/src/dashboard/demo.ts` automatically advances the graph, protective actions, and container logs together. The three-panel viewer omits summary banners, counts, legends, and search/filter controls; the graph follows incoming activity by default with Bézier connections. Classified nodes reuse the graph protocol; provisional “Awaiting Jev” nodes remain outside it and never imply safety. Colors use Jev's discrete level, not its confidence. HappyRobot call transcripts and host containment steps are presentation fixtures, not new backend contracts or real operations. `useGraphStream()` remains independently tested but is not mounted by `App`; a future live viewer needs action/log feeds and pending-event capture as well as graph SSE.
- **Run level is derived, not stored**: there is no `Run` model or table. The run's level is `max` over the nodes stamped with its `run_id`, which makes escalate-only and L1-stickiness structural rather than enforced state.
- **The graph is undirected; run isolation comes from `run_id`**: nodes keep a mutual adjacency list (`neighbors`) — no `parent`, loops allowed via `connect()`. A run's nodes are the ones stamped with its `run_id`, so runs stay isolated without relying on edge direction.
- **The tape and the graph are different things**: the JSONL tape under `run_log_dir` keeps every raw event (short-term context, replay, forensics); the graph keeps the same actions as structured nodes — the record jev judged them with, plus `action_id` once a playbook fires. The tape is the raw record; the graph is the annotated one.
- **Frontend tests exercise behavior, not just types**: `bun test` covers graph snapshots/reconnection, cycle-safe layout, mock verdict/action ordering, and automatic dashboard updates, node selection, and expandable traces/logs in happy-dom. The dashboard test also proves it opens no `EventSource`. `bun run lint` (`tsc --noEmit`) owns typechecking; `bun run build` checks the production bundle.
- **Tests are offline**: every test drives the clients through `httpx.MockTransport` — no test touches the network, so `make test` passes with no API keys set (CI copies `.env_template`, where keys are empty).
- **Levels only escalate; L1 is sticky**: a run never auto-downgrades. After L1, later `jev` calls get `prior_level=1`. L1–L3 are one agent; L4–L5 are the environment. Agent sandboxes must sit on a separate network (`agentnet`) from the product compose stack so L4 does not black-hole the viewer.
- **L4/L5 page Guli in parallel with the cut**: HappyRobot outbound voice is notification, not authorization. Missing `ONCALL_PHONE` still executes infra. Destination is on the outbound node, not in the JSON. Hook URL, key, and number stay in gitignored `.env`; `scripts/page.sh` is the local trigger.

## Where the details live

- [docs/cli.md](cli.md) — participant CLI commands, flags, exit codes.
- [docs/Graph.md](Graph.md) — action graph spec (undirected adjacency, loops allowed, `run_id`-stamped nodes, one node per action with key nodes at level ≥ 1, short/long context, save/load) and the SSE stream contract. Code: `backend/app/graph/`, `frontend/src/graph/`.
- [docs/AgentMonitoring.md](AgentMonitoring.md) — sandbox capture signals.
- [docs/Actions.md](Actions.md) — levels 1–5, playbooks, pager, build order.
- [docs/HappyRobotEvals.md](HappyRobotEvals.md) — HappyRobot use-case map, adversarial methodology, and the synthetic corpus contract.
- [docs/scenarios.md](scenarios.md) — malicious-agent harness, toolset, and the demo scenarios (L1–L5).
- The code — `backend/app/` (API), `compose.yaml` + `docker/` (runtime), root `Makefile` (verbs).
