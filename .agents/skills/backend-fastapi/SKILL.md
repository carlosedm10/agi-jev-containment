---
name: backend-fastapi
description: Scaffolds FastAPI backends with uv, ruff, pyproject.toml, alembic, PostgreSQL, and pytest. Use when creating or extending a FastAPI backend, setting up Python API projects, or when the project-scaffold orchestrator selects FastAPI over DRF.
---

# Backend FastAPI

## When to use

- Default for most REST APIs
- Lightweight services without Django admin or heavy DRF ecosystem needs
- Projects needing async, OpenAPI-first design, or minimal framework overhead

Use **backend-drf** instead when the project needs Django admin, complex permissions, or heavy ORM-centric workflows.

## Environment

Settings read from env vars (`DATABASE_URL`, etc.). Locally, **env-secrets** loads them via `.envrc`/direnv from gitignored `.env`. In Docker, Compose passes the same `.env` via `env_file`.

## Stack

| Tool | Purpose |
|------|---------|
| uv | Package manager and virtual env |
| ruff | Linting and formatting |
| pyproject.toml | Project config and dependencies |
| FastAPI | Web framework |
| SQLAlchemy + alembic | ORM and migrations |
| psycopg | PostgreSQL driver |
| pytest + httpx | Testing |

## Directory layout

```
backend/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
└── app/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── database.py
    └── <feature>/
        ├── __init__.py
        ├── router.py
        ├── models.py
        ├── schemas.py
        └── tests/
            ├── __init__.py
            └── test_<feature>.py
```

Each feature package has its own `tests/` directory.

## Scaffold workflow

1. **Create** `backend/` with `pyproject.toml` (see [reference.md](reference.md)).
2. **Create** `app/main.py` with a health-check route and router includes.
3. **Create** `app/config.py` reading `DATABASE_URL` from env.
4. **Create** `app/database.py` with SQLAlchemy engine/session setup.
5. **Initialize alembic**: create `alembic.ini` and `alembic/env.py` stubs.
6. **Add** a sample feature package with `router.py`, `schemas.py`, `models.py`, and `tests/`.
7. **Configure ruff** in `pyproject.toml` (`[tool.ruff]` section).
8. **Point** to **fastapi-test-generation** for writing tests.

## pyproject.toml essentials

```toml
[project]
name = "PROJECT_SLUG"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy>=2.0",
    "alembic>=1.14",
    "psycopg[binary]>=3.2",
    "pydantic-settings>=2.6",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "httpx>=0.28",
    "ruff>=0.8",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.pytest.ini_options]
testpaths = ["app"]
python_files = ["test_*.py"]
```

## Agent may write

- `pyproject.toml`, `uv.lock` (or instruct `uv lock`)
- App package stubs (`main.py`, `config.py`, `database.py`)
- Feature packages with routers, schemas, models
- Alembic config stubs
- `tests/` directories and sample test files

## Makefile — FastAPI / Alembic section

**makefile-operations** owns lifecycle, package managers, shells, logs, lint, and `clean`.
This skill owns Alembic recipes. Copy the section from [reference.md](reference.md).

| Target | Notes |
|--------|--------|
| `migrate` | Bare verb. `alembic upgrade head`. |
| `alembic-revision` | `MSG="..."`. |
| `db-load-schema-test` | Test-env upgrade; CI calls this before the suite. |
| `test-backend` | `uv run pytest`. Filter with `TEST=`. |

## Agent must NOT execute

- `uv init` / `uv sync` (user runs locally or via Docker after scaffold)
- Database migrations against a live DB without explicit user request

## Integration with sibling skills

| Skill | When |
|-------|------|
| dockerization-template | Docker setup with uvicorn dev command |
| makefile-operations | Generic `up`/`down`/`uv-*`/`bun-*`/`lint`/`logs-*`/`clean`; splice this skill's Alembic section in |
| fastapi-test-generation | Writing endpoint tests |
| github-actions | CI calls `make lint` / `make test` |

## Additional resources

- File templates and the Alembic Makefile section: [reference.md](reference.md)
