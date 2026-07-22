"""Pure board logic shared by every live_alarm provider.

Every function takes `now` as an argument. Nothing here reads a clock, so
boundary behaviour is testable without sleeping or freezing time.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    STALE_AFTER_SEC,
    AlarmEvent,
    FeedStatus,
)


log = logging.getLogger(__name__)

__all__ = ["feed_status_for", "dedupe_by_id", "parse_members"]


def feed_status_for(meta: dict[str, Any] | None, known: bool, *, now: int) -> FeedStatus:
    """Which of the three empty states is this?

    "No alarms" is ambiguous on its own: a healthy quiet fab, a dead feed,
    and an unconfigured fab all render as an empty list. `known` (is this
    fab in the writer's registry?) separates the third; the heartbeat age
    separates the first two.
    """
    if not known:
        return "not_configured"
    if not meta or "polled_at" not in meta:
        return "stale"
    return "live" if now - int(meta["polled_at"]) <= STALE_AFTER_SEC else "stale"


def dedupe_by_id(events: Iterable[AlarmEvent]) -> list[AlarmEvent]:
    """One row per id, chosen deterministically.

    ZSET members are canonical JSON, so the same alarm reported with a
    different decorative field (alarm_name, operation_desc) lands as a
    second member under the same id. Sorting by the serialized member
    before picking makes every reader process render the same screen.
    """
    best: dict[str, tuple[str, AlarmEvent]] = {}
    for event in events:
        key = str(event.get("id", ""))
        marker = json.dumps(event, sort_keys=True, separators=(",", ":"))
        current = best.get(key)
        if current is None or marker < current[0]:
            best[key] = (marker, event)
    return [event for _, event in best.values()]


def parse_members(raw: Iterable[bytes]) -> list[AlarmEvent]:
    """Decode ZSET members, skipping anything unreadable.

    The writer is deployed separately, so a partial rollout can leave a
    member this build cannot parse. Dropping that one member beats 500ing
    the endpoint — same leniency `flask_modules`' read_task_logs applies
    to malformed log entries.
    """
    out: list[AlarmEvent] = []
    for member in raw:
        try:
            text = member.decode("utf-8") if isinstance(member, bytes) else member
            out.append(json.loads(text))
        except (UnicodeDecodeError, ValueError, TypeError):
            log.warning("dropping unparseable live_alarm member: %r", member[:120])
    return out
