"""The seeded data must be able to test the business rules RN-01 to RN-10.

All tests read the same 'small' database (seed 42). The fixed scenario orders
have references that start with "SCN-".
"""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CalendarDay,
    Carrier,
    CarrierCompliance,
    CarrierStatusMap,
    Order,
    Penalty,
    RawEvent,
    Recipient,
    Settlement,
    ShipmentSla,
    ShipmentStatus,
    ShippingLabel,
    TrackingEvent,
)
from tests.helpers import local_date


@pytest.fixture
def session(seeded_small):
    with Session(seeded_small) as session:
        yield session


def guides_of(session, prefix):
    order = session.scalars(select(Order).where(Order.referencia_marca.like(f"{prefix}%"))).one()
    return list(
        session.scalars(
            select(ShippingLabel).where(ShippingLabel.order_id == order.order_id).order_by(ShippingLabel.label_id)
        )
    )


def one_guide(session, prefix):
    guides = guides_of(session, prefix)
    assert len(guides) == 1
    return guides[0]


def penalty_of(session, label_id):
    return session.scalars(select(Penalty).where(Penalty.label_id == label_id)).one_or_none()


# --- RN-01: state normalization ----------------------------------------------
def test_rn01_status_map_covers_all_canonical_states(session):
    rows = list(session.scalars(select(CarrierStatusMap)))
    assert {r.estado_canonico for r in rows} == {
        "CREADO", "RECOGIDO", "EN_TRANSITO", "EN_REPARTO",
        "NOVEDAD", "ENTREGADO", "DEVUELTO", "SINIESTRO",
    }
    assert len({r.estado_origen for r in rows}) == 14   # 14 carrier codes -> 8 states


def test_rn01_every_raw_status_maps_to_the_stored_canonical_state(session):
    mapping = {
        (r.carrier_id, r.estado_origen): r.estado_canonico for r in session.scalars(select(CarrierStatusMap))
    }
    raw = {r.raw_id: r for r in session.scalars(select(RawEvent))}
    for event in session.scalars(select(TrackingEvent)):
        payload = raw[event.raw_id].payload
        assert mapping[(event.carrier_id, payload["estado"])] == event.estado_canonico


# --- RN-02: final states ------------------------------------------------------
def test_rn02_event_after_a_final_state_is_an_anomaly(session):
    guide = one_guide(session, "SCN-07")
    events = list(
        session.scalars(
            select(TrackingEvent).where(TrackingEvent.label_id == guide.label_id).order_by(TrackingEvent.ocurrio_en)
        )
    )
    assert [e.estado_canonico for e in events] == [
        "CREADO", "RECOGIDO", "EN_TRANSITO", "EN_REPARTO", "ENTREGADO", "EN_TRANSITO",
    ]
    assert [e.es_anomalia for e in events] == [False] * 5 + [True]
    # The final state is not replaced.
    assert session.get(ShipmentStatus, guide.label_id).estado_actual == "ENTREGADO"


# --- RN-03: SLA ---------------------------------------------------------------
def test_rn03_dispatch_after_16_and_holiday_in_the_middle(session):
    sla = session.get(ShipmentSla, one_guide(session, "SCN-02").label_id)
    assert local_date(sla.fecha_limite) == date(2026, 3, 25)   # the CA-02 example
    assert sla.dias_retraso == 0


def test_rn03_dispatch_on_a_public_holiday(session):
    sla = session.get(ShipmentSla, one_guide(session, "SCN-11").label_id)
    assert local_date(sla.fecha_limite) == date(2026, 3, 27)


def test_rn03_dispatch_on_a_saturday(session):
    sla = session.get(ShipmentSla, one_guide(session, "SCN-08").label_id)
    assert local_date(sla.fecha_limite) == date(2026, 7, 1)    # Sunday and Monday holiday skipped


def test_rn03_destination_country_calendar_is_used(session):
    # CD in Mexico on a Mexican holiday, destination Peru: the day still counts.
    sla = session.get(ShipmentSla, one_guide(session, "SCN-12").label_id)
    assert local_date(sla.fecha_limite, "America/Lima") == date(2026, 3, 19)


def test_rn03_delivery_inside_and_after_the_sla(session):
    assert session.get(ShipmentSla, one_guide(session, "SCN-01").label_id).dias_retraso == 0
    assert session.get(ShipmentSla, one_guide(session, "SCN-03").label_id).dias_retraso > 0


# --- RN-04: risk --------------------------------------------------------------
def test_rn04_risk_by_deadline_unless_already_in_delivery(session):
    assert session.get(ShipmentSla, one_guide(session, "SCN-08").label_id).en_riesgo is True
    assert session.get(ShipmentSla, one_guide(session, "SCN-09").label_id).en_riesgo is False


def test_rn04_risk_by_open_novelty_for_more_than_12_hours(session):
    guide = one_guide(session, "SCN-10")
    assert session.get(ShipmentSla, guide.label_id).en_riesgo is True
    assert session.get(ShipmentStatus, guide.label_id).novedad_abierta_desde is not None


# --- RN-05: responsibility ----------------------------------------------------
def test_rn05_responsibility_for_cd_carrier_and_brand(session):
    responsible = lambda prefix: session.get(ShipmentSla, one_guide(session, prefix).label_id).responsable
    assert responsible("SCN-03") == "TRANSPORTADORA"
    assert responsible("SCN-04") == "CD"
    assert responsible("SCN-05") == "MARCA"


# --- RN-06: penalties ---------------------------------------------------------
def test_rn06_penalty_is_a_percentage_of_the_freight_and_passed_to_the_carrier(session):
    guide = one_guide(session, "SCN-03")            # 3 days late -> 10% of the freight
    penalty = penalty_of(session, guide.label_id)
    assert float(penalty.monto_marca) == pytest.approx(float(guide.valor_flete) * 0.10)
    assert penalty.monto_traslado == penalty.monto_marca   # carrier is responsible


def test_rn06_cd_penalty_is_not_passed_to_the_carrier(session):
    guide = one_guide(session, "SCN-04")            # 2 days late -> 5% of the freight
    penalty = penalty_of(session, guide.label_id)
    assert float(penalty.monto_marca) == pytest.approx(float(guide.valor_flete) * 0.05)
    assert float(penalty.monto_traslado) == 0.0


def test_rn06_no_penalty_when_the_brand_is_responsible(session):
    assert penalty_of(session, one_guide(session, "SCN-05").label_id) is None


# --- RN-07: several guides ----------------------------------------------------
def test_rn07_order_with_one_guide_on_time_and_one_late(session):
    guides = guides_of(session, "SCN-06")
    assert len(guides) == 2
    delays = sorted(session.get(ShipmentSla, g.label_id).dias_retraso for g in guides)
    assert delays[0] == 0 and delays[1] > 0   # so the order does NOT meet the SLA


# --- RN-08: settlement --------------------------------------------------------
def test_rn08_settlement_uses_netting(session):
    settlements = list(session.scalars(select(Settlement)))
    assert settlements
    for settlement in settlements:
        penalties = list(session.scalars(select(Penalty).where(Penalty.settlement_id == settlement.settlement_id)))
        assert penalties
        paid = sum(float(p.monto_marca) for p in penalties)
        collected = sum(float(p.monto_traslado) for p in penalties)
        assert float(settlement.a_pagar_marca) == pytest.approx(paid)
        assert float(settlement.a_cobrar_transportadora) == pytest.approx(collected)
        assert float(settlement.neto) == pytest.approx(paid - collected)


# --- RN-09: carrier compliance ------------------------------------------------
def below_85(session, carrier_id):
    rows = session.scalars(
        select(CarrierCompliance).where(CarrierCompliance.carrier_id == carrier_id).order_by(CarrierCompliance.quincena)
    )
    return [float(r.cumplimiento_pct) < 85 for r in rows]


def test_rn09_one_carrier_is_under_85_for_two_consecutive_periods(session):
    flags = below_85(session, 12)
    assert any(a and b for a, b in zip(flags, flags[1:]))
    assert session.get(Carrier, 12).estado == "EN_REVISIÓN"
    assert any(r.en_revision for r in session.scalars(select(CarrierCompliance).where(CarrierCompliance.carrier_id == 12)))


def test_rn09_a_single_bad_period_does_not_put_a_carrier_in_review(session):
    flags = below_85(session, 11)
    assert sum(flags) == 1
    assert session.get(Carrier, 11).estado == "ACTIVO"


# --- RN-10: data access -------------------------------------------------------
def test_rn10_two_brands_have_their_own_recipients(session):
    brand_orders = {
        brand_id: set(session.scalars(select(Order.order_id).where(Order.brand_id == brand_id)))
        for brand_id in (1, 2)
    }
    assert brand_orders[1] and brand_orders[2]
    assert brand_orders[1].isdisjoint(brand_orders[2])
    for order_ids in brand_orders.values():
        recipients = list(session.scalars(select(Recipient).where(Recipient.order_id.in_(order_ids))))
        assert len(recipients) == len(order_ids)   # every order has its recipient


# --- Reference data -----------------------------------------------------------
def test_calendar_marks_holidays_and_sundays(session):
    holiday = session.get(CalendarDay, ("CO", date(2026, 3, 23)))
    sunday = session.get(CalendarDay, ("CO", date(2026, 3, 22)))
    assert holiday.es_festivo and not holiday.es_habil
    assert not sunday.es_festivo and not sunday.es_habil
    assert holiday.hora_corte.hour == 16


def test_carriers_follow_the_project_mix(session):
    modalities = [c.modalidad for c in session.scalars(select(Carrier))]
    assert (modalities.count("A"), modalities.count("B"), modalities.count("C")) == (5, 4, 3)
