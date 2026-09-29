"""Query-argument readers shared by feature routes.

These exist so a normalization rule is written down once. Five route modules
had each grown their own ``_resolve_fab_name`` and two of them had drifted to a
different rule (no ``.upper()``), which nothing caught: the mocks re-normalize
internally, so the divergence is invisible at home and only surfaces when an
office adapter forwards the raw string to a case-sensitive keyword query.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import abort, request

# Korea has no DST, so a fixed +09:00 offset is exact (mirrors
# ``_office_search.KST``, which routes cannot import -- that is office-side
# plumbing and routes run under both providers).
_KST = timezone(timedelta(hours=9), "KST")


def resolve_fab_name(arg: str = "fab_name") -> str | None:
    """Read a single fab_name, uppercased. ``None`` means "no fab filter".

    ``strip().upper()`` matches ``_logging.policy.normalize_fab_name_list``,
    which is what the log writer indexes through — the canonical form of a fab
    name in this system is uppercase.

    Empty collapses to ``None`` rather than ``""`` because the two mean
    opposite things downstream: ``None`` is "every fab", ``""`` would be "the
    fab whose name is the empty string", i.e. no rows.

    A comma is a caller bug, not a value — the multi-fab UI joins its selection
    into one route segment ("r3,r4") and a screen that forwards that segment to
    a single-fab endpoint gets a name no fab has. Every mock ignores fab_name
    or re-normalizes it, so at home this returns a cheerful 200; at the office
    it builds a Redis key that does not exist and a keyword term that matches
    nothing, and the screen reports the tool as unreachable. 400 here is what
    makes that visible in the environment where it is cheap to find. Callers
    that legitimately take a list use ``resolve_fab_names``.
    """
    raw = (request.args.get(arg) or "").strip().upper()
    if "," in raw:
        abort(400, description=f"{arg} takes one fab, not a list: {raw!r}")
    return raw or None


def resolve_fab_names(arg: str = "fab_name") -> tuple[str, ...]:
    """Read a comma-separated fab_name list, uppercased, blanks dropped."""
    raw = request.args.get(arg) or ""
    return tuple(part.strip().upper() for part in raw.split(",") if part.strip())


def parse_kst_wall(raw: str | None) -> datetime | None:
    """Inbound ISO timestamp -> a naive **KST wall clock**.

    The office OpenSearch indices store offset-less KST wall clock
    (``docs/datatables/README.md``), and the hardware office adapters put the
    values returned here straight into a range clause. So an offset must be
    CONVERTED, never deleted: the frontend sends
    ``new Date().toISOString()``, which always renders UTC, and merely
    stripping its ``Z`` leaves a UTC wall clock wearing a KST label -- every
    window then slides nine hours into the past and the newest ~9h of data
    silently falls outside it.

    A value that arrives without an offset (a hand-built deep link) is already
    a KST wall clock and passes through unshifted. Normalizing to naive here
    also keeps a route's window comparison total: an aware ``start`` next to a
    naive fallback raises TypeError. Shared by the hardware window and the
    meas_hist window route, so this rule is written down once.
    """
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(_KST).replace(tzinfo=None)
