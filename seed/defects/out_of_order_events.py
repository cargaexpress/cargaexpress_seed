"""Defect: out_of_order_events.

For a few guides, the second event (RECOGIDO or similar) and the third event
happened in the right order, but the control tower RECEIVED them in the wrong
order: the later event arrives first.

  - The event that arrived late gets tracking_event.es_anomalia = True.
  - Both raw payloads are marked with payload["seed_defect"] = "out_of_order_events".
"""

from datetime import timedelta

from seed.hashing import payload_hash


def apply(ctx, rng):
    events_by_label = {}
    for event in ctx.rows["tracking_event"]:
        events_by_label.setdefault(event["label_id"], []).append(event)
    raw_by_id = {r["raw_id"]: r for r in ctx.rows["raw_event"]}

    eligible = sorted(
        label_id
        for label_id, events in events_by_label.items()
        if len(events) >= 3 and not any(e["es_anomalia"] for e in events)
    )
    amount = min(ctx.size.defect_records, len(eligible))

    for label_id in sorted(rng.sample(eligible, amount)):
        events = sorted(events_by_label[label_id], key=lambda e: e["ocurrio_en"])
        earlier, later = events[1], events[2]
        raw_earlier, raw_later = raw_by_id[earlier["raw_id"]], raw_by_id[later["raw_id"]]

        # The later event is received first, the earlier one arrives after it.
        raw_later["recibido_en"] = later["ocurrio_en"] + timedelta(seconds=30)
        raw_earlier["recibido_en"] = later["ocurrio_en"] + timedelta(seconds=90)
        earlier["es_anomalia"] = True

        for raw in (raw_earlier, raw_later):
            payload = dict(raw["payload"])
            payload["seed_defect"] = "out_of_order_events"
            raw["payload"] = payload
            raw["hash"] = payload_hash(raw["carrier_id"], payload)
