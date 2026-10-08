"""Settlements (RN-08) and carrier compliance (RN-09)."""

from decimal import Decimal

from seed.calendar_utils import quincena_end, quincena_start
from seed.config import (
    CARRIER_IN_REVIEW,
    COMPLIANCE_THRESHOLD,
    DATA_START,
    REFERENCE_NOW,
)
from seed.reference_data import CARRIER_ONE_BAD_PERIOD, CARRIER_TWO_BAD_PERIODS
from datetime import timedelta

ZERO = Decimal("0.00")


def generate(ctx):
    _settlements(ctx)
    _compliance(ctx)


def _closed_quincenas():
    """Starts of every half-month that is already closed at REFERENCE_NOW."""
    current_start = quincena_start(REFERENCE_NOW.date())
    starts, day = [], quincena_start(DATA_START)
    while day < current_start:
        starts.append(day)
        day = quincena_start(quincena_end(day) + timedelta(days=1))
    return starts


def _settlements(ctx):
    """One settlement per brand and closed half-month, using netting (RN-08).

    net = penalties paid to the brand - penalties collected from the carrier
    """
    current_start = quincena_start(REFERENCE_NOW.date())
    groups = {}
    for penalty in ctx.rows["penalty"]:
        brand_id, delivered_day = ctx.penalty_meta[penalty["penalty_id"]]
        start = quincena_start(delivered_day)
        if start >= current_start:
            continue  # the half-month is still open: no settlement yet
        groups.setdefault((start, brand_id), []).append(penalty)

    for start, brand_id in sorted(groups):
        penalties = groups[(start, brand_id)]
        to_pay = sum((p["monto_marca"] for p in penalties), ZERO)
        to_collect = sum((p["monto_traslado"] for p in penalties), ZERO)
        settlement_id = ctx.next_id("settlement")
        ctx.add(
            "settlement",
            settlement_id=settlement_id,
            brand_id=brand_id,
            quincena_inicio=start,
            quincena_fin=quincena_end(start),
            a_pagar_marca=to_pay,
            a_cobrar_transportadora=to_collect,
            neto=to_pay - to_collect,
        )
        for penalty in penalties:
            penalty["settlement_id"] = settlement_id


def _compliance(ctx):
    """Compliance % per carrier and closed half-month.

    These numbers are mock values (they are not recalculated from the guides).
    Carrier 12 stays under 85% for two consecutive periods -> EN_REVISIÓN.
    Carrier 11 has only ONE bad period -> must stay ACTIVO.
    """
    rng = ctx.rng("compliance")
    quincenas = _closed_quincenas()
    two_bad = {5: Decimal("82.50"), 6: Decimal("79.00"), 7: Decimal("81.00")}  # May 16 -> Jun 16

    for carrier in ctx.rows["carrier"]:
        carrier_id = carrier["carrier_id"]
        values = []
        for index, _start in enumerate(quincenas):
            normal = Decimal(rng.randint(8800, 9950)) / 100
            if carrier_id == CARRIER_TWO_BAD_PERIODS and index in two_bad:
                value = two_bad[index]
            elif carrier_id == CARRIER_ONE_BAD_PERIOD and index == 3:
                value = Decimal("83.50")
            else:
                value = normal
            values.append(value.quantize(Decimal("0.01")))

        in_review_any = False
        for index, start in enumerate(quincenas):
            review = (
                values[index] < COMPLIANCE_THRESHOLD
                and index > 0
                and values[index - 1] < COMPLIANCE_THRESHOLD
            )
            in_review_any = in_review_any or review
            ctx.add(
                "carrier_compliance",
                carrier_id=carrier_id,
                quincena=start,
                cumplimiento_pct=values[index],
                en_revision=review,
            )
        if in_review_any:
            carrier["estado"] = CARRIER_IN_REVIEW
