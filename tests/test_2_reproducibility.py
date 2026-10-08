"""Acceptance criterion 2: the same seed gives the same dataset."""

from app.database import create_db_engine
from seed.generators import build_dataset
from tests.helpers import dump_database, sqlite_url


def test_same_seed_builds_the_same_dataset():
    assert build_dataset("small", 42) == build_dataset("small", 42)


def test_different_seed_builds_a_different_dataset():
    assert build_dataset("small", 1) != build_dataset("small", 2)


def test_fixed_scenarios_do_not_depend_on_the_seed():
    first = build_dataset("small", 1)
    second = build_dataset("small", 2)
    scenarios = lambda data: [o["referencia_marca"] for o in data["orders"] if o["referencia_marca"].startswith("SCN-")]
    assert scenarios(first) == scenarios(second)
    assert len(scenarios(first)) == 12


def test_same_seed_gives_equal_databases(run_seed, tmp_path):
    url_a = sqlite_url(tmp_path / "a.db")
    url_b = sqlite_url(tmp_path / "b.db")
    run_seed("--size", "small", "--seed", "42", url=url_a)
    run_seed("--size", "small", "--seed", "42", url=url_b)

    engine_a, engine_b = create_db_engine(url_a), create_db_engine(url_b)
    try:
        assert dump_database(engine_a) == dump_database(engine_b)
    finally:
        engine_a.dispose()
        engine_b.dispose()
