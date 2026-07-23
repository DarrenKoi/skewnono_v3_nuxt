"""Row-value logic shared by the bm_pm mock and office adapters.

The dispatcher (`providers/office_example.py`) swaps `mock.py` and `office.py`
by module name, so both must produce rows with the same keys, the same
timestamp format, and the same BM/PM classification. That logic lives here,
imported by both, instead of being written twice and drifting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


__all__ = [
    "TS_FMT",
    "classify_category",
    "derive_cards",
    "fmt_dt",
    "merge_notes",
]


# Load-bearing: front-dev-home/app/utils/bmPmMarkers.ts matches `job_starts`
# against the trend charts' own x-axis values. A different format does not
# fail — it draws the overlay markers nowhere.
TS_FMT = "%Y-%m-%d %H:%M"

# Column labels for the three free-form note fields, in display order.
_NOTE_LABELS: tuple[tuple[str, str], ...] = (
    ("note_comment", "Comment"),
    ("zzproblem", "Problem"),
    ("hltext", "Highlight"),
)


def fmt_dt(value: datetime | None) -> str:
    return value.strftime(TS_FMT) if value is not None else ""


def classify_category(*candidates: str) -> str:
    """Reduce raw maintenance-type text to the "BM"/"PM" the UI needs.

    Office `pm_type`/`eq_event` values carry characters around the BM/PM part,
    so this matches on containment rather than equality. Candidates are walked
    in priority order and an unrecognisable one does NOT stop the walk: a
    `pm_type` of "기타" beside an `eq_event` of "PM_WEEKLY" is a PM record.

    An unclassifiable row yields "" and still renders — its raw `pm_type` and
    `eq_event` columns stay visible. It only drops out of the chart overlay,
    which already skips anything that is not exactly "BM" or "PM".

    "PM" is tested first because a value carrying both is far more likely a PM
    record qualified by other text than the reverse.
    """
    for candidate in candidates:
        text = (candidate or "").strip().upper()
        if "PM" in text:
            return "PM"
        if "BM" in text:
            return "BM"
    return ""


def merge_notes(row: dict[str, Any]) -> str:
    """The three note fields as one labelled block, for the overlay tooltip.

    Carried on the row but never declared as a column: `BmPmTables.vue`
    renders only declared columns, while `bmPmMarkers.ts` reads
    `row.engr_note` directly. Blank notes are dropped so a tooltip never shows
    a bare label.
    """
    parts = []
    for key, label in _NOTE_LABELS:
        text = str(row.get(key) or "").strip()
        if text:
            parts.append(f"[{label}] {text}")
    return "\n".join(parts)


def derive_cards(
    past: list[dict[str, Any]], future: list[dict[str, Any]]
) -> dict[str, Any]:
    """Summary-card values read off the finished rows.

    Relies on the row order both providers promise — `past` newest-first,
    `future` soonest-first — so the first matching row on each side is the one
    the card wants.
    """
    last_bm = "—"
    for row in past:
        if row.get("category") == "BM":
            # A tool that is still down has no job_end; show when it went down
            # rather than a blank card.
            last_bm = str(row.get("job_end") or row.get("job_starts") or "—")
            break

    next_pm = "—"
    for row in future:
        if row.get("category") == "PM":
            next_pm = str(row.get("job_starts") or "—")
            break

    return {
        "last_bm": last_bm,
        "next_pm": next_pm,
        "planned_count": len(future),
        "recent_count": len(past),
    }
