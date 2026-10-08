"""Seed configuration: volumes, defects and fixed project constants.

Everything that a developer may want to tune lives in this file.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class SizeConfig:
    name: str
    brands: int          # number of client brands (the project talks about ~60)
    orders: int          # total orders, including the fixed scenario orders
    defect_records: int  # how many records each enabled defect touches


# Technical decision: these volumes are not defined by the project documents.
SIZES = {
    "small": SizeConfig("small", brands=5, orders=100, defect_records=5),
    "medium": SizeConfig("medium", brands=20, orders=2_000, defect_records=25),
    "large": SizeConfig("large", brands=60, orders=20_000, defect_records=100),
}
DEFAULT_SIZE = "small"
DEFAULT_SEED = 42

# Defects that make sense for the current database model.
AVAILABLE_DEFECTS = (
    "mixed_dates",
    "out_of_order_events",
    "duplicate_webhooks",
    "invalid_tracking",
)

# Defects named by the project that we do NOT implement, and why.
UNSUPPORTED_DEFECTS = {
    "repeated_headers": (
        "it only exists inside Excel/CSV files, and this seed fills database tables"
    ),
}

# --- Fixed "current moment" -------------------------------------------------
# We never call datetime.now(). Risk (RN-04) is calculated against this moment,
# so the dataset is the same today, tomorrow and next year.
REFERENCE_NOW = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)  # 10:00 in Bogota
DATA_START = date(2026, 3, 1)
DATA_START_UTC = datetime(2026, 3, 1, 5, 0, tzinfo=timezone.utc)  # midnight in Bogota

# --- Business constants -----------------------------------------------------
CANONICAL_STATES = (
    "CREADO",
    "RECOGIDO",
    "EN_TRANSITO",
    "EN_REPARTO",
    "NOVEDAD",
    "ENTREGADO",
    "DEVUELTO",
    "SINIESTRO",
)
FINAL_STATES = ("ENTREGADO", "DEVUELTO", "SINIESTRO")  # RN-02

CARRIER_ACTIVE = "ACTIVO"
CARRIER_IN_REVIEW = "EN_REVISIÓN"  # RN-09

CUTOFF_HOUR = 16                # RN-03: after 16:00 the SLA starts next business day
RISK_BUSINESS_HOURS = 24        # RN-04
OPEN_NOVELTY_RISK_HOURS = 12    # RN-04
COMPLIANCE_THRESHOLD = Decimal("85")  # RN-09

# Technical decision (RN-05 does not give a number): if the CD takes more than
# this to dispatch an order, a late delivery is the CD's responsibility.
CD_MAX_HANDLING_HOURS = 24

RESPONSIBLE_CD = "CD"
RESPONSIBLE_CARRIER = "TRANSPORTADORA"
RESPONSIBLE_BRAND = "MARCA"
