# Task 4 report: FastAPI incident contract and configuration

## Status

Implemented the secured demo incident API, production service dependency, and
required settings. No real HappyRobot calls were made.

## RED evidence

Command:

`uv run pytest app/actions/tests/test_router.py -v`

Result before implementation: 17 tests collected; 12 errors because
`app.actions.router` did not exist and 5 settings tests failed because the
polling fields and validation did not exist.

## GREEN evidence

- `uv run pytest app/actions/tests/test_router.py -v` — 18 passed.
- `uv run pytest -v` — 205 passed.
- `uv run ruff check .` — all checks passed.
- Cursor diagnostics on the changed Python files — no errors.
- `git diff --check` — clean.

The requested Docker/Make commands could not run because Docker is unavailable
in this environment (`docker: command not found`). The equivalent backend
commands were run directly through the project's `uv` environment.

## Files

- Created `backend/app/actions/router.py`.
- Created `backend/app/actions/tests/test_router.py`.
- Modified `backend/app/config.py`.
- Modified `backend/app/main.py`.
- Added only the documented empty `ACTION_DISPATCH_TOKEN` entry for this task
  to `.env_template`; pre-existing user edits in that file were preserved.

## Self-review

- `/incidents/latest` is declared before `/incidents/{incident_id}` and is
  covered by the empty-journal 404 test.
- POST authentication distinguishes missing server configuration (503) from
  missing/wrong caller credentials (401) and uses `secrets.compare_digest`.
- The cached service factory wires `ActionJournal`, `HappyRobotPager`, polling
  settings, on-call settings, and the existing simulation delay.
- FastAPI dependency overrides keep API tests offline.
- Strict integer request validation rejects booleans, floats, and levels
  outside 1–5.
- Only task-owned paths are staged for the commit; unrelated working-tree
  changes remain untouched.

## Commit

`feat: secure demo incident API`

## Concerns

Docker-backed `make test-backend` and `make lint-backend` remain unverified in
this environment. Direct backend tests and lint are green.

## Fix round 1

### RED evidence

`uv run pytest app/actions/tests/test_router.py -v` collected 21 tests and
failed the three new regressions as expected:

- A latin-1 `café` dispatch header raised `TypeError` from `compare_digest`.
- The POST OpenAPI response map omitted status 200.
- `.env_template` omitted both HappyRobot polling variables.

### GREEN evidence

- `uv run pytest app/actions/tests/test_router.py -v` — 21 passed.
- `uv run pytest -q` — 208 passed.
- `uv run ruff check .` — all checks passed.
- `git diff --check` — clean.

The token comparison now encodes both values before constant-time comparison,
the route documents its real 200 no-op response, and the polling defaults are
documented beside the HappyRobot settings. Existing unstaged `.env_template`
edits were preserved through partial staging.

## Fix round 2

Removed the backend pytest that read the repository-root `.env_template`,
because the canonical backend container mounts only the backend project. The
actual polling documentation remains in `.env_template`; no replacement
filesystem test was added.

- `uv run pytest app/actions/tests/test_router.py -q` — 20 passed.
- `uv run pytest -q` — 207 passed.
- `uv run ruff check .` — all checks passed.
- `git diff --check` — clean.
