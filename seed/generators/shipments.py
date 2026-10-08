"""Build everything that belongs to ONE guide (shipping label).

A guide is built from a "plan": the carrier, the freight, the dispatch time and
the list of events. From that plan this module creates:
  shipping_label, dispatch, raw_event, tracking_event, shipment_status,
  shipment_sla and (when it applies) penalty.

Random orders and fixed scenarios use the same function, so both follow the
same business rules.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from seed.calendar_utils import get_tz
from seed.config import (
    CD_MAX_HANDLING_HOURS,
    FINAL_STATES,
    OPEN_NOVELTY_RISK_HOURS,
    REFERENCE_NOW,
    RESPONSIBLE_BRAND,
    RESPONSIBLE_CARRIER,
    RESPONSIBLE_CD,
    RISK_BUSINESS_HOURS,
)
from seed.hashing import payload_hash
from seed.reference_data import COUNTRY_TZ, raw_code_for

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class GuidePlan:
    carrier_id: int
    freight: Decimal
    dispatch_utc: datetime
    # Each event: (canonical_state, utc_datetime, is_address_problem)
    events: list = field(default_factory=list)


def penalty_pct(rules, late_days: int) -> Decimal:
    for rule in rules:
        if rule["dias_desde"] <= late_days and (
            rule["dias_hasta"] is None or late_days <= rule["dias_hasta"]
        ):
            return rule["pct_flete"]
    raise ValueError(f"no penalty rule for {late_days} late days")


def _receive_delay_seconds(rng, modalidad: str) -> int:
    """How long after the event the control tower receives it."""
    if modalidad == "A":   # webhook: almost immediate
        return rng.randint(1, 30)
    if modalidad == "B":   # API polled every 30 minutes
        return rng.randint(60, 1800)
    return rng.randint(600, 14400)  # C: files loaded every 4 hours


def add_guide(ctx, order: dict, plan: GuidePlan) -> int:
    """Create all rows for one guide and return its label_id."""
    look = ctx.lookup
    cal = ctx.calendar
    carrier = look.carriers[plan.carrier_id]
    region = look.regions[order["region_id"]]
    cd = look.cds[order["cd_id"]]

    dest_country = region["pais"]
    dest_tz = get_tz(COUNTRY_TZ[dest_country])
    cd_tz = get_tz(cd["zona_horaria"])

    # --- guide and dispatch -------------------------------------------------
    label_id = ctx.next_id("shipping_label")
    numero_guia = f"G{plan.carrier_id:02d}-{label_id:07d}"
    ctx.add(
        "shipping_label",
        label_id=label_id,
        order_id=order["order_id"],
        carrier_id=plan.carrier_id,
        numero_guia=numero_guia,
        valor_flete=plan.freight,
    )
    ctx.add(
        "dispatch",
        dispatch_id=ctx.next_id("dispatch"),
        label_id=label_id,
        despachado_en=plan.dispatch_utc,
    )

    # --- SLA deadline (RN-03) -----------------------------------------------
    sla_days = look.sla_days[(order["brand_id"], order["tipo_envio_id"], order["region_id"])]
    start_day = cal.sla_start_day(dest_country, plan.dispatch_utc.astimezone(cd_tz))
    deadline_day = cal.sla_deadline_day(dest_country, start_day, sla_days)
    deadline_utc = datetime.combine(deadline_day, time(23, 59, 59), tzinfo=dest_tz).astimezone(
        timezone.utc
    )

    # --- events (only the ones that already happened) -----------------------
    rng = ctx.rng("guide", label_id)
    events = sorted(
        (e for e in plan.events if e[1] <= REFERENCE_NOW), key=lambda e: e[1]
    )

    current_state = None
    current_since = None
    final_reached = False
    delivered_utc = None
    address_problem = False

    for canonical, occurred, is_address in events:
        # RN-02: an event after a final state is kept, but marked as anomaly.
        is_anomaly = final_reached

        raw_id = ctx.next_id("raw_event")
        payload = {
            "numero_guia": numero_guia,
            "estado": raw_code_for(carrier["style"], canonical, is_address),
            "fecha": occurred.isoformat(),
        }
        ctx.add(
            "raw_event",
            raw_id=raw_id,
            carrier_id=plan.carrier_id,
            modalidad=carrier["modalidad"],
            payload=payload,
            recibido_en=occurred + timedelta(seconds=_receive_delay_seconds(rng, carrier["modalidad"])),
            hash=payload_hash(plan.carrier_id, payload),
        )
        ctx.add(
            "tracking_event",
            event_id=ctx.next_id("tracking_event"),
            raw_id=raw_id,
            label_id=label_id,
            carrier_id=plan.carrier_id,
            estado_canonico=canonical,
            ocurrio_en=occurred,
            es_anomalia=is_anomaly,
        )

        if not is_anomaly:
            current_state, current_since = canonical, occurred
            if canonical == "ENTREGADO":
                delivered_utc = occurred
            if canonical == "NOVEDAD" and is_address:
                address_problem = True
            if canonical in FINAL_STATES:
                final_reached = True

    # --- current status -----------------------------------------------------
    novelty_since = current_since if current_state == "NOVEDAD" else None
    ctx.add(
        "shipment_status",
        label_id=label_id,
        estado_actual=current_state,
        actualizado_en=current_since,
        novedad_abierta_desde=novelty_since,
    )

    # --- delay and responsibility (RN-05) -----------------------------------
    late_days = 0
    responsible = None
    delivered_day = None
    if delivered_utc is not None:
        delivered_day = delivered_utc.astimezone(dest_tz).date()
        late_days = cal.business_days_late(dest_country, deadline_day, delivered_day)
        if late_days > 0:
            handling_hours = (plan.dispatch_utc - order["created_at"]).total_seconds() / 3600
            if address_problem:
                responsible = RESPONSIBLE_BRAND
            elif handling_hours > CD_MAX_HANDLING_HOURS:
                responsible = RESPONSIBLE_CD
            else:
                responsible = RESPONSIBLE_CARRIER

    # --- risk (RN-04), calculated against the fixed REFERENCE_NOW -----------
    at_risk = False
    if current_state not in FINAL_STATES:
        remaining = cal.business_hours_between(dest_country, dest_tz, REFERENCE_NOW, deadline_utc)
        if current_state != "EN_REPARTO" and remaining <= RISK_BUSINESS_HOURS:
            at_risk = True
        if novelty_since is not None and REFERENCE_NOW - novelty_since > timedelta(
            hours=OPEN_NOVELTY_RISK_HOURS
        ):
            at_risk = True

    ctx.add(
        "shipment_sla",
        label_id=label_id,
        fecha_limite=deadline_utc,
        dias_retraso=late_days,
        responsable=responsible,
        en_riesgo=at_risk,
    )

    # --- penalty (RN-06) ----------------------------------------------------
    # If the brand caused the delay (wrong address), nothing is owed to the brand.
    if late_days > 0 and responsible in (RESPONSIBLE_CD, RESPONSIBLE_CARRIER):
        pct = penalty_pct(look.penalty_rules, late_days)
        amount = money(plan.freight * pct / 100)
        transfer = amount if responsible == RESPONSIBLE_CARRIER else money(0)
        penalty_id = ctx.next_id("penalty")
        ctx.add(
            "penalty",
            penalty_id=penalty_id,
            label_id=label_id,
            dias_retraso=late_days,
            monto_marca=amount,
            monto_traslado=transfer,
            responsable=responsible,
            settlement_id=None,  # filled in by the billing step
        )
        ctx.penalty_meta[penalty_id] = (order["brand_id"], delivered_day)

    return label_id
