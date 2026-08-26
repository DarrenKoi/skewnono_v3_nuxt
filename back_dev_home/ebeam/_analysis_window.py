"""The ``window_weeks`` axis the two lab pages (tttm, pm-tune) gather data over.

One module rather than a constant in each feature because the axis is SHARED:
pm-tune joins the tttm check payload with the pm_planning fleet payload, and
the recipe picker (`/tttm/recipes`) must list what the check will find. Three
endpoints that each read the query argument their own way would drift — one
defaulting to a week, another to three — and a picker scoped to a different
window from the payload it drives offers recipes the check then finds nothing
for.

Why WEEKS and why these four: the fleet check is a daily monitor run, so a
week is the smallest span that separates a reproducible tool offset from
day-to-day scatter, and four weeks is where the office cost stops being a lab
page (see ``runs_per_tool`` in each office adapter — the run cap scales with
the window, and every run is one MinIO GET). The user picks; the default is
two — a second week to confirm what the first showed, at half the cost of the
widest choice. "Not enough runs" was the complaint that created the axis
(2026-08-25, when the effective window was ten runs); the user then settled
the default at 2 with 1-4 on offer (2026-08-26).
"""

from __future__ import annotations

from flask import jsonify, request


WINDOW_WEEKS_CHOICES: tuple[int, ...] = (1, 2, 3, 4)
DEFAULT_WINDOW_WEEKS = 2

_ARG = "window_weeks"


def window_days(weeks: int) -> int:
    """The lookback in days for a chosen window."""
    return 7 * weeks


def resolve_window_weeks(arg: str = _ARG) -> int | None:
    """Read ``?window_weeks=`` — absent/blank is the default, anything else
    outside ``WINDOW_WEEKS_CHOICES`` is ``None`` (the route answers 400).

    Refused rather than clamped: a client asking for 8 weeks and getting 3
    would label the screen with a span the server never gathered, and nothing
    about that response looks wrong.
    """
    raw = (request.args.get(arg) or "").strip()
    if not raw:
        return DEFAULT_WINDOW_WEEKS
    try:
        weeks = int(raw)
    except ValueError:
        return None
    return weeks if weeks in WINDOW_WEEKS_CHOICES else None


def bad_window_weeks_response():
    allowed = ", ".join(str(weeks) for weeks in WINDOW_WEEKS_CHOICES)
    return jsonify({"error": f"{_ARG} must be one of {allowed}"}), 400
