"""Orders: one shared builder + the random orders.

add_order() writes an order with its recipient, lines, picking and guides.
generate() creates the random orders. The fixed scenarios (scenarios.py)
also use add_order().

Each random order has its OWN random generator (ctx.rng("order", k)), so the
content of order k never depends on how many orders were created before it.
"""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from seed.calendar_utils import get_tz
from seed.config import DATA_START_UTC, REFERENCE_NOW
from seed.generators.scenarios import SCENARIO_COUNT
from seed.generators.shipments import GuidePlan, add_guide, money
from seed.reference_data import (
    COUNTRY_TZ,
    FIRST_NAMES,
    LAST_NAMES,
    PHONE_CODES,
)

FINISHED_OUTCOMES = ["ON_TIME", "LATE_CARRIER", "LATE_CD", "LATE_BRAND", "RETURNED", "LOST"]
FINISHED_WEIGHTS = [70, 14, 6, 5, 3, 2]
LATE_OUTCOMES = ("LATE_CARRIER", "LATE_CD", "LATE_BRAND")


def add_order(ctx, rng, *, reference, brand_id, cd_id, region_id, tipo_envio_id, created_utc, plans):
    """Create one order and everything below it. Returns the order row."""
    order_id = ctx.next_id("orders")
    order = ctx.add(
        "orders",
        order_id=order_id,
        brand_id=brand_id,
        cd_id=cd_id,
        tipo_envio_id=tipo_envio_id,
        region_id=region_id,
        referencia_marca=reference,
        created_at=created_utc,
    )
    region = ctx.lookup.regions[region_id]

    # Recipient: personal data, kept in its own table (RN-10).
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    ctx.add(
        "recipient",
        order_id=order_id,
        nombre=f"{first} {last}",
        email=f"{first}.{last}.{order_id}@example.com".lower(),
        direccion=f"Calle {rng.randint(1, 150)} # {rng.randint(1, 99)}-{rng.randint(1, 99)}",
        telefono=f"+{PHONE_CODES[region['pais']]}{rng.randint(300000000, 399999999)}",
    )

    # Order lines (at least one line per guide).
    line_ids, line_qty = [], []
    for num in range(1, max(rng.randint(1, 4), len(plans)) + 1):
        line_id = ctx.next_id("order_line")
        qty = rng.randint(1, 5)
        ctx.add(
            "order_line",
            line_id=line_id,
            order_id=order_id,
            num_linea=num,
            sku=f"SKU-{rng.randint(1, 500):04d}",
            cantidad=qty,
            valor_unitario=money(rng.randrange(5000, 120001, 50)),
        )
        line_ids.append(line_id)
        line_qty.append(qty)

    # Picking: starts after creation and ends before the first dispatch.
    first_dispatch = min(p.dispatch_utc for p in plans)
    picking_id = ctx.next_id("picking_task")
    ctx.add(
        "picking_task",
        picking_id=picking_id,
        order_id=order_id,
        inicio=created_utc + timedelta(minutes=rng.randint(10, 50)),
        fin=first_dispatch - timedelta(minutes=15),
        estado="COMPLETADO",
    )
    for line_id, qty in zip(line_ids, line_qty):
        picked = qty if (rng.random() < 0.95 or qty == 1) else qty - 1
        ctx.add(
            "picking_line",
            picking_id=picking_id,
            line_id=line_id,
            cant_solicitada=qty,
            cant_alistada=picked,
        )

    # Guides. Line i goes to guide (i % number of guides).
    label_ids = [add_guide(ctx, order, plan) for plan in plans]
    for index, (line_id, qty) in enumerate(zip(line_ids, line_qty)):
        ctx.add(
            "label_line",
            label_id=label_ids[index % len(label_ids)],
            line_id=line_id,
            cantidad=qty,
        )
    return order


def _trim(moment: datetime) -> datetime:
    return moment.replace(microsecond=0)


def _plan_events(ctx, rng, outcome, *, dispatch_utc, cd_tz, region, sla_days):
    """Create the event timeline for one guide, based on the planned outcome."""
    cal = ctx.calendar
    dest = region["pais"]
    dest_tz = get_tz(COUNTRY_TZ[dest])

    start_day = cal.sla_start_day(dest, dispatch_utc.astimezone(cd_tz))
    if outcome in LATE_OUTCOMES:
        business_days = sla_days + rng.randint(1, 4)   # 1 to 4 days late
    else:
        business_days = rng.randint(1, sla_days)       # inside the SLA
    delivery_day = cal.add_business_days(dest, start_day, business_days)
    delivered = datetime.combine(
        delivery_day, time(rng.randint(9, 17), rng.randint(0, 59)), tzinfo=dest_tz
    ).astimezone(timezone.utc)

    created_evt = dispatch_utc - timedelta(minutes=60)
    picked = dispatch_utc + timedelta(minutes=rng.randint(120, 360))

    if outcome == "LATE_BRAND":
        last_leg = delivered - timedelta(hours=26)       # first delivery attempt
    else:
        last_leg = delivered - timedelta(minutes=rng.randint(90, 240))

    hubs_count = rng.randint(1, 2)
    hubs = [picked + (last_leg - picked) * (i + 1) / (hubs_count + 1) for i in range(hubs_count)]

    events = [("CREADO", created_evt, False), ("RECOGIDO", picked, False)]
    events += [("EN_TRANSITO", hub, False) for hub in hubs]

    if outcome == "LOST":
        events = events[:3] + [("SINIESTRO", delivered, False)]
    elif outcome == "RETURNED":
        events += [
            ("EN_REPARTO", last_leg, False),
            ("NOVEDAD", last_leg + timedelta(minutes=120), False),
            ("DEVUELTO", delivered, False),
        ]
    elif outcome == "LATE_BRAND":
        events += [
            ("EN_REPARTO", last_leg, False),
            ("NOVEDAD", last_leg + timedelta(hours=3), True),   # wrong address
            ("EN_REPARTO", delivered - timedelta(hours=2), False),
            ("ENTREGADO", delivered, False),
        ]
    else:
        events += [("EN_REPARTO", last_leg, False), ("ENTREGADO", delivered, False)]

    # Make sure time always moves forward, even when the plan collides.
    fixed, previous = [], None
    for canonical, moment, is_address in events:
        moment = _trim(moment)
        if previous is not None and moment <= previous:
            moment = previous + timedelta(minutes=10)
        fixed.append((canonical, moment, is_address))
        previous = moment
    return fixed


def generate(ctx):
    cds = list(ctx.lookup.cds.values())
    regions = list(ctx.lookup.regions.values())
    random_orders = ctx.size.orders - SCENARIO_COUNT
    old_limit = REFERENCE_NOW - timedelta(days=14)

    for k in range(1, random_orders + 1):
        rng = ctx.rng("order", k)
        brand_id = rng.randint(1, ctx.size.brands)
        cd = rng.choice(cds)
        same_country = rng.random() < 0.85   # 15% of orders cross a border
        region = rng.choice([r for r in regions if r["pais"] == cd["pais"] or not same_country])
        tipo_id = rng.randint(1, 3)
        guides = rng.choices([1, 2, 3], [85, 12, 3])[0]

        recent = rng.random() < 0.14          # these orders are still in progress
        if recent:
            created = REFERENCE_NOW - timedelta(minutes=rng.randint(30 * 60, 96 * 60))
            outcomes = ["ON_TIME"] * guides
        else:
            span = int((old_limit - DATA_START_UTC).total_seconds())
            created = DATA_START_UTC + timedelta(seconds=rng.randrange(span))
            outcomes = rng.choices(FINISHED_OUTCOMES, FINISHED_WEIGHTS, k=guides)

        handling = rng.randint(1560, 3600) if "LATE_CD" in outcomes else rng.randint(120, 1200)
        cd_tz = get_tz(cd["zona_horaria"])
        sla_days = ctx.lookup.sla_days[(brand_id, tipo_id, region["region_id"])]

        plans = []
        for outcome in outcomes:
            carrier_id = rng.randint(1, len(ctx.lookup.carriers))
            dispatch = created + timedelta(minutes=handling + rng.randint(0, 30))
            plans.append(
                GuidePlan(
                    carrier_id=carrier_id,
                    freight=money(rng.randrange(8000, 45001, 50)),
                    dispatch_utc=dispatch,
                    events=_plan_events(
                        ctx, rng, outcome,
                        dispatch_utc=dispatch, cd_tz=cd_tz, region=region, sla_days=sla_days,
                    ),
                )
            )

        add_order(
            ctx, rng,
            reference=f"REF-{brand_id:03d}-{k:06d}",
            brand_id=brand_id,
            cd_id=cd["cd_id"],
            region_id=region["region_id"],
            tipo_envio_id=tipo_id,
            created_utc=created,
            plans=plans,
        )
