"""Defect: mixed_dates.

Changes the date INSIDE the raw message (payload["fecha"]) of a few raw events
into formats that are different from ISO 8601. The tracking_event keeps the
correct UTC time, so a test can compare the "dirty" raw value with the truth.

Marked with payload["seed_defect"] = "mixed_dates".
"""

from datetime import datetime

from seed.hashing import payload_hash

# Note: "%d/%m/%Y" and "%m-%d-%Y" are ambiguous when the day is 12 or less.
# That is on purpose: it is a typical real-world date problem.
FORMATS = ["%d/%m/%Y %H:%M", "%m-%d-%Y %H:%M", "epoch", "%Y%m%d%H%M%S"]


def apply(ctx, rng):
    candidates = [r for r in ctx.rows["raw_event"] if "seed_defect" not in r["payload"]]
    amount = min(ctx.size.defect_records, len(candidates))
    for position, index in enumerate(sorted(rng.sample(range(len(candidates)), amount))):
        row = candidates[index]
        original = datetime.fromisoformat(row["payload"]["fecha"])
        chosen = FORMATS[position % len(FORMATS)]
        payload = dict(row["payload"])
        payload["fecha"] = int(original.timestamp()) if chosen == "epoch" else original.strftime(chosen)
        payload["seed_defect"] = "mixed_dates"
        row["payload"] = payload
        row["hash"] = payload_hash(row["carrier_id"], payload)
