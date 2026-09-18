# AGENTS.md

Local stack for the HackSpain 2026 hackathon: FastAPI (`backend/`), React/Vite (`frontend/`), Postgres via Docker. The participant CLI binary is not in this repo.

Read before changing anything:
docs/ is the source of true in case of doubt follow docs instructions.

**AI skills** → [`.agents/skills/`](.agents/skills/) — Makefile, Docker, FastAPI/React, docs, CI, and pydantic_ai conventions. Claude Code loads them via [`.claude/skills/`](.claude/skills/); for other tools run the installer in [`.agents/install`](.agents/install) (see [`.agents/README.md`](.agents/README.md)).

1. [docs/README.md](docs/README.md) — taxonomy, architecture, data flows, key decisions. Keep its "Key decisions" list updated when a change makes or supersedes one.
2. [docs/cli.md](docs/cli.md) — hackspain CLI command surface. Read before documenting or mentioning CLI commands.
3. Root `Makefile` — `build`, `up`, `down`, `lint`, `test`, `migrate`.

Known code flaws: [INCONSISTENCIES.md](INCONSISTENCIES.md) — check before fixing something already tracked; delete entries you resolve.

## Non-negotiable rules

- **CLI source of truth** — Commands and flags stay aligned with [hackspain.app/cli](https://hackspain.app/cli); do not invent subcommands in this repo.
- **Docs ride the PR** — If the official CLI surface changes, update [docs/cli.md](docs/cli.md) in the same change. Architecture or data-flow changes update [docs/README.md](docs/README.md) in the same change.
- **CI calls make** — GitHub Actions only run `make <target>`; do not duplicate lint/test/build commands in YAML.
- **Secrets** — `.env` is gitignored; document new keys in `.env_template`. Do not put secrets in `.envrc`.

## Local verification

- App: `make lint` and `make test` after the stack is up (`make build` / `make up`). Per-service targets (`lint-backend`, …) use `docker compose exec` and fail if the container is not running.
- CLI docs: relative links resolve; every listed command still appears on the official CLI page.
