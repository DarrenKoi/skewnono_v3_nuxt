"""Query-argument readers shared by feature routes.

These exist so a normalization rule is written down once. Five route modules
had each grown their own ``_resolve_fab_name`` and two of them had drifted to a
different rule (no ``.upper()``), which nothing caught: the mocks re-normalize
internally, so the divergence is invisible at home and only surfaces when an
office adapter forwards the raw string to a case-sensitive keyword query.
"""

from __future__ import annotations

from flask import abort, request


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
        abort(400, f"{arg} takes one fab, not a list: {raw!r}")
    return raw or None


def resolve_fab_names(arg: str = "fab_name") -> tuple[str, ...]:
    """Read a comma-separated fab_name list, uppercased, blanks dropped."""
    raw = request.args.get(arg) or ""
    return tuple(part.strip().upper() for part in raw.split(",") if part.strip())
