"""Builds the complete dataset in memory (no database needed)."""

from seed.config import SIZES
from seed.context import Context
from seed.defects import apply_defects
from seed.generators import billing, catalogs, orders, scenarios


def build_dataset(size_name: str, seed: int, defects=()) -> dict:
    """Return {table_name: [row dicts]} for the given size, seed and defects."""
    ctx = Context(SIZES[size_name], seed)
    catalogs.generate(ctx)
    scenarios.generate(ctx)   # fixed scenario orders first (they get the first IDs)
    orders.generate(ctx)      # then the random orders
    billing.generate(ctx)     # settlements and carrier compliance
    apply_defects(ctx, defects)
    return ctx.rows
