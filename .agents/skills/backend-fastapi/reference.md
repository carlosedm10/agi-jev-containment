# Backend FastAPI reference templates

Replace `PROJECT_SLUG` with the project slug.

## app/main.py

```python
from fastapi import FastAPI

from app.<feature>.router import router as feature_router

app = FastAPI(title="PROJECT_SLUG")

app.include_router(feature_router, prefix="/api/<feature>", tags=["<feature>"])


@app.get("/health")
def health():
    return {"status": "ok"}
```

## app/config.py

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/PROJECT_SLUG"

    model_config = {"env_file": ".env"}


settings = Settings()
```

## app/database.py

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## app/<feature>/router.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/")
def list_items(db: Session = Depends(get_db)):
    return []
```

## alembic.ini (minimal)

```ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

## alembic/env.py (stub)

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base

# Import all models so alembic can detect them
# from app.<feature>.models import *  # noqa: F401, F403

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## Makefile — FastAPI / Alembic section

Splice this into the project Makefile. Replace `PROJECT_SLUG`.

```makefile
# ----------------------------- FastAPI / Alembic ----------------------------- #
.PHONY: migrate alembic-revision db-load-schema-test

# migrate is deliberately bare — the verb the framework's own docs use.
migrate:
	docker compose exec -T backend-PROJECT_SLUG uv run alembic upgrade head

alembic-revision:
	docker compose exec -T backend-PROJECT_SLUG uv run alembic revision --autogenerate -m "$(MSG)"

db-load-schema-test:
	docker compose exec -T -e ENV=test backend-PROJECT_SLUG uv run alembic upgrade head
```

`test-backend` stays in the Testing section:

```makefile
test-backend:
	docker compose exec -T backend-PROJECT_SLUG uv run pytest $(TEST)
```
