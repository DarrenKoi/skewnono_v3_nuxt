"""Beam_shape metric registry — the single declaration of every beam_shape
(`type: "total"`) measurement field, its kind, and its plausible value band.

`providers/bsm/mock.py` fabricates each doc straight off this list, and
the hardware page reads the same keys off the returned docs (data-driven
selectors). Adding a future field = one entry here; the mock emits it and the
UI surfaces it with no further code change.

Ranges are anchored to the sample doc in `docs/datatables/hardware_beam_shape.txt`.
`profile16` keys produce a length-16 per-degree array; `scalar` keys produce
one float. The `degree` axis and the `Reso EB Focus` / `Reso EB Focus Range`
fields are emitted by the generator directly (not range-driven), so they are
not in this registry.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class BeamShapeMetric(TypedDict):
    key: str
    kind: Literal["profile16", "scalar"]
    low: float
    high: float


# Order matters only for readability; the generator emits all of them.
BEAM_SHAPE_METRICS: list[BeamShapeMetric] = [
    # --- per-degree 16-arrays --------------------------------------------
    {"key": "Reso EB", "kind": "profile16", "low": 7.90, "high": 8.30},
    {"key": "Reso Detector", "kind": "profile16", "low": 0.0030, "high": 0.0070},
    {"key": "Noise", "kind": "profile16", "low": 6.00, "high": 6.50},
    {"key": "Focus offset", "kind": "profile16", "low": 4.00, "high": 8.00},
    {"key": "Apature angle factor", "kind": "profile16", "low": 0.00100, "high": 0.00160},
    # --- scalars ----------------------------------------------------------
    {"key": "Major Axis", "kind": "scalar", "low": 8.05, "high": 8.20},
    {"key": "Minor Axis", "kind": "scalar", "low": 7.85, "high": 8.00},
    {"key": "Ellipicity", "kind": "scalar", "low": 1.000, "high": 1.060},
    {"key": "Tilt", "kind": "scalar", "low": -45.0, "high": -25.0},
    {"key": "X range", "kind": "scalar", "low": 8.00, "high": 8.15},
    {"key": "Y range", "kind": "scalar", "low": 7.95, "high": 8.05},
    {"key": "Area", "kind": "scalar", "low": 198.0, "high": 208.0},
    {"key": "Ave. Reso Detector", "kind": "scalar", "low": 0.0025, "high": 0.0040},
    {"key": "Ave. Noise", "kind": "scalar", "low": 6.20, "high": 6.35},
    {"key": "Ave. Apature angle factor", "kind": "scalar", "low": 0.00110, "high": 0.00130},
]

PROFILE16_KEYS: list[str] = [m["key"] for m in BEAM_SHAPE_METRICS if m["kind"] == "profile16"]
SCALAR_KEYS: list[str] = [m["key"] for m in BEAM_SHAPE_METRICS if m["kind"] == "scalar"]

__all__ = ["BeamShapeMetric", "BEAM_SHAPE_METRICS", "PROFILE16_KEYS", "SCALAR_KEYS"]
