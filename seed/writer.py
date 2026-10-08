"""Writes the in-memory dataset into the database, safely.

Idempotency: every row is inserted with "ON CONFLICT DO NOTHING".
  - A row that already exists (same primary key or same UNIQUE value) is skipped.
  - Existing rows are never updated and never deleted.
All tables are written inside ONE transaction: if something fails, nothing stays.
"""

from sqlalchemy import Integer, func, select, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import Base
from seed.context import TABLE_ORDER

CHUNK_SIZE = 2000


def write_dataset(engine, dataset: dict) -> list:
    """Insert the dataset. Returns [(table, rows_in_dataset, rows_inserted), ...]."""
    insert_function = postgres_insert if engine.dialect.name == "postgresql" else sqlite_insert
    report = []

    with engine.begin() as connection:
        for name in TABLE_ORDER:
            table = Base.metadata.tables[name]
            rows = dataset.get(name, [])
            before = connection.execute(select(func.count()).select_from(table)).scalar_one()
            for start in range(0, len(rows), CHUNK_SIZE):
                statement = insert_function(table).on_conflict_do_nothing()
                connection.execute(statement, rows[start:start + CHUNK_SIZE])
            after = connection.execute(select(func.count()).select_from(table)).scalar_one()
            report.append((name, len(rows), after - before))

        if engine.dialect.name == "postgresql":
            _reset_sequences(connection)

    return report


def _reset_sequences(connection) -> None:
    """Move PostgreSQL ID counters after the IDs we inserted by hand.

    We insert explicit IDs (1, 2, 3...). PostgreSQL does not know about them, so
    the next normal INSERT from the application would try ID 1 again and fail.
    """
    for table in Base.metadata.sorted_tables:
        columns = list(table.primary_key.columns)
        if len(columns) == 1 and isinstance(columns[0].type, Integer) and columns[0].autoincrement is not False:
            column = columns[0].name
            connection.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('\"{table.name}\"', '{column}'), "
                    f"COALESCE((SELECT MAX({column}) FROM \"{table.name}\"), 1))"
                )
            )
