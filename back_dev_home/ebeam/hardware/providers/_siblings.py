"""Shared deterministic helpers for the fleet-style hardware mocks (mdc/sce)
and the metadata tail every faithful doc carries.

Same seed-from-id trick the other providers use, so a given (eqp_id, fab_name)
always yields the same sibling set, IPs, and fac_id across requests/restarts.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime


# Anchor "today" so generated dates are stable regardless of wall clock.
NOW = datetime(2026, 5, 24, 9, 0)


def seed_for(eqp_id: str) -> int:
    """Stable int seed from the equipment id (md5, process-salt-free)."""
    digest = hashlib.md5(eqp_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _seed_for_pair(eqp_id: str, fab_name: str | None) -> int:
    digest = hashlib.md5(f"{eqp_id}|{fab_name or ''}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def fac_id_for(fab_name: str | None) -> str:
    """Derive fac_id from a fab_name the way sem_list builds it.

    `M16B` -> `M16`; `R3`/`R4` -> themselves; unknown/None -> 'M16'.
    """
    if not fab_name:
        return "M16"
    name = fab_name.strip().upper()
    if name in {"R3", "R4"}:
        return name
    m = re.match(r"^(M\d{2})[A-C]?$", name)
    if m:
        return m.group(1)
    return name


def eqp_ip_for(eqp_id: str) -> str:
    """Deterministic plausible IP for the metadata tail (177./197. nets)."""
    rng = random.Random(seed_for(eqp_id) ^ 0x49502049)  # distinct stream
    prefix = "177" if rng.random() < 0.5 else "197"
    return f"{prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"


def _prefix_of(eqp_id: str) -> str:
    m = re.match(r"^([A-Za-z]+)", eqp_id)
    return m.group(1) if m else "ECXDX"


def sibling_eqp_ids(
    eqp_id: str,
    fab_name: str | None,
    *,
    count_low: int = 3,
    count_high: int = 5,
) -> list[str]:
    """`eqp_id` first, then 3-5 stable same-prefix in-fab siblings.

    Siblings share the requested tool's id prefix (the in-fab cohort) and are
    seeded from (eqp_id, fab_name) so the set is stable per scope.
    """
    rng = random.Random(_seed_for_pair(eqp_id, fab_name))
    prefix = _prefix_of(eqp_id)
    n = rng.randint(count_low, count_high)
    result: list[str] = [eqp_id]
    seen = {eqp_id}
    attempts = 0
    while len(result) < n + 1 and attempts < 200:
        attempts += 1
        candidate = f"{prefix}{rng.randint(100, 999)}"
        if candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


__all__ = [
    "NOW",
    "seed_for",
    "fac_id_for",
    "eqp_ip_for",
    "sibling_eqp_ids",
]
