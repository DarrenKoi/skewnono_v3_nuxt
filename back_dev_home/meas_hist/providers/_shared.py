"""Row-value logic shared by the meas_hist mock and office adapters.

`data.py` is a pure dispatcher, so anything every provider must guarantee
about a row lives here and is imported by both adapters instead of being
applied one layer up — where it would silently paper over an adapter that
reports the wrong value rather than making that adapter correct.
"""

from __future__ import annotations


__all__ = ["derive_fail_ratio"]


def derive_fail_ratio(fail_images: int, total_images: int) -> float:
    """Fail ratio as a 0..1 fraction, derived from the image counts.

    The counts are the source of truth; a `fail_ratio` field carried by the
    source is not trusted. The office index has been observed shipping it as
    a percentage (25.0 for 25%), and a count pair can disagree with it
    outright, so deriving here keeps the contract's 0..1 fraction honest.

    Clamped because `fail_images > total_images` is a real (if malformed)
    input, and a ratio above 1.0 would render as a >100% failure bar.
    """
    if total_images <= 0:
        return 0.0
    return round(max(0.0, min(1.0, fail_images / total_images)), 4)
