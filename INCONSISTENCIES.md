# Known inconsistencies

Tracked flaws that are knowingly left in place. Resolve an entry by fixing it, then delete it from this list (see [AGENTS.md](AGENTS.md)).

## Stale benchmark artifacts

- `experiments/*.csv` and `experiments/*.png` were measured against the old jev request shape (`state = {agent_id, events}`). The shipped client also sends policy, drift, Sentinel evidence and atomic questions. Kept as historical record; use `make monitor-eval` with `TYPESAFE_API_KEY` for the current live acceptance run.

## Referenced but never written

- [docs/scenarios.md](docs/scenarios.md) references optional richer-demo services that do not exist: `victim-agent`, `customers-db`, and `docker-lure`. Detection coverage for those mechanisms lives in the eval corpus instead.

## Not built

- The dispatcher records idempotent L1–L5 actions and executes demo-world counters. Host-side automatic invocation of Docker containment scripts remains intentionally separate because the backend container does not mount the Docker socket; scripts are verified through `--dry-run`.
