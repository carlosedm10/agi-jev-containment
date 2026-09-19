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
