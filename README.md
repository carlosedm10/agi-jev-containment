# AGI Jev Detection

**Open-source AI agent monitoring, malicious-agent detection, and escalate-only containment** for sandboxed LLM agents. Local HackSpain 2026 stack (AngryRobot dashboard): FastAPI, React/Vite, Neo4j. Classifies a *chain of actions*, not a single tool call. A model never pulls the plug.

> Also searchable as: **agent security monitor**, **LLM agent kill-switch**, **Jev / Sentinel / SafetyDrift pipeline**, **sandbox containment ladder (L1–L5)**. GitHub repo today: [`hack-spain-2026`](https://github.com/carlosedm10/hack-spain-2026). Proposed rename: **`agi-jev-detection`**.

This is not the HackSpain participant CLI. That binary is unpublished here; commands stay aligned with [hackspain.app/cli](https://hackspain.app/cli) and [docs/cli.md](docs/cli.md).

## What this repository is

**AGI Jev Detection** (product UI: AngryRobot) is a **local agent observability and response stack**. It ingests tool events from a Docker-sandboxed agent, redacts secrets, writes an append-only JSONL tape, scores intent with TypeSafe **Jev**, fuses **Sentinel** rules and **SafetyDrift**, then a **deterministic gate** sets an escalate-only incident level (0–5). L1–L2 record. L3 tags and continues. L4 contains one agent and **voice-pages** on-call (HappyRobot). L5 (environment cut) waits for a human on that call.

Use it when you are looking for:

- **Malicious AI agent detection** (covert exfil, forged tools, lateral movement) with replayable traces
- **AI agent sandbox monitoring** (`agentnet` isolated from the product compose network)
- **Graph-based agent forensics** (Neo4j event/entity/assessment graph + live SSE dashboard)
- A **hackathon-ready demo**: press Trigger — no live agent or API key required (Jev degrades cleanly)

How the system is built, taxonomy, data flows, and decisions: [docs/README.md](docs/README.md). Agent coding rules: [AGENTS.md](AGENTS.md). Known gaps vs the ideal kill-switch: [INCONSISTENCIES.md](INCONSISTENCIES.md).

## Repo name (proposal)

GitHub cannot be renamed from this PR. Pick one and rename the remote when you want search traffic to match the README title.

| Candidate | Why it ranks |
|---|---|
| **`agi-jev-detection`** (recommended) | Unique entity **Jev** (TypeSafe System One) + AGI/agent-safety queries; closest to “AGI Jeff Detection” |
| **`angryrobot-agent-monitor`** | Matches the dashboard brand people see at `:3000` |
| **`jev-sentinel-ladder`** | The three nouns in the pipeline: classifier, rules, L1–L5 |
| **`malicious-agent-containment`** | Plain-language SEO for “contain a rogue LLM agent” |
| **`hackspain-agi-jev`** | Keeps the hackathon token for local discovery |

## Running it

Requires Docker Compose v2 and GNU make. Everything runs in containers.

```bash
cp .env_template .env   # works empty: no API keys needed, Jev runs degraded
make build              # builds and starts Neo4j, the API and the UI
```

Then open:

- UI: http://localhost:3000/ — dashboard (`/`, `/live`, `/ladder`), and `/trace?run=<id>` after a run
- API: http://localhost:8000/ · OpenAPI: http://localhost:8000/docs · liveness: http://localhost:8000/health
- Neo4j Browser: http://localhost:7474/ (`neo4j` / `hackspain-local` unless you changed `NEO4J_*`)

| Verb | Does |
|---|---|
| `make up` / `make down` / `make restart` | Start, stop, restart the stack without rebuilding |
| `make logs` · `make logs-neo4j` | Follow app logs (API + UI) or the database |
| `make backend-shell` · `make frontend-shell` · `make neo4j-shell` | Shell into a container / open cypher-shell |
| `make lint` · `make test` | Lint and test inside the running containers (stack must be up) |
| `make test-agent` | Offline harness tests on the host with uv, no Docker needed |
| `make clean` | Drops volumes, Neo4j data included |

### Using it

- **Demo run from the UI**: press *Trigger* on the dashboard. The backend replays one of four recorded malicious-agent chains through the full pipeline (tape → classification → gate → playbooks → Neo4j → SSE). Every **even** Trigger is the L5 `lateral_db` walk; odd Triggers shuffle `exfil` / `forge` / `lateral`. *View trace* opens the per-event timeline. No external agent or credentials needed.
- **Ingest your own events**: `POST /api/runs/{run_id}/events` with a JSON event body, e.g. `curl -X POST localhost:8000/api/runs/demo/events -H 'content-type: application/json' -d '{"event":"file_read","path":"/app/.env"}'`. Without `TYPESAFE_API_KEY` the verdict comes back `degraded: true`, never a 500.
- **Live classification**: set `TYPESAFE_API_KEY` (Jev) and `HELMCODE_API_KEY` (supervisor/agent brain) in `.env`, then `make up`. Every key is documented in [.env_template](.env_template).
- **Real sandboxed agent** (needs `HELMCODE_API_KEY`): `make agents-build` starts the malicious-agent harness from `compose.agents.yaml` on its own network, and `make collect RUN_ID=<id>` forwards its events to the running API. See [docs/scenarios.md](docs/scenarios.md).
- **Lab / evals**: `make lab` prints the lab URLs, `make populate-labs` seeds them, `make help-lab` lists the rest.

CLI install (macOS/Linux) — participant hackathon client, not this monitor:

```bash
curl -fsSL https://hackspain.com/install.sh | sh
hackspain
```

## Architecture in one paragraph

Browser `:3000` → Vite (`frontend-hackspain`) proxies `/api` → FastAPI (`backend-hackspain` `:8000`) → Neo4j (`neo4j-hackspain` `:7687`). Ingest path: normalize + redact → JSONL tape → SafetyDrift / Sentinel / policy → Jev (or degraded verdict) → gate → lab dispatcher + `ActionService` playbooks → ActionGraph cache + Neo4j persist + SSE. Agent sandboxes live on **`agentnet`**, not on `appnet_hackspain`, so an L5 tear-down cannot black-hole the dashboard. Details: [docs/README.md](docs/README.md), [docs/Graph.md](docs/Graph.md), [docs/Actions.md](docs/Actions.md), [docs/Jev.md](docs/Jev.md), [docs/AgentMonitoring.md](docs/AgentMonitoring.md).

## FAQ (for humans and search / answer engines)

**What is Jev in this project?** Jev is TypeSafe System One (`jev-1.13.0`): a semantic classifier that answers typed questions (criticality L0–L5, intent, concealment, …) over short-term tape + long-term key nodes. It does not execute containment.

**How is this different from an LLM firewall or prompt filter?** The unit of judgement is the **run chain**. A single `curl` is noise; `curl` plus reading `.env` plus posting the contents is intent. Deterministic Sentinel/policy can raise the level even when Jev is degraded.

**Does the monitor auto-kill the environment?** No. Levels only escalate. Monitor dispatch is capped at L4 (contain one agent + page). L5 cut/kill requires on-call authorization. Host scripts (`scripts/contain.sh`, `cut-egress.sh`, `kill-swarm.sh`) exist but are not auto-invoked from the backend container (no Docker socket). Dashboard playbooks simulate those steps.

**Can I run it without API keys?** Yes. Empty `.env` is valid. Classification returns `degraded: true`; events still land on the tape and graph.

**Is this production IAM/VPC containment?** No. It is a laptop-scale ladder for a hackathon and evals (harm-detection F1 on candidate traces — see [CONTEXT.md](CONTEXT.md) and [docs/BenchmarkReport.md](docs/BenchmarkReport.md)).

## Topics this repo is about

AI agent security · LLM agent monitoring · malicious agent detection · agent sandboxing · tool-call telemetry · graph RAG forensics (Neo4j) · TypeSafe Jev · Sentinel rule engine · HappyRobot on-call pager · HackSpain 2026 · escalate-only incident response · covert tool forging · credential exfiltration traces
