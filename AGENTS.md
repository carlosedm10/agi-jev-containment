# AGENTS.md

docs/ is the source of true in case of doubt follow docs instructions.

1. [docs/README.md](docs/README.md) — `hackspain` client: commands, exit codes, and conventions (`--json`).

## Non-negotiable rules

- **Source of truth for the CLI** — Commands and flags must stay aligned with [hackspain.app/cli](https://hackspain.app/cli); do not invent subcommands in this repo.
- **Docs ride the PR** — If the CLI's public interface changes on the official website, update `docs/README.md` in the same change.

## Local verification

- There is no build or tests in this repo; check relative links and that every listed command still appears on the official CLI page.
