"""Stable helpers shared only by Hitachi hardware mock adapters."""

import hashlib


def seed_for_equipment(eqp_id: str) -> int:
    """Return a process-stable seed without relying on salted ``hash()``."""
    digest = hashlib.md5(eqp_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)
