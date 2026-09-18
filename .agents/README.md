# HackSpain agent skills (`.agents/`)

Project-local [Agent Skills](https://agentskills.io/) for keeping this stack aligned with Factorial's templates (FastAPI, React/Vite, Compose, Makefile, docs, CI).

**Claude Code:** `.claude/skills/` holds git-tracked symlinks into [`skills/`](skills/) — no global install needed.

**Cursor, Codex, OpenCode, Pi, etc.:** install from this directory:

```bash
cd .agents
./install --yes --platforms cursor --skills all --mode symlink
```

Adjust `--platforms` and `--skills` as needed. Use `symlink` to stay in sync with edits under `.agents/skills/`, or `copy` for a frozen snapshot.

## Skills in this repo

| Skill | Use when |
|-------|----------|
| `document-code` | `AGENTS.md`, `docs/README.md`, `docs/cli.md` |
| `makefile-operations` | Root `Makefile`, compose lifecycle |
| `github-actions` | `.github/workflows` (only `make` in CI) |
| `env-secrets` | `.env_template`, `.envrc`, `.env` |
| `backend-fastapi` | `backend/` API, uv, Alembic |
| `frontend-react` | `frontend/` Vite + Bun |
| `dockerization-template` | `compose.yaml`, `docker/` |
| `fastapi-test-generation` | Colocated API tests |
| `generate-pr-description` | PR summaries |
| `pydantic-ai-agents` | pydantic_ai agents in the backend |

Upstream skill sources live in the [agent-skills-template](https://github.com/factorialco/skills) repo; refresh by copying skill folders into `.agents/skills/` or re-running install from that repo.
