"""[Office template] live_alarm reader. Copy to office.py to activate.

    cp office_example.py office.py

Reads only. Everything on the board was put there by the writer job (see
writer/office_example.py), so this file never touches the in-house alarm
API and never writes to Redis.

Key layout comes from writer.job (keys(), REGISTRY_KEY) so the reader and
writer cannot drift on key names. Only the WRITER must stay free of
back_dev_home imports (it is copied to another service); the reader runs
inside SKEWNONO, where importing the writer package is fine.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from back_dev_home._runtime.office_redis import redis_client
from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.hitachi.live_alarm import board
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    BOARD_WINDOW_SEC,
    FUTURE_TOLERANCE_SEC,
    LiveAlarmPayload,
)
from back_dev_home.ebeam.hitachi.live_alarm.writer.job import REGISTRY_KEY, keys


KST = timezone(timedelta(hours=9))

# The writer keys its entries by the tool_slug in its ALARM_API map, which
# uses the "cd-sem"/"hv-sem" spelling — so the reader passes the tool_type
# value straight through. The two spellings MUST match for the lookup to hit.
_TOOL_SLUG: dict[str, str] = {"cd-sem": "cd-sem", "hv-sem": "hv-sem"}


def _iso(epoch: int | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), KST).isoformat(sep=" ")


def _decode(raw) -> dict | None:
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(text)
    except (UnicodeDecodeError, ValueError, TypeError):
        return None


def get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload:
    client = redis_client()
    tool_slug = _TOOL_SLUG[tool_type]
    events_key, meta_key = keys(tool_slug, fab_name)

    # Redis is the single clock authority — the writer prunes against this
    # same clock, so the two never disagree about the boundary.
    now = int(client.time()[0])

    raw_members = client.zrangebyscore(
        events_key,
        now - BOARD_WINDOW_SEC,
        # Not "+inf": a fast upstream clock would otherwise pin a far-future
        # event to the top of the board forever.
        now + FUTURE_TOLERANCE_SEC,
    )
    meta = _decode(client.get(meta_key))
    known = bool(client.sismember(REGISTRY_KEY, f"{tool_slug}:{fab_name}"))

    events = board.dedupe_by_id(board.parse_members(raw_members))
    events.sort(key=lambda e: e["occurred_epoch"], reverse=True)

    return {
        "fab_name": fab_name,
        "tool_type": tool_type,
        "feed_status": board.feed_status_for(meta, known, now=now),
        "polled_at": _iso(meta.get("polled_at")) if meta else None,
        "covered_since": _iso(meta.get("covered_since")) if meta else None,
        "server_now": _iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        "events": events,
    }
