"""Acceptance criterion 3 (second part): existing data is not corrupted."""

from sqlalchemy import insert, text
from sqlalchemy.orm import Session

from app.models import Brand, PenaltyRule
from tests.helpers import table_counts


def test_existing_rows_are_not_overwritten_or_duplicated(run_seed, engine):
    run_seed("--size", "small", "--seed", "42")

    # A developer edits one seeded row and adds one row of their own.
    with engine.begin() as connection:
        connection.execute(
            Brand.__table__.update().where(Brand.brand_id == 1).values(nombre="Edited by developer")
        )
        connection.execute(insert(Brand.__table__).values(brand_id=9999, nombre="My own brand", es_premium=False))
    counts_before = table_counts(engine)

    run_seed("--size", "small", "--seed", "42")

    assert table_counts(engine) == counts_before
    with Session(engine) as session:
        assert session.get(Brand, 1).nombre == "Edited by developer"   # not overwritten
        assert session.get(Brand, 9999).nombre == "My own brand"       # not deleted


def test_missing_rows_are_added_back(run_seed, engine):
    run_seed("--size", "small", "--seed", "42")
    expected = table_counts(engine)

    with engine.begin() as connection:
        connection.execute(PenaltyRule.__table__.delete())   # no other table depends on it
    assert table_counts(engine)["penalty_rule"] == 0

    run_seed("--size", "small", "--seed", "42")
    assert table_counts(engine) == expected


def test_tables_that_are_not_part_of_the_seed_are_left_alone(run_seed, engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE developer_notes (id INTEGER PRIMARY KEY, note TEXT)"))
        connection.execute(text("INSERT INTO developer_notes VALUES (1, 'keep me')"))

    run_seed("--size", "small", "--seed", "42")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT note FROM developer_notes")).scalars().all() == ["keep me"]


def test_reset_is_an_explicit_option(run_seed, engine):
    run_seed("--size", "small", "--seed", "42")
    expected = table_counts(engine)
    with engine.begin() as connection:
        connection.execute(insert(Brand.__table__).values(brand_id=9999, nombre="My own brand", es_premium=False))

    run_seed("--size", "small", "--seed", "42", "--reset")   # only now the tables are dropped

    assert table_counts(engine) == expected
    with Session(engine) as session:
        assert session.get(Brand, 9999) is None
