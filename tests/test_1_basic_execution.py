"""Acceptance criterion 1: one command creates the dataset, no manual inserts."""

from seed.config import SIZES
from tests.helpers import table_counts


def test_basic_execution_creates_dataset(run_seed, engine):
    # The database is empty and has no tables. The command must do everything.
    assert run_seed("--size", "small", "--seed", "42") == 0

    counts = table_counts(engine)
    assert len(counts) == 25
    assert counts["orders"] == SIZES["small"].orders

    # Every table has data, except unmatched_event (it only gets rows with a defect).
    empty_tables = [name for name, total in counts.items() if total == 0 and name != "unmatched_event"]
    assert empty_tables == []
    assert counts["unmatched_event"] == 0


def test_default_arguments_work(run_seed, engine):
    # No arguments: size small and seed 42 are the defaults.
    assert run_seed() == 0
    assert table_counts(engine)["orders"] == SIZES["small"].orders
