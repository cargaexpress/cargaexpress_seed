"""Database connection helpers.

The default URL matches the PostgreSQL container defined in docker-compose.yml,
so a developer does not need to configure anything to run the project locally.
To use another database, set the DATABASE_URL environment variable.
"""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://cargaexpress:cargaexpress@localhost:5432/cargaexpress"
)


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine(url: str | None = None) -> Engine:
    engine = create_engine(url or get_database_url())

    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless we turn them on.
        # The tests use SQLite, so we want the same FK checks as PostgreSQL.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine
