# HackSpain 2026 — The One Doc

This repo is the local **hackspain** product stack for the 2026 hackathon: FastAPI, React/Vite, and Neo4j for the monitoring graph. The participant **hackspain** CLI is a separate binary; its command surface lives in [docs/cli.md](cli.md) and must stay aligned with [hackspain.app/cli](https://hackspain.app/cli).

## The layers

```
browser :3000  →  frontend-hackspain (Vite :5173)  →  backend-hackspain :8000
                                                      →  neo4j-hackspain :7687
```

- **frontend/** — React/Vite UI, host port 3000. Compose maps `3000:5173` and expects `frontend/package.json`. Vite proxies `/api` to `backend-hackspain:8000`, so the browser talks to one origin. The UI renders nothing today: it mirrors the live graph in memory ([docs/Graph.md](Graph.md)).
- **backend/** — FastAPI app (`app.main:app`), uv. **CORS allows only `http://localhost:3000`.**
- **neo4j-hackspain** — Neo4j Community. Persistent event/entity/assessment graph plus resumable realtime messages.

Compose network is `appnet_hackspain`. Services are named `backend-hackspain`, `frontend-hackspain`, `neo4j-hackspain`.

## The taxonomy

These names repeat in compose, Makefile targets, and env vars.

| Name | Covers | Where it lives |
|---|---|---|
| **Runs** | HTTP ingest + JSONL tape: `POST /api/runs/{run_id}/events`, run lookup, run list | `backend/app/runs/` |
| **Realtime monitor API** | Contrato frontend: snapshot, SSE, lifecycle y grafo Neo4j | [docs/RealtimeGraphAPI.md](RealtimeGraphAPI.md) |
| **Classification** | `jev` client, watcher client, two-tier pipeline (τ trigger, gate, degraded path) | `backend/app/classification/` |
| **Monitoring Graph** | Complete Neo4j event/entity/assessment graph; sparse `key_nodes` only for Jev context; transitional ActionGraph SSE | `backend/app/graph/` · `frontend/src/graph/` · [docs/Graph.md](Graph.md) |
| **health** | Liveness JSON `{status: ok}` | `GET /health` on the API |
| **hackspain CLI** | Participant terminal client (not this repo's code) | [docs/cli.md](cli.md) |
| **Agent monitoring** | Host-side capture of a sandboxed agent run | [docs/AgentMonitoring.md](AgentMonitoring.md) |
| **Actions** | `jev` intent → levels 1–5 → deterministic playbooks | [docs/Actions.md](Actions.md) |
| **Demo scenarios** | Malicious-agent harness + the L1–L5 demo arcs | [docs/scenarios.md](scenarios.md) |
| **jev** | Classifier: chain intent → level 0–5 + confidence + intent choice | Called from `backend/app/classification/jev.py`, over HTTP from the monitoring host |

## How it's built

One path for local work:

```
make build/up → compose → uvicorn (reload) + bun dev + neo4j
```

GitHub Actions copies `.env_template` to `.env`, then `make build`, `make lint`, and `make test`. Live Jev (`make monitor-eval`) stays a local command: GitHub runners cannot reach TypeSafe reliably, so it is not a required check.

### The principles that matter

- **Make is the public interface** — CI and humans run the same verbs (`lint`, `test`). Do not duplicate tool commands in workflow YAML.
- **Secrets stay in gitignored `.env`** — `.envrc` only loads; new keys are documented in `.env_template`.
- **Backend venv lives outside the bind mount** — `UV_PROJECT_ENVIRONMENT=/opt/venv` so `./backend:/app` does not wipe dependencies on the host.
- **CLI commands are not invented here** — the binary is unpublished in this tree; [docs/cli.md](cli.md) tracks the official surface.

## How data flows

Settings (`NEO4J_*`) come from the process environment. Pydantic settings also accept a `.env` next to the process cwd (`/app` in the container) and ignore extra keys.

- **Reads**: `GET /health` hits no database. Run `snapshot`, `stream`, `timeline` and `graph` read the persistent Neo4j monitor; `/api/graph/stream` remains the transitional whole-ActionGraph SSE used by the headless mirror already on `main`.
- **Writes**: `POST /api/runs/{run_id}/events` normalizes, redacta y añade el evento al tape JSONL; ejecuta clasificación, drift, Sentinel, gate y dispatch; y persiste grafo y `StreamMessage` en Neo4j. La demo de contramedidas usa un world state mínimo en memoria.
- **Sync / background**: Neo4j `StreamMessage` ofrece replay SSE por run; el ActionGraph transitorio también fan-out mutations a sus clientes conectados.
- **Agent run (product path)**: tool preflight → tape completo → SafetyDrift/Sentinel → Jev → gate determinista → ejecución o rechazo → Neo4j persiste evento, entidades, assessment y stream SSE → dispatcher registra playbooks y ejecuta counters del world demo.

### Entities

- **Run**: identified by `run_id` in the URL. Neo4j persists its level and event membership; the complete event tape is JSONL, while the legacy API still derives key nodes from the in-memory ActionGraph.
- **Event / Assessment / Entity**: Neo4j persists the directed monitoring graph; its concrete labels, relationships and frontend payloads live in [RealtimeGraphAPI.md](RealtimeGraphAPI.md).
- **Node / Verdict**: the transitional ActionGraph keeps `{level, score, intent, action_id}` per [docs/Graph.md](Graph.md); `jev`'s answer is a `Verdict` dataclass in `backend/app/classification/models.py`.

### One example, end to end

1. Copy `.env_template` → `.env` and `direnv allow` (or export the same keys).
2. `make build` starts Neo4j, then uvicorn on `:8000` and the frontend container on `:3000`.
3. Browser or `curl` `GET http://localhost:8000/health` → `{"status":"ok"}`.
4. `curl -X POST localhost:8000/api/runs/demo/events -H 'content-type: application/json' -d '{"event":"file_read","path":"/app/.env"}'` → verdict JSON. With no `TYPESAFE_API_KEY` this returns a clean degraded verdict (level unchanged, `degraded: true`), and the event still lands on the tape — not a 500.
5. OpenAPI UI is at `http://localhost:8000/docs`.

## Key decisions and caveats (why it is this way)

- **Post-run trace is event-by-event**: after a triggered run finishes (or stops), View trace opens `/trace?run=<id>`. React Flow renders a directed horizontal timeline with timestamps beneath each node, including repeated actions, using the existing cards and controls. `GET /api/runs/{run_id}/trace` merges the JSONL tape with persisted Neo4j events and per-event assessments; it never derives the timeline from collapsed action signatures. The tape remains usable during a Neo4j outage with a visible warning. Missing assessments are shown as unavailable, not inferred. The detail panel and Previous/Next buttons inspect timestamps, phases, tools, targets and recorded levels. This first version traces agent actions, not the asynchronous pager/playbook lifecycle.
- **Trace explanations are optional display copy**: `POST /api/runs/{run_id}/trace/explanations` reuses the configured supervisor model for a plain-language sentence (at most 24 words / 160 characters) that says what the agent was doing, without repeating kind, tool or target ids. Requests include kind, phase, tool, sanitized target, agent, channel, level, and a truncated action description (`content` with bearer tokens stripped). Arguments and results stay out. Batches of up to 24 actions have a six-second request timeout and a bounded process-local cache keyed by model, prompt and facts. The timeline loads independently and retains recorded labels if generation fails; explanations never affect safety verdicts. The inspector shows that sentence under “In plain terms”, without a framed box.

- **CORS pinned to the Vite origin**: `http://localhost:3000` only — other origins are rejected on purpose until a real frontend origin exists.
- **Tests live next to the code they cover**: feature tests under `app/<feature>/tests/`; health lives in `app/tests/`. Not a top-level `backend/tests/`.
- **`make lint` / `make test` run inside already-up containers**: the stack must be up first. `make build` builds AND starts it (`docker compose up --build -d`), so CI only needs `make build` — no separate `make up` step.
- **Frontend image must not copy host `node_modules`**: root `.dockerignore` excludes `frontend/node_modules` so `COPY frontend/ .` cannot overwrite the Linux install with Darwin Rollup binaries. Recreate the anonymous `/code/node_modules` volume after a bad copy (`docker compose up --renew-anon-volumes`).
- **`PYTHONPATH=/app` on the backend**: keeps the bind-mounted `app/` package importable for any venv entrypoint that does not add the project cwd to `sys.path`.
- **Compose build cache is env-injected**: `cache_from`/`cache_to` interpolate `CACHE_FROM`/`CACHE_TO`; CI sets them to the GitHub Actions cache (`type=gha`), local builds default to throwaway `/tmp` dirs. Only one CI workflow exists (`ci.yml`) — it covers push and PRs to `main`, with in-progress runs cancelled on new commits.
- **Compose injects `TYPESAFE_API_KEY` only via `env_file: .env`**: do not also set `environment: TYPESAFE_API_KEY=${TYPESAFE_API_KEY:-}` — an empty interpolation overrides the file and the process looks keyed or blank depending on Settings. Pydantic settings ignore empty env values and strip wrapping quotes. The secret stays gitignored, documented in `.env_template`.
- **`jev` contributes the level; deterministic code owns the decision**: criticality is intent of the *chain*, not of one event. Drift, Sentinel and gate can raise the incident level. `app.dispatch` records lab kinds and demo-world counters; **`ActionService` runs host playbooks after the gate**, using `gate.incident_level`, not raw Jev alone. L1–L2 record the level and do nothing; L3 tags and continues; L4 contains one agent; L5 cuts, kills the agent swarm, then calls.
- **Sentinel inspect history is link-scoped, rehydrated from Neo4j when enabled**: the current run's recent events always participate; other runs participate when they share a real link (target, `derived_from`/`caused_by`, agent+target, memory/entity keys, tool+target). On ingest, missing in-process history and linked runs are restored from Neo4j before `inspect`; the ActionGraph cache is rebuilt for `prior_level` / `key_nodes`. With Neo4j off, cross-run inspect is process-local only. JSONL remains the append-only tape.
- **Lab suite default is full ingest; smoke is opt-in:** `POST /api/evals/benchmarks` walks Sentinel traces through `service.ingest` (JSONL, monitor.prepare, Jev-or-degrade, gate, dispatch, Neo4j persist, SSE). `?smoke=true` is the in-process `_walk_trace` and must not be pitched as Jev science. **LIVE** is only set when a classify returns `latency_ms`; a present `TYPESAFE_API_KEY` plus HTTP 401 is degraded. `make populate-labs LIVE_JEV=1` is the Make variable (`--live-jev` is not a make option).
- **One node per action; key nodes are level ≥ 1**: ingest appends one ActionGraph node after classification for every event, Jev-degraded included — the node level is `max(prior, jev, gate.incident_level)` and confidence is 0 when degraded — so the dashboard graph always mirrors the run's complete action sequence. `key_nodes()` (level ≥ 1) is the flagged subset — that's the `long_term` history. On every event, `jev` gets the recent burst (tape) and the key-node history in parallel — a streak of bad nodes is dangerous; a mild node after earlier problems still counts for more. How those are mixed is `jev`'s job.
- **Classification state and persistent state**: Neo4j `:Run.level` is escalate-only; the ActionGraph cache derives `max` level over hydrated nodes for the same `run_id`.
- **Two graph representations during migration**: the ActionGraph is an undirected in-process cache isolated by `run_id`; the persistent Neo4j monitoring graph is directed (`HAS_EVENT`, `NEXT`, causal and entity edges) and is the source for replay, inspect rehydration, and visualization.
- **The tape and the graphs are different things**: JSONL keeps each normalized event for short-term context, replay and recovery; the ActionGraph keeps classified chain nodes for Jev; Neo4j keeps the persistent directed event/entity/assessment graph. Their exact frontend boundary is [RealtimeGraphAPI.md](RealtimeGraphAPI.md).
- **Dashboard still uses the transitional ActionGraph stream**: React `/`, `/live`, and `/ladder` read `GET /api/graph/stream` and `/api/demo/incidents/latest` while Neo4j + per-run SSE remain the long-term contract ([RealtimeGraphAPI.md](RealtimeGraphAPI.md)). On startup the ActionGraph is rehydrated from Neo4j so the global stream immediately reflects persisted runs; new ingests update it in place and reuse action-signature nodes across runs.
- **Dashboard runs rotate through four predetermined chains**: `GET /api/demo/scenarios` lists ordered steps and action scores in `app/evals/demo_chains.py`. Omitting `scenario` in `POST /api/demo/trigger` draws from a server-owned shuffled cycle: every four automatic runs cover all four cases, without adjacent repeats across cycle boundaries. Rotation survives browser navigation but resets with the single API process; explicit scenario requests remain available. `exfil` (7 steps) and `forge` (8) cover forged-tool credential-export attempts under a failing-test cover task, peaking at L3. `lateral` (9) and `lateral_db` (10) cover agentnet discovery, lab SSH password attempts, neighboring workspace access and distinct customers-db probes, peaking at L4. They have distinct endpoints and non-monotonic action scores. Cards show the display-only Action level separately from the escalate-only Incident level; public event metadata cannot set that action score. No rate writes occur. These are recorded demo observations, not executed attacks: they bypass live Jev with server-owned verdicts, while Sentinel, gate, sequential containment lifecycle and L4 HappyRobot paging still run. The backend does not execute the host network-disconnect scripts; a real simultaneous network-cut demonstration requires separate host integration and lab services. No L5 containment breach is fabricated. Real runs and randomized lab population retain normal classification.
- **Logs are an all-run event feed, not a graph projection**: `GET /api/runs/logs/recent` returns the latest 500 tape events across all runs (limit 1–2000), newest first. The dashboard polls serially every 500 ms regardless of the followed run. IDs combine run and event; repeated shared-node visits remain separate stdout JSON rows with event timestamps. Fields are allowlisted, excluding raw content/arguments/results. Level is included only when the graph retains the matching event assessment, otherwise the row is marked Recorded. Local tape scanning is a demo-scale implementation; move to indexed event storage for larger deployments.
- **Voice context comes from recorded chain steps**: the pager populates main's `nodos` field from the current run's JSONL tape, matching recorded step signatures to trusted catalog descriptions. It excludes future actions, raw content, arguments, results and secret values. It identifies these as simulated traces; containment is reported as in progress, not prematurely finished. Existing node rendering and layout are unchanged by the chain selector.
- **Frontend tests are DOM tests, not typechecks**: `bun test` mounts dashboard hooks in happy-dom against a fake `EventSource`. `bun run lint` (`tsc --noEmit`) still owns typechecking; `make test` no longer just re-runs it.
- **Tests are offline**: every unit test drives clients through `httpx.MockTransport`, so `make test` passes with no API keys. `make monitor-eval` is the local live Jev runner; CI does not call it.
- **Levels only escalate; L1 is sticky**: a run never auto-downgrades. After L1, later `jev` calls get `prior_level=1`. L1–L4 are one agent / one conversation; L5 is the environment. Agent sandboxes must sit on a separate network (`agentnet`) from the product compose stack so L5 does not black-hole the viewer.
- **HappyRobot is the L5 voice call, after the cut**: `ActionService` runs forensics / cut-egress / kill-swarm first, then pages. There is no SMS step — L4 is containment only. A missing pager must never block infrastructure containment. `app.dispatch` may still record a `page_oncall` kind for the lab at L5.

- **Triggered runs can be stopped between actions**: `POST /api/demo/trigger/{run_id}/stop` signals the local generator; an in-flight ingest finishes to preserve its tape and graph writes. `GET /api/demo/trigger/{run_id}` reports whether it is still active. Controls are process-local for the single-worker demo, and do not stop external agents or undo protective actions. Missing action signatures create nodes through normal ingest; existing signatures reuse their nodes.

- **Shared nodes never share incident severity**: action signatures still reuse visual nodes, but each node retains `run_states` (level, confidence, intent, event and response trace). Classification history and prior levels read only the requested run's state. Snapshots persist those states; Neo4j hydration reconstructs them from each run's assessments. The dashboard projects the followed run's own state.
- **Gate decisions dispatch even with degraded Jev**: Sentinel/policy L3+ evidence still schedules the protective playbook. Degradation alone never raises severity. Containment steps and accepted escalations execute sequentially per incident; L4/L5 paging remains parallel. Triggered demos wait for each action's containment steps before advancing to the next trace event.

## Where the details live

- **Trigger starts a fresh visible log window**: clicking Trigger clears displayed rows immediately and excludes events older than that click on subsequent all-run polls. Stale in-flight responses cannot repopulate the cleared window. Stored tapes are not deleted. Active graph selection and the inspector advance together using per-run event sequence; the camera waits for the focused node's registered position.

- [docs/cli.md](cli.md) — participant CLI commands, flags, exit codes.
- [docs/Graph.md](Graph.md) — persistent Neo4j graph plus the transitional ActionGraph/SSE projection. Code: `backend/app/graph/`, existing headless mirror: `frontend/src/graph/`.
- [docs/RealtimeGraphAPI.md](RealtimeGraphAPI.md) — contrato implementable en español para snapshot + SSE, payloads, lifecycle, grafo Neo4j y world state.
- [docs/AgentMonitoring.md](AgentMonitoring.md) — sandbox capture signals.
- [docs/Actions.md](Actions.md) — levels 1–5, playbooks, pager, build order.
- [docs/HappyRobotEvals.md](HappyRobotEvals.md) — HappyRobot + Sentinel eval corpora, lab pages, monitor coverage gaps.
- [docs/BenchmarkReport.md](BenchmarkReport.md) — dated scientific eval report (method, n, thresholds, live Jev vs degraded).
- [docs/scenarios.md](scenarios.md) — malicious-agent harness, toolset, and the demo scenarios (L1–L5).
- The code — `backend/app/` (API), `compose.yaml` + `docker/` (runtime), root `Makefile` (verbs).
