"""Defect: invalid_tracking.

Adds carrier messages for tracking numbers that do not exist in the WMS.
Each one gets a raw_event and an unmatched_event (that table has no FK to
shipping_label on purpose). Tracking numbers look like "INVALID-000001".

Marked with payload["seed_defect"] = "invalid_tracking".
"""

from datetime import timedelta

from seed.config import REFERENCE_NOW
from seed.hashing import payload_hash
from seed.reference_data import raw_code_for


def apply(ctx, rng):
    carriers = ctx.rows["carrier"]
    for number in range(1, ctx.size.defect_records + 1):
        carrier = carriers[(number - 1) % len(carriers)]
        carrier_id = carrier["carrier_id"]
        style = ctx.lookup.carriers[carrier_id]["style"]
        guide = f"INVALID-{number:06d}"
        occurred = (REFERENCE_NOW - timedelta(hours=rng.randint(1, 72))).replace(microsecond=0)
        payload = {
            "numero_guia": guide,
            "estado": raw_code_for(style, "EN_TRANSITO"),
            "fecha": occurred.isoformat(),
            "seed_defect": "invalid_tracking",
        }
        raw_id = ctx.next_id("raw_event")
        ctx.add(
            "raw_event",
            raw_id=raw_id,
            carrier_id=carrier_id,
            modalidad=carrier["modalidad"],
            payload=payload,
            recibido_en=occurred + timedelta(seconds=rng.randint(1, 30)),
            hash=payload_hash(carrier_id, payload),
        )
        ctx.add(
            "unmatched_event",
            unmatched_id=ctx.next_id("unmatched_event"),
            raw_id=raw_id,
            carrier_id=carrier_id,
            numero_guia=guide,
            motivo="TRACKING_NUMBER_NOT_FOUND",
        )
