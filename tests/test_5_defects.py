"""Acceptance criterion 5: controlled and documented data-quality defects."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seed.config import SIZES
from seed.generators import build_dataset
from app.models import RawEvent, ShippingLabel, TrackingEvent, UnmatchedEvent
from tests.helpers import dump_database, table_counts

N = SIZES["small"].defect_records
ALL_DEFECTS = "mixed_dates,out_of_order_events,duplicate_webhooks,invalid_tracking"


def marked_raw_events(engine, defect):
    with Session(engine) as session:
        return [e for e in session.scalars(select(RawEvent)) if e.payload.get("seed_defect") == defect]


def test_without_defects_nothing_is_marked(run_seed, engine):
    run_seed("--size", "small", "--seed", "42")
    with Session(engine) as session:
        assert [e for e in session.scalars(select(RawEvent)) if "seed_defect" in e.payload] == []
    assert table_counts(engine)["unmatched_event"] == 0


@pytest.mark.parametrize(
    "defect, expected",
    [
        ("mixed_dates", N),
        ("out_of_order_events", 2 * N),  # two raw events per affected guide
        ("duplicate_webhooks", N),
        ("invalid_tracking", N),
    ],
)
def test_each_defect_marks_a_controlled_number_of_records(defect, expected, run_seed, engine):
    run_seed("--size", "small", "--seed", "42", "--defects", defect)
    assert len(marked_raw_events(engine, defect)) == expected


def test_mixed_dates_uses_different_formats(run_seed, engine):
    run_seed("--size", "small", "--seed", "42", "--defects", "mixed_dates")
    values = [e.payload["fecha"] for e in marked_raw_events(engine, "mixed_dates")]
    assert any(isinstance(v, int) for v in values)                       # epoch seconds
    assert any(isinstance(v, str) and "/" in v for v in values)          # dd/mm/yyyy
    assert any(isinstance(v, str) and "-" in v and "T" not in v for v in values)  # mm-dd-yyyy


def test_out_of_order_events_arrive_in_the_wrong_order(run_seed, engine):
    run_seed("--size", "small", "--seed", "42", "--defects", "out_of_order_events")
    with Session(engine) as session:
        raw = {r.raw_id: r for r in session.scalars(select(RawEvent))}
        events = list(session.scalars(select(TrackingEvent)))

    flagged = [
        e for e in events
        if e.es_anomalia and raw[e.raw_id].payload.get("seed_defect") == "out_of_order_events"
    ]
    assert len(flagged) == N
    for event in flagged:
        same_guide = sorted((x for x in events if x.label_id == event.label_id), key=lambda x: x.ocurrio_en)
        next_event = same_guide[same_guide.index(event) + 1]
        # The next event happened later, but it was received BEFORE this one.
        assert raw[next_event.raw_id].recibido_en < raw[event.raw_id].recibido_en


def test_duplicate_webhooks_repeat_a_message_but_not_the_tracking_event(run_seed, engine, tmp_path):
    from tests.helpers import sqlite_url
    from app.database import create_db_engine

    baseline_url = sqlite_url(tmp_path / "baseline.db")
    run_seed("--size", "small", "--seed", "42", url=baseline_url)
    baseline_engine = create_db_engine(baseline_url)
    baseline = table_counts(baseline_engine)
    baseline_engine.dispose()

    run_seed("--size", "small", "--seed", "42", "--defects", "duplicate_webhooks")
    counts = table_counts(engine)
    assert counts["raw_event"] == baseline["raw_event"] + N
    assert counts["tracking_event"] == baseline["tracking_event"]   # no second event

    duplicates = marked_raw_events(engine, "duplicate_webhooks")
    with Session(engine) as session:
        originals = [r for r in session.scalars(select(RawEvent)) if "seed_defect" not in r.payload]
    for duplicate in duplicates:
        assert duplicate.payload["retry"] == 1
        same_message = [
            o for o in originals
            if all(o.payload[k] == duplicate.payload[k] for k in ("numero_guia", "estado", "fecha"))
        ]
        assert len(same_message) == 1


def test_invalid_tracking_creates_unmatched_events(run_seed, engine):
    run_seed("--size", "small", "--seed", "42", "--defects", "invalid_tracking")
    with Session(engine) as session:
        unmatched = list(session.scalars(select(UnmatchedEvent)))
        real_guides = set(session.scalars(select(ShippingLabel.numero_guia)))
    assert len(unmatched) == N
    for item in unmatched:
        assert item.numero_guia.startswith("INVALID-")
        assert item.numero_guia not in real_guides


def test_defects_do_not_change_the_normal_data(run_seed, engine, tmp_path):
    from tests.helpers import sqlite_url
    from app.database import create_db_engine

    clean_url = sqlite_url(tmp_path / "clean.db")
    run_seed("--size", "small", "--seed", "42", url=clean_url)
    run_seed("--size", "small", "--seed", "42", "--defects", ALL_DEFECTS)

    clean_engine = create_db_engine(clean_url)
    try:
        clean, dirty = dump_database(clean_engine), dump_database(engine)
    finally:
        clean_engine.dispose()

    untouched = [
        "brand", "carrier", "orders", "recipient", "order_line", "shipping_label",
        "dispatch", "shipment_sla", "shipment_status", "penalty", "settlement", "carrier_compliance",
    ]
    for table in untouched:
        assert clean[table] == dirty[table], table


def test_all_defects_together_are_reproducible():
    defects = tuple(ALL_DEFECTS.split(","))
    assert build_dataset("small", 42, defects) == build_dataset("small", 42, defects)


def test_repeated_headers_is_rejected_with_a_clear_message(run_seed, capsys):
    with pytest.raises(SystemExit) as error:
        run_seed("--defects", "repeated_headers")
    assert error.value.code == 2
    assert "repeated_headers" in capsys.readouterr().err


def test_unknown_defect_is_rejected(run_seed):
    with pytest.raises(SystemExit) as error:
        run_seed("--defects", "does_not_exist")
    assert error.value.code == 2
