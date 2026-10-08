"""Acceptance criterion 4: the size flag controls the amount of data."""

import pytest

from seed.config import SIZES
from seed.generators import build_dataset
from tests.helpers import table_counts


def test_sizes_grow_from_small_to_large():
    assert SIZES["small"].orders < SIZES["medium"].orders < SIZES["large"].orders
    assert SIZES["small"].brands < SIZES["medium"].brands < SIZES["large"].brands


@pytest.mark.parametrize("size", ["small", "medium"])
def test_database_has_the_configured_volume(size, run_seed, engine):
    run_seed("--size", size, "--seed", "42")
    counts = table_counts(engine)
    config = SIZES[size]

    assert counts["brand"] == config.brands
    assert counts["orders"] == config.orders
    assert counts["carrier"] == 12
    assert counts["distribution_center"] == 9
    # An order has between 1 and 3 guides.
    assert config.orders <= counts["shipping_label"] <= config.orders * 3
    # The more brands, the more SLA rules (brands x 3 shipping types x 9 regions).
    assert counts["sla_rule"] == config.brands * 3 * 9


@pytest.mark.slow
def test_large_volume_is_built_as_configured():
    # The large dataset is only built in memory: writing it to SQLite would be slow.
    dataset = build_dataset("large", 42)
    config = SIZES["large"]
    assert len(dataset["brand"]) == config.brands
    assert len(dataset["orders"]) == config.orders
    assert len(dataset["shipping_label"]) >= config.orders
