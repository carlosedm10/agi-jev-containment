# Should fix

1. **`GET /api/items/` does not use the database** — `backend/app/items/router.py` injects `get_db` then returns `[]`. The `Item` model is never queried.
2. **No Alembic revisions** — `backend/alembic/versions/` is empty (`.gitkeep` only). `make migrate` upgrades nothing; the `items` table is not created.
