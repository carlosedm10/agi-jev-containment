# HackSpain 2026

Local product stack for the HackSpain 2026 hackathon: FastAPI, React/Vite, and Neo4j. The participant CLI is a separate binary.

- **How the system is built:** [docs/README.md](docs/README.md)
- **CLI commands:** [docs/cli.md](docs/cli.md) · official page [hackspain.app/cli](https://hackspain.app/cli)
- **Agent rules:** [AGENTS.md](AGENTS.md)

## Running it

Requires Docker with Compose v2 and GNU make. Everything runs in containers; nothing is installed on the host.

```bash
cp .env_template .env   # works empty: no API keys needed, Jev runs degraded
make build              # builds and starts Neo4j, the API and the UI
```

Then open:

- UI: http://localhost:3000/ — dashboard (`/`, `/live`, `/ladder`), and `/trace?run=<id>` after a run
- API: http://localhost:8000/ · OpenAPI: http://localhost:8000/docs · liveness: http://localhost:8000/health
- Neo4j Browser: http://localhost:7474/ (`neo4j` / `hackspain-local` unless you changed `NEO4J_*`)

Day-to-day verbs:

| Verb | Does |
|---|---|
| `make up` / `make down` / `make restart` | Start, stop, restart the stack without rebuilding |
| `make logs` · `make logs-neo4j` | Follow app logs (API + UI) or the database |
| `make backend-shell` · `make frontend-shell` · `make neo4j-shell` | Shell into a container / open cypher-shell |
| `make lint` · `make test` | Lint and test inside the running containers (stack must be up) |
| `make test-agent` | Offline harness tests on the host with uv, no Docker needed |
| `make clean` | Drops volumes, Neo4j data included |

### Using it

- **Demo run from the UI**: press *Trigger* on the dashboard. The backend replays one of four recorded malicious-agent chains through the full pipeline (tape → classification → gate → playbooks → Neo4j → SSE) and the graph fills in live. *View trace* opens the per-event timeline. No external agent or credentials needed.
- **Ingest your own events**: `POST /api/runs/{run_id}/events` with a JSON event body, e.g. `curl -X POST localhost:8000/api/runs/demo/events -H 'content-type: application/json' -d '{"event":"file_read","path":"/app/.env"}'`. Without `TYPESAFE_API_KEY` the verdict comes back `degraded: true`, never a 500.
- **Live classification**: set `TYPESAFE_API_KEY` (Jev) and `HELMCODE_API_KEY` (supervisor/agent brain) in `.env`, then `make up`. Every key is documented in [.env_template](.env_template).
- **Real sandboxed agent** (needs `HELMCODE_API_KEY`): `make agents-build` starts the malicious-agent harness from `compose.agents.yaml` on its own network, and `make collect RUN_ID=<id>` forwards its events to the running API. See [docs/scenarios.md](docs/scenarios.md).
- **Lab / evals**: `make lab` prints the lab URLs, `make populate-labs` seeds them, `make help-lab` lists the rest.

CLI install (macOS/Linux):

```bash
curl -fsSL https://hackspain.com/install.sh | sh
hackspain
```
