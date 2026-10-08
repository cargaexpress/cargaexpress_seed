"""Acceptance criterion 3: running the seed again is safe."""

from sqlalchemy import select

from app.models import RawEvent, ShippingLabel
from tests.helpers import dump_database, table_counts


def test_running_twice_does_not_create_duplicates(run_seed, engine):
    run_seed("--size", "small", "--seed", "42")
    counts_after_first = table_counts(engine)
    data_after_first = dump_database(engine)

    run_seed("--size", "small", "--seed", "42")

    assert table_counts(engine) == counts_after_first
    assert dump_database(engine) == data_after_first


def test_natural_keys_stay_unique_after_several_runs(run_seed, engine):
    for _ in range(3):
        run_seed("--size", "small", "--seed", "42")

    with engine.connect() as connection:
        guides = connection.execute(select(ShippingLabel.carrier_id, ShippingLabel.numero_guia)).all()
        hashes = connection.execute(select(RawEvent.hash)).scalars().all()
    assert len(guides) == len(set(guides))
    assert len(hashes) == len(set(hashes))


def test_running_with_defects_twice_is_also_safe(run_seed, engine):
    args = ("--size", "small", "--seed", "42", "--defects", "mixed_dates,invalid_tracking")
    run_seed(*args)
    counts = table_counts(engine)
    run_seed(*args)
    assert table_counts(engine) == counts
