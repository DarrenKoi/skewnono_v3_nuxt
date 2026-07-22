"""In-house alarm rows -> AlarmEvent, plus the canonical ZSET member form.

Standalone by design (see window.py). The AlarmEvent shape here must stay
in step with back_dev_home/.../live_alarm/contracts.py; the contract test
in test_writer_job.py is what enforces that.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any


KST = timezone(timedelta(hours=9))
ALID_KIND = {"9006": "align", "9100": "meas"}
FUTURE_TOLERANCE_SEC = 300

__all__ = ["to_events", "canonical_json", "ALID_KIND"]


def _text(row: Any, *names: str) -> str:
    for name in names:
        if isinstance(row, dict) and name in row and row[name] is not None:
            return str(row[name]).strip()
    return ""


def _alid(row: Any) -> str:
    """Normalize the alarm id to a bare integer string.

    The in-house feed reaches us through pandas in places, which turns an
    integer column into "9006.0". Both spellings mean the same alarm.
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
            # An upstream clock running fast would park this above the
            # pruning boundary, where it would never age off the board.
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
