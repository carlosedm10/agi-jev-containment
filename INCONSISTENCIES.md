# Known inconsistencies

Tracked flaws that are knowingly left in place. Resolve an entry by fixing it, then delete it from this list (see [AGENTS.md](AGENTS.md)).

## Stale benchmark artifacts

- `experiments/*.csv` and `experiments/*.png` were measured against the old jev request shape (`state = {agent_id, events}`). The shipped client sends `{run_id, prior_level, short_term, long_term}` plus three questions per call, so the τ/M/gate numbers quoted in [docs/Jev.md](docs/Jev.md) predate the shipped shape. Kept as historical record; not re-run because no API keys are available locally. Re-calibrate with `make bench` / `make bench-analyze` before trusting the band edges.

## Referenced but never written

- [docs/Actions.md](docs/Actions.md) references containment scripts that do not exist in this repo: `scripts/contain.sh`, `scripts/cut-egress.sh`, `scripts/kill-swarm.sh`.
- [docs/scenarios.md](docs/scenarios.md) references pieces that do not exist: `victim-agent`, `customers-db`, and `docker-lure` services; the dispatcher that maps `actionable_level` to a playbook.

## Not built

- The dispatcher that maps a materialized node to its prewritten playbook ([docs/Actions.md](docs/Actions.md)) is not implemented — the pipeline materializes nodes and computes `actionable_level`, but nothing fires scripts yet.
