"""Fixed reference data used by the seed.

IMPORTANT: the project documents do not list the countries, the carrier status
codes, the holidays, the SLA days or the penalty percentages. The values below
are TEST VALUES chosen by the seed (see the technical document).
"""

from datetime import date
from decimal import Decimal

# --- Countries --------------------------------------------------------------
COUNTRY_TZ = {
    "CO": "America/Bogota",
    "MX": "America/Mexico_City",
    "PE": "America/Lima",
}
PHONE_CODES = {"CO": "57", "MX": "52", "PE": "51"}

# 9 distribution centers: (name, city, country)
DISTRIBUTION_CENTERS = [
    ("CD Bogota", "Bogota", "CO"),
    ("CD Medellin", "Medellin", "CO"),
    ("CD Barranquilla", "Barranquilla", "CO"),
    ("CD Mexico City", "Mexico City", "MX"),
    ("CD Guadalajara", "Guadalajara", "MX"),
    ("CD Monterrey", "Monterrey", "MX"),
    ("CD Lima", "Lima", "PE"),
    ("CD Arequipa", "Arequipa", "PE"),
    ("CD Trujillo", "Trujillo", "PE"),
]

# 9 destination regions: (name, country). Index 3 of each country gets +1 SLA day.
REGIONS = [
    ("Caribe", "CO"), ("Andina", "CO"), ("Pacifico", "CO"),
    ("Norte", "MX"), ("Centro", "MX"), ("Sur", "MX"),
    ("Costa", "PE"), ("Sierra", "PE"), ("Selva", "PE"),
]
# Regions that are far away (third region of each country) get one extra SLA day.
FAR_REGION_IDS = (3, 6, 9)

# Shipping types: (name, base SLA business days)
SHIPPING_TYPES = [("STANDARD", 3), ("EXPRESS", 2), ("ECONOMY", 5)]

# Penalty ranges (RN-06): (days_from, days_to, % of freight). Test values.
PENALTY_RULES = [
    (1, 2, Decimal("5.00")),
    (3, 5, Decimal("10.00")),
    (6, None, Decimal("20.00")),
]

# --- Carriers ---------------------------------------------------------------
# 12 carriers: 5 type A (webhooks), 4 type B (REST API), 3 type C (files).
CARRIER_COUNT = 12
CARRIER_MODALITIES = ["A"] * 5 + ["B"] * 4 + ["C"] * 3
# Carrier 12 is the one that falls under 85% for two periods (RN-09).
CARRIER_TWO_BAD_PERIODS = 12
# Carrier 11 only has one bad period: it must NOT go to review.
CARRIER_ONE_BAD_PERIOD = 11

# 14 distinct carrier status codes -> 8 canonical states (RN-01).
# Each carrier uses one of three "styles" (a subset of the 14 codes).
STATUS_STYLES = {
    0: [
        ("CREATED", "CREADO"), ("PICKED_UP", "RECOGIDO"),
        ("IN_TRANSIT", "EN_TRANSITO"), ("HUB_ARRIVAL", "EN_TRANSITO"),
        ("OUT_FOR_DELIVERY", "EN_REPARTO"), ("EXCEPTION", "NOVEDAD"),
        ("WRONG_ADDRESS", "NOVEDAD"), ("DELIVERED", "ENTREGADO"),
        ("RETURNED", "DEVUELTO"), ("LOST", "SINIESTRO"),
    ],
    1: [
        ("PENDING", "CREADO"), ("COLLECTED", "RECOGIDO"),
        ("IN_TRANSIT", "EN_TRANSITO"), ("OUT_FOR_DELIVERY", "EN_REPARTO"),
        ("EXCEPTION", "NOVEDAD"), ("WRONG_ADDRESS", "NOVEDAD"),
        ("DELIVERED", "ENTREGADO"), ("REJECTED", "DEVUELTO"),
        ("DAMAGED", "SINIESTRO"),
    ],
    2: [
        ("CREATED", "CREADO"), ("COLLECTED", "RECOGIDO"),
        ("HUB_ARRIVAL", "EN_TRANSITO"), ("OUT_FOR_DELIVERY", "EN_REPARTO"),
        ("EXCEPTION", "NOVEDAD"), ("WRONG_ADDRESS", "NOVEDAD"),
        ("DELIVERED", "ENTREGADO"), ("RETURNED", "DEVUELTO"),
        ("LOST", "SINIESTRO"), ("DAMAGED", "SINIESTRO"),
    ],
}


def raw_code_for(style: int, canonical: str, address_issue: bool = False) -> str:
    """Return the carrier-specific status code for a canonical state."""
    if canonical == "NOVEDAD":
        return "WRONG_ADDRESS" if address_issue else "EXCEPTION"
    for code, canon in STATUS_STYLES[style]:
        if canon == canonical:
            return code
    raise ValueError(f"style {style} has no code for {canonical}")


# --- Holidays ---------------------------------------------------------------
# SAMPLE holidays for testing only. They are NOT an official calendar.
# In production the holidays come from the Nager.Date API (source F6).
HOLIDAYS = {
    "CO": [
        date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3), date(2026, 5, 1),
        date(2026, 5, 18), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 29),
        date(2026, 7, 20), date(2026, 8, 7), date(2026, 8, 17),
    ],
    "MX": [date(2026, 3, 16), date(2026, 5, 1), date(2026, 9, 16)],
    "PE": [
        date(2026, 4, 2), date(2026, 4, 3), date(2026, 5, 1),
        date(2026, 6, 29), date(2026, 7, 28), date(2026, 7, 29),
    ],
}
CALENDAR_FIRST_DAY = date(2026, 2, 14)
CALENDAR_LAST_DAY = date(2026, 9, 30)

# --- Mock recipient data (fake, safe names) ---------------------------------
FIRST_NAMES = ["Ana", "Luis", "Maria", "Carlos", "Laura", "Jorge", "Sofia", "Diego", "Elena", "Pablo"]
LAST_NAMES = ["Garcia", "Rodriguez", "Martinez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres", "Flores"]
