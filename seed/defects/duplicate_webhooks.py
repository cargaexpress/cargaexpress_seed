"""Defect: duplicate_webhooks.

Type A carriers send webhooks and sometimes send the same message again
(a retry). raw_event.hash is UNIQUE, so an identical copy could never be stored.
To keep the database valid, the duplicate carries an extra field "retry": 1,
so its hash is different, but the guide, the status and the date are the same.

  - Only raw_event gets the new row. No second tracking_event is created,
    because tracking_event is already unique per (carrier, guide, state, time).
  - The duplicate is marked with payload["seed_defect"] = "duplicate_webhooks".
"""

from datetime import timedelta

from seed.hashing import payload_hash


def apply(ctx, rng):
    webhook_carriers = {c["carrier_id"] for c in ctx.rows["carrier"] if c["modalidad"] == "A"}
    candidates = [
        r for r in ctx.rows["raw_event"]
        if r["carrier_id"] in webhook_carriers and "seed_defect" not in r["payload"]
    ]
    amount = min(ctx.size.defect_records, len(candidates))

    for index in sorted(rng.sample(range(len(candidates)), amount)):
        original = candidates[index]
        payload = dict(original["payload"])
        payload["retry"] = 1
        payload["seed_defect"] = "duplicate_webhooks"
        ctx.add(
            "raw_event",
            raw_id=ctx.next_id("raw_event"),
            carrier_id=original["carrier_id"],
            modalidad=original["modalidad"],
            payload=payload,
            recibido_en=original["recibido_en"] + timedelta(seconds=30),
            hash=payload_hash(original["carrier_id"], payload),
        )
