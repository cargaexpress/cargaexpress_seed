"""Controlled data-quality defects.

Every defect:
  - is deterministic (it has its own random generator, built from the seed),
  - touches only a small, fixed number of records (SizeConfig.defect_records),
  - is marked inside raw_event.payload with the key "seed_defect",
  - is applied AFTER the normal data, so the normal data never changes.

Defects always run in the order of DEFECTS, no matter the order in the command.
"""

from seed.config import AVAILABLE_DEFECTS, UNSUPPORTED_DEFECTS
from seed.defects import (
    duplicate_webhooks,
    invalid_tracking,
    mixed_dates,
    out_of_order_events,
)

DEFECTS = {
    "mixed_dates": mixed_dates.apply,
    "out_of_order_events": out_of_order_events.apply,
    "duplicate_webhooks": duplicate_webhooks.apply,
    "invalid_tracking": invalid_tracking.apply,
}
assert tuple(DEFECTS) == AVAILABLE_DEFECTS


def parse_defects(text: str) -> tuple:
    """Turn 'mixed_dates,invalid_tracking' into ('mixed_dates', 'invalid_tracking')."""
    names = [item.strip() for item in (text or "").split(",") if item.strip()]
    for name in names:
        if name in UNSUPPORTED_DEFECTS:
            raise ValueError(f"defect '{name}' is not supported: {UNSUPPORTED_DEFECTS[name]}")
        if name not in DEFECTS:
            raise ValueError(
                f"unknown defect '{name}'. Available defects: {', '.join(AVAILABLE_DEFECTS)}"
            )
    return tuple(dict.fromkeys(names))


def apply_defects(ctx, selected) -> None:
    for name, function in DEFECTS.items():
        if name in selected:
            function(ctx, ctx.rng("defect", name))
