"""Small helpers shared by the tests."""

from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.models import Base


def sqlite_url(path: Path) -> str:
    return "sqlite+pysqlite:///" + path.as_posix()


def table_counts(engine) -> dict:
    """{table_name: number_of_rows} for every CargaExpress table."""
    with engine.connect() as connection:
        return {
            table.name: connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in Base.metadata.sorted_tables
        }


def dump_database(engine) -> dict:
    """Every row of every table, sorted by primary key. Used to compare two databases."""
    result = {}
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            rows = connection.execute(select(table).order_by(*table.primary_key.columns)).all()
            result[table.name] = [tuple(row) for row in rows]
    return result


def local_date(value, tz_name: str = "America/Bogota"):
    """Date of a stored UTC datetime in a local time zone (SQLite returns naive values)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(tz_name)).date()
