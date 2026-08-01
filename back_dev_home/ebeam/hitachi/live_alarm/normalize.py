"""Office alarm rows -> AlarmEvent, plus the canonical ZSET member form.

Moved out of writer/ when the scheduled writer was replaced by the on-demand
refresh. It no longer duplicates ALID_KIND and FUTURE_TOLERANCE_SEC: that
duplication existed only because the writer was copied onto a service without
back_dev_home on its path.

Deliberately free of pandas. refresh.py converts the office DataFrame to dict
rows before calling in, so this module stays testable with plain literals.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    ALID_KIND,
    FUTURE_TOLERANCE_SEC,
)


KST = timezone(timedelta(hours=9))

__all__ = ["to_events", "canonical_json"]

# What DataFrame.to_dict leaves behind in an empty optional cell. str() turns
# each of these into text that would render literally on the board. Kept in
# step with `_office_search._MISSING_TEXT`, which answers the same question
# for OpenSearch cells — the two drifting would mean two answers for one cell.
# Not imported from there: that module pulls pandas, opensearchpy and
# ops_store at import time, and this one is deliberately dependency-free.
_NULLISH = {"nan", "nat", "none", "null", "<na>"}


def _text(row: Any, *names: str) -> str:
    if not isinstance(row, dict):
        return ""
    for name in names:
        if name not in row:
            continue
        value = row[name]
        if value is None:
            continue
        if isinstance(value, float) and value != value:  # NaN != itself
            continue
        text = str(value).strip()
        if not text or text.lower() in _NULLISH:
            continue
        return text
    return ""


def _alid(row: Any) -> str:
    """Normalize the alarm id to a bare integer string.

    The feed reaches us through pandas, which turns an integer column into
    "9006.0". Both spellings mean the same alarm.
    """
    raw = _text(row, "ALID", "alarm_id", "alid")
    return raw[:-2] if raw.endswith(".0") else raw


def _parse(text: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    return None


def to_events(rows: list[dict], *, now: int) -> list[dict]:
    """Convert raw feed rows into AlarmEvents, discarding what we cannot use."""
    events: list[dict] = []
    for row in rows:
        alid = _alid(row)
        kind = ALID_KIND.get(alid)
        if kind is None:
            continue

        moment = _parse(_text(row, "UTC9", "TIMESTAMP", "timestamp"))
        if moment is None:
            continue

        occurred_epoch = int(moment.timestamp())
        if occurred_epoch > now + FUTURE_TOLERANCE_SEC:
            # An upstream clock running fast would park this above the prune
            # boundary, where it would never age off the board.
            continue

        occurred_at = moment.isoformat(sep=" ")
        eqp_id = _text(row, "EQP_ID", "eqp_id")
        events.append({
            "id": f"{eqp_id}|{alid}|{occurred_at}",
            "eqp_id": eqp_id,
            "alid": alid,
            "kind": kind,
            "alarm_name": _text(row, "ALARM_NAME", "alarm_name"),
            "occurred_at": occurred_at,
            "occurred_epoch": occurred_epoch,
            "recipe_id": _text(row, "RECIPE_ID", "recipe_id"),
            "operation_desc": _text(row, "OPERATION_DESC", "operation_desc"),
            "lot_type_cd": _text(row, "LOT_TYPE_CD", "lot_type_cd"),
        })
    return events


def canonical_json(event: dict) -> str:
    """Stable serialization — ZSET dedupe compares member strings exactly."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
