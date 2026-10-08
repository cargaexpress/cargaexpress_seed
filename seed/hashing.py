"""Deterministic hash used by raw_event.hash (the UNIQUE column)."""

import hashlib
import json


def payload_hash(carrier_id: int, payload: dict) -> str:
    text = json.dumps(
        {"carrier_id": carrier_id, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
