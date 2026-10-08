"""Shared state used while the dataset is being built.

The Context keeps:
  - the rows of every table (a dict: table name -> list of dicts),
  - one counter per table to create stable, deterministic IDs,
  - small lookup tables used by the generators,
  - a helper to create independent random generators.
"""

import random

from seed.calendar_utils import BusinessCalendar
from seed.config import SizeConfig
from seed.reference_data import HOLIDAYS

# Insert order: parents first, children later (so foreign keys are always valid).
TABLE_ORDER = [
    "brand", "distribution_center", "shipping_type", "region", "carrier",
    "calendar_day", "carrier_status_map", "sla_rule", "penalty_rule",
    "orders", "recipient", "order_line", "picking_task", "picking_line",
    "shipping_label", "dispatch", "label_line",
    "raw_event", "tracking_event", "shipment_status", "unmatched_event",
    "shipment_sla", "settlement", "penalty", "carrier_compliance",
]


class Lookup:
    """Small in-memory tables used by the generators (not written to the DB)."""

    def __init__(self):
        self.cds = {}          # cd_id -> row
        self.regions = {}      # region_id -> row
        self.carriers = {}     # carrier_id -> {"modalidad": ..., "style": ...}
        self.sla_days = {}     # (brand_id, tipo_envio_id, region_id) -> business days
        self.penalty_rules = []


class Context:
    def __init__(self, size: SizeConfig, seed: int):
        self.size = size
        self.seed = seed
        self.rows = {name: [] for name in TABLE_ORDER}
        self.lookup = Lookup()
        self.calendar = BusinessCalendar(HOLIDAYS)
        self.penalty_meta = {}  # penalty_id -> (brand_id, delivered_day)
        self._counters = {}

    def next_id(self, table: str) -> int:
        self._counters[table] = self._counters.get(table, 0) + 1
        return self._counters[table]

    def add(self, table: str, **row) -> dict:
        self.rows[table].append(row)
        return row

    def rng(self, *parts) -> random.Random:
        """An independent random generator for one part of the dataset.

        The generator is created from the text '<seed>:<part>:<part>...'.
        Same text -> same numbers, on every machine and every run.
        """
        text = ":".join(str(p) for p in (self.seed, *parts))
        return random.Random(text)
