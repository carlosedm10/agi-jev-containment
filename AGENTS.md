# HackSpain 2026 — Agent Instructions

Repo del hackathon HackSpain 2026. Stack: FastAPI (`backend/`) + React/Vite (`frontend/`) + Postgres via Docker.

Read before changing anything:

1. [docs/README.md](docs/README.md) — cliente `hackspain`: instalación, comandos, códigos de salida y convenciones (`--json`).
2. Root `Makefile` — `build`, `up`, `down`, `lint`, `test`, `migrate`.

## Non-negotiable rules

- **Fuente del CLI** — Los comandos y flags se mantienen alineados con [hackspain.app/cli](https://hackspain.app/cli); no inventar subcomandos en este repo.
- **Docs ride the PR** — Si cambia la interfaz pública del CLI en la web oficial, actualizar `docs/README.md` en el mismo cambio.
- **CI calls make** — GitHub Actions only run `make <target>`; do not duplicate lint/test/build commands in YAML.
- **Secrets** — `.env` is gitignored; document new keys in `.env_template`. Do not put secrets in `.envrc`.

## Local verification

- App: `make lint` and `make test` (stack must be up, or CI `make build` + `make up` first).
- CLI docs: revisar enlaces relativos y que cada comando listado siga apareciendo en la página oficial del CLI.
