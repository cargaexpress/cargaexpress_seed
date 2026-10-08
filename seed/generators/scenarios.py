"""Fixed scenario orders.

These orders are ALWAYS created, with the same dates, for every size and seed.
Their reference starts with "SCN-" so they are easy to find. They cover the
business rules of the project (RN-02 to RN-10) in a controlled way.

All times are LOCAL times written as 'YYYY-MM-DD HH:MM'. Calendar facts used:
  - 2026-03-23 is a Monday and a (sample) holiday in Colombia.
  - 2026-03-16 is a Monday and a (sample) holiday in Mexico, but not in Peru.
  - SLA days: STANDARD = 3, EXPRESS = 2 (regions Caribe, Andina, Costa).
"""

from seed.calendar_utils import local_to_utc
from seed.generators.shipments import GuidePlan, money
from seed.reference_data import COUNTRY_TZ

BRAND_PREMIUM = 1      # brand 1 is premium
BRAND_REGULAR = 2
CD_BOGOTA = 1
CD_MEXICO_CITY = 4
REGION_CARIBE, REGION_ANDINA, REGION_COSTA = 1, 2, 7
STANDARD, EXPRESS = 1, 2


def _at(country: str, text: str):
    return local_to_utc(COUNTRY_TZ[country], text)


def _ev(country, state, text, address=False):
    return (state, _at(country, text), address)


def _plan(carrier_id, freight, country, dispatch_text, events):
    return GuidePlan(
        carrier_id=carrier_id,
        freight=money(freight),
        dispatch_utc=_at(country, dispatch_text),
        events=events,
    )


def _scenarios():
    co = "CO"
    return [
        # SCN-01: normal dispatch, delivered inside the SLA.
        dict(ref="SCN-01-NORMAL-ON-TIME", brand=BRAND_PREMIUM, cd=CD_BOGOTA, region=REGION_CARIBE,
             tipo=STANDARD, created=(co, "2026-03-10 08:00"),
             plans=[_plan(1, 20000, co, "2026-03-10 10:00", [
                 _ev(co, "CREADO", "2026-03-10 09:00"), _ev(co, "RECOGIDO", "2026-03-10 12:00"),
                 _ev(co, "EN_TRANSITO", "2026-03-10 20:00"), _ev(co, "EN_REPARTO", "2026-03-12 09:00"),
                 _ev(co, "ENTREGADO", "2026-03-12 15:00")])]),
        # SCN-02: the CA-02 example. Friday 17:00 (after cutoff), Monday is a holiday.
        # Day 0 = Saturday, deadline = Wednesday 2026-03-25. Delivered on time.
        dict(ref="SCN-02-AFTER-CUTOFF-HOLIDAY", brand=BRAND_PREMIUM, cd=CD_BOGOTA, region=REGION_ANDINA,
             tipo=EXPRESS, created=(co, "2026-03-20 14:00"),
             plans=[_plan(2, 18000, co, "2026-03-20 17:00", [
                 _ev(co, "CREADO", "2026-03-20 16:30"), _ev(co, "RECOGIDO", "2026-03-20 19:00"),
                 _ev(co, "EN_TRANSITO", "2026-03-21 08:00"), _ev(co, "EN_REPARTO", "2026-03-25 08:30"),
                 _ev(co, "ENTREGADO", "2026-03-25 11:00")])]),
        # SCN-03: late delivery, the carrier is responsible (penalty is passed on).
        dict(ref="SCN-03-LATE-CARRIER", brand=BRAND_REGULAR, cd=CD_BOGOTA, region=REGION_CARIBE,
             tipo=STANDARD, created=(co, "2026-04-06 07:30"),
             plans=[_plan(3, 20000, co, "2026-04-06 09:00", [
                 _ev(co, "CREADO", "2026-04-06 08:30"), _ev(co, "RECOGIDO", "2026-04-06 11:00"),
                 _ev(co, "EN_TRANSITO", "2026-04-07 07:00"), _ev(co, "EN_TRANSITO", "2026-04-09 18:00"),
                 _ev(co, "EN_REPARTO", "2026-04-13 08:00"), _ev(co, "ENTREGADO", "2026-04-13 11:30")])]),
        # SCN-04: the CD took 54 hours to dispatch, so the CD is responsible.
        dict(ref="SCN-04-LATE-CD", brand=BRAND_REGULAR, cd=CD_BOGOTA, region=REGION_ANDINA,
             tipo=STANDARD, created=(co, "2026-04-14 08:00"),
             plans=[_plan(4, 18000, co, "2026-04-16 14:00", [
                 _ev(co, "CREADO", "2026-04-16 13:30"), _ev(co, "RECOGIDO", "2026-04-16 16:00"),
                 _ev(co, "EN_TRANSITO", "2026-04-17 09:00"), _ev(co, "EN_REPARTO", "2026-04-22 08:00"),
                 _ev(co, "ENTREGADO", "2026-04-22 10:30")])]),
        # SCN-05: wrong-address NOVEDAD, the brand is responsible (no penalty).
        dict(ref="SCN-05-ADDRESS-ISSUE", brand=BRAND_PREMIUM, cd=CD_BOGOTA, region=REGION_CARIBE,
             tipo=STANDARD, created=(co, "2026-05-04 08:00"),
             plans=[_plan(5, 22000, co, "2026-05-04 10:00", [
                 _ev(co, "CREADO", "2026-05-04 09:30"), _ev(co, "RECOGIDO", "2026-05-04 12:00"),
                 _ev(co, "EN_TRANSITO", "2026-05-05 08:00"), _ev(co, "EN_REPARTO", "2026-05-07 08:00"),
                 _ev(co, "NOVEDAD", "2026-05-07 11:00", address=True),
                 _ev(co, "EN_REPARTO", "2026-05-09 08:00"), _ev(co, "ENTREGADO", "2026-05-09 12:00")])]),
        # SCN-06: one order, two guides (RN-07). One is on time, the other is late.
        dict(ref="SCN-06-MULTI-GUIDE", brand=BRAND_PREMIUM, cd=CD_BOGOTA, region=REGION_CARIBE,
             tipo=STANDARD, created=(co, "2026-05-12 08:00"),
             plans=[
                 _plan(5, 15000, co, "2026-05-12 10:00", [
                     _ev(co, "CREADO", "2026-05-12 09:30"), _ev(co, "RECOGIDO", "2026-05-12 13:00"),
                     _ev(co, "EN_TRANSITO", "2026-05-13 08:00"), _ev(co, "EN_REPARTO", "2026-05-14 09:00"),
                     _ev(co, "ENTREGADO", "2026-05-14 14:00")]),
                 _plan(6, 16000, co, "2026-05-12 10:30", [
                     _ev(co, "CREADO", "2026-05-12 10:00"), _ev(co, "RECOGIDO", "2026-05-12 14:00"),
                     _ev(co, "EN_TRANSITO", "2026-05-13 09:00"), _ev(co, "EN_REPARTO", "2026-05-20 08:00"),
                     _ev(co, "ENTREGADO", "2026-05-20 11:00")]),
             ]),
        # SCN-07: an event arrives after a final state (RN-02).
        dict(ref="SCN-07-EVENT-AFTER-FINAL", brand=BRAND_REGULAR, cd=CD_BOGOTA, region=REGION_ANDINA,
             tipo=STANDARD, created=(co, "2026-05-25 08:00"),
             plans=[_plan(7, 19000, co, "2026-05-25 10:00", [
                 _ev(co, "CREADO", "2026-05-25 09:30"), _ev(co, "RECOGIDO", "2026-05-25 12:00"),
                 _ev(co, "EN_TRANSITO", "2026-05-25 20:00"), _ev(co, "EN_REPARTO", "2026-05-26 08:00"),
                 _ev(co, "ENTREGADO", "2026-05-26 11:00"), _ev(co, "EN_TRANSITO", "2026-05-26 14:00")])]),
        # SCN-08: dispatched on a Saturday. Deadline is 2026-07-01 (Sunday and the
        # Monday holiday do not count). Still EN_TRANSITO "today" -> at risk.
        dict(ref="SCN-08-RISK-DEADLINE", brand=BRAND_PREMIUM, cd=CD_BOGOTA, region=REGION_CARIBE,
             tipo=EXPRESS, created=(co, "2026-06-27 07:00"),
             plans=[_plan(8, 17000, co, "2026-06-27 10:00", [
                 _ev(co, "CREADO", "2026-06-27 09:30"), _ev(co, "RECOGIDO", "2026-06-27 13:00"),
                 _ev(co, "EN_TRANSITO", "2026-06-30 08:00")])]),
        # SCN-09: same dates, but already EN_REPARTO -> NOT at risk.
        dict(ref="SCN-09-DEADLINE-IN-DELIVERY", brand=BRAND_REGULAR, cd=CD_BOGOTA, region=REGION_CARIBE,
             tipo=EXPRESS, created=(co, "2026-06-27 07:00"),
             plans=[_plan(9, 17000, co, "2026-06-27 10:30", [
                 _ev(co, "CREADO", "2026-06-27 10:00"), _ev(co, "RECOGIDO", "2026-06-27 13:00"),
                 _ev(co, "EN_TRANSITO", "2026-06-30 08:00"), _ev(co, "EN_REPARTO", "2026-07-01 08:00")])]),
        # SCN-10: a NOVEDAD open for 16 hours -> at risk (more than 12 h).
        dict(ref="SCN-10-RISK-OPEN-NOVELTY", brand=BRAND_PREMIUM, cd=CD_BOGOTA, region=REGION_ANDINA,
             tipo=STANDARD, created=(co, "2026-06-30 07:00"),
             plans=[_plan(10, 21000, co, "2026-06-30 08:30", [
                 _ev(co, "CREADO", "2026-06-30 08:00"), _ev(co, "RECOGIDO", "2026-06-30 10:30"),
                 _ev(co, "EN_TRANSITO", "2026-06-30 13:00"), _ev(co, "EN_REPARTO", "2026-06-30 15:00"),
                 _ev(co, "NOVEDAD", "2026-06-30 18:00")])]),
        # SCN-11: dispatched ON a public holiday (2026-03-23). Day 0 = next business day.
        dict(ref="SCN-11-HOLIDAY-DISPATCH", brand=BRAND_REGULAR, cd=CD_BOGOTA, region=REGION_CARIBE,
             tipo=STANDARD, created=(co, "2026-03-23 08:00"),
             plans=[_plan(11, 20000, co, "2026-03-23 10:00", [
                 _ev(co, "CREADO", "2026-03-23 09:30"), _ev(co, "RECOGIDO", "2026-03-23 13:00"),
                 _ev(co, "EN_TRANSITO", "2026-03-24 08:00"), _ev(co, "EN_REPARTO", "2026-03-26 08:00"),
                 _ev(co, "ENTREGADO", "2026-03-26 12:00")])]),
        # SCN-12: CD in Mexico (holiday on 2026-03-16), destination in Peru (no holiday).
        # RN-03: the destination calendar is used, so day 0 is the dispatch day.
        dict(ref="SCN-12-CROSS-BORDER", brand=BRAND_PREMIUM, cd=CD_MEXICO_CITY, region=REGION_COSTA,
             tipo=STANDARD, created=("MX", "2026-03-16 08:00"),
             plans=[_plan(12, 25000, "MX", "2026-03-16 10:00", [
                 _ev("MX", "CREADO", "2026-03-16 09:30"), _ev("MX", "RECOGIDO", "2026-03-16 12:00"),
                 _ev("MX", "EN_TRANSITO", "2026-03-17 08:00"), _ev("PE", "EN_REPARTO", "2026-03-19 08:00"),
                 _ev("PE", "ENTREGADO", "2026-03-19 11:00")])]),
    ]


SCENARIO_COUNT = 12


def generate(ctx):
    # Imported here to avoid a circular import (orders imports SCENARIO_COUNT).
    from seed.generators.orders import add_order

    scenarios = _scenarios()
    assert len(scenarios) == SCENARIO_COUNT
    for index, spec in enumerate(scenarios, start=1):
        country, created_text = spec["created"]
        add_order(
            ctx,
            ctx.rng("scenario", index),
            reference=spec["ref"],
            brand_id=spec["brand"],
            cd_id=spec["cd"],
            region_id=spec["region"],
            tipo_envio_id=spec["tipo"],
            created_utc=_at(country, created_text),
            plans=spec["plans"],
        )
