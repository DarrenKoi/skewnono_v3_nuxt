"""Row-value logic shared by the meas_hist mock and office adapters.

`data.py` is a pure dispatcher, so anything every provider must guarantee
about a row lives here and is imported by both adapters instead of being
applied one layer up — where it would silently paper over an adapter that
reports the wrong value rather than making that adapter correct.

`fail_ratio` is a PERCENTAGE, 0..100 — 4.57 means 4.57% of the images failed.
That is the scale the office OpenSearch indices store, and the office value is
authoritative: it is computed upstream at ingestion, so the adapter reads the
field rather than re-deriving it from the counts. The mock has no upstream, so
it derives its own from the counts it generated — on the same scale.

Consequence for callers: nothing downstream multiplies by 100. A renderer
appends "%" to the number as it stands.
"""

from __future__ import annotations


__all__ = ["FAIL_RATIO_MAX", "fail_ratio_percent", "normalize_fail_ratio"]


# A ratio of failed-to-total images cannot exceed "all of them".
FAIL_RATIO_MAX = 100.0


def fail_ratio_percent(fail_images: int, total_images: int) -> float:
    """Percent of images that failed, derived from the counts (mock only).

    The office adapter must NOT use this: office documents carry a stored
    `fail_ratio` computed upstream, and recomputing it here would let this
    app disagree with every other consumer of the same index.
    """
    if total_images <= 0:
        return 0.0
    return normalize_fail_ratio(fail_images / total_images * 100)


def normalize_fail_ratio(value: float | int | str | None) -> float:
    """Coerce a stored fail_ratio onto the contract: a 0..100 float.

    Clamped rather than trusted blindly. A value above 100 is not a ratio at
    all, and rendering one as "457.0%" is how a scale mismatch reaches a user
    as a plausible-looking number instead of an obvious error.
    """
    try:
        ratio = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if ratio != ratio:  # NaN
        return 0.0
    return round(max(0.0, min(FAIL_RATIO_MAX, ratio)), 4)
