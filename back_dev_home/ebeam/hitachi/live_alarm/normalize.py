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
from datetime import datetime
from typing import Any

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    ALID_KIND,
    FUTURE_TOLERANCE_SEC,
    KST,
)


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


def _int_text(row: Any, *names: str) -> str:
    """Read an integer-valued cell as a bare integer string.

    The feed reaches us through pandas, where one null anywhere in an integer
    column promotes the whole column to float and every value gains a ".0"
    tail. "9006" and "9006.0" are the same alarm id, and "881423" and
    "881423.0" are the same row — but only one spelling of each matches a
    dict lookup or dedupes against yesterday's ZSET member.
    """
    raw = _text(row, *names)
    return raw[:-2] if raw.endswith(".0") else raw


def _alid(row: Any) -> str:
    return _int_text(row, "ALID", "alarm_id", "alid")


def _rawid(row: Any) -> str:
    return _int_text(row, "RAWID", "rawid")


def _parse(text: str) -> datetime | None:
    """Read either timestamp spelling the feed uses, in KST.

    `UTC9` is a datetime64[us] column, so `to_dict` hands us a Timestamp whose
    str() may carry microseconds ("... 09:32:40.123456"); `TIMESTAMP` is a
    plain string in ISO-T form ("2026-03-03T09:32:40"). fromisoformat covers
    both plus the fractional part, which the two strptime formats alone did
    not — a sub-second alarm would have been dropped as undated.

    Anything without an offset is KST: both columns are already 한국 시간, so
    attaching +09:00 relabels rather than shifts. A row that DOES carry an
    offset is trusted as-is instead of being stamped KST twice.
    """
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=KST)


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
        rawid = _rawid(row)
        events.append({
            # RAWID is the feed's own unique key, so it dedupes exactly. The
            # composite is the fallback, and it is strictly weaker: two alarms
            # from one tool in the same second share it and collapse into one
            # row. Prefer the key the source hands us.
            "id": rawid or f"{eqp_id}|{alid}|{occurred_at}",
            "rawid": rawid,
            "eqp_id": eqp_id,
            "alarm_modelname": _text(row, "ALARM_MODELNAME", "alarm_modelname"),
            "alid": alid,
            "al_code": _text(row, "AL_CODE", "al_code"),
            "al_type": _text(row, "AL_TYPE", "al_type"),
            "kind": kind,
            # AL_TEXT is the description the tool emits ("FAILURE IN AUTO
            # MEASUREMENT"). ALARM_NAME is the older POC spelling, kept as a
            # fallback so a feed predating the rename still renders a label.
            "alarm_name": _text(row, "AL_TEXT", "al_text", "ALARM_NAME", "alarm_name"),
            "occurred_at": occurred_at,
            "occurred_epoch": occurred_epoch,
            "lot_id": _text(row, "LOT_ID", "lot_id"),
            "cassette_id": _text(row, "CASSETTE_ID", "cassette_id"),
            # RECIPE_ID and PPID are the same recipe under two systems' names,
            # and the office confirmed they ALWAYS agree (2026-08-03). Both are
            # carried rather than coalesced so this module stays a faithful
            # flattening of the feed — picking one here would make normalize.py
            # the place that decides which spelling is canonical, and the day
            # they diverge that decision would be invisible.
            "recipe_id": _text(row, "RECIPE_ID", "recipe_id"),
            "ppid": _text(row, "PPID", "ppid"),
            "operation_desc": _text(row, "OPERATION_DESC", "operation_desc"),
            "step_id": _text(row, "STEP_ID", "step_id"),
            "lot_type_cd": _text(row, "LOT_TYPE_CD", "lot_type_cd"),
            "meseventname": _text(row, "MESEVENTNAME", "meseventname"),
            "eq_stat": _text(row, "EQ_STAT", "eq_stat"),
        })
    return events


def canonical_json(event: dict) -> str:
    """Stable serialization — ZSET dedupe compares member strings exactly."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
