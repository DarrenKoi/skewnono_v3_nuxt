"""Pure board logic shared by every live_alarm provider.

Every function takes `now` as an argument. Nothing here reads a clock, so
boundary behaviour is testable without sleeping or freezing time.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Iterable

from back_dev_home.ebeam._tool_specs import ToolType
from back_dev_home.ebeam.live_alarm.contracts import (
    BOARD_WINDOW_SEC,
    KST,
    STALE_AFTER_SEC,
    AlarmEvent,
    FeedStatus,
    LiveAlarmPayload,
)


log = logging.getLogger(__name__)

__all__ = [
    "feed_status_for",
    "dedupe_by_id",
    "parse_members",
    "iso",
    "payload",
    "merged_meta",
]


def iso(epoch: int | None) -> str | None:
    """Epoch -> "YYYY-MM-DD HH:MM:SS+09:00", the contract's timestamp form."""
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), KST).isoformat(sep=" ")


def feed_status_for(meta: dict[str, Any] | None, known: bool, *, now: int) -> FeedStatus:
    """Which of the three empty states is this?

    "No alarms" is ambiguous on its own: a healthy quiet fab, a dead feed,
    and a fab with no tools all render as an empty list. `known` (does the
    sem_list roster hold any tool of this type in this fab?) separates the
    third; the age of the last SUCCESSFUL fetch separates the first two.

    `fetched_at` is stamped only after the office call returns, so a failing
    feed ages into "stale" instead of reporting a fresh heartbeat over data
    that was never refreshed.
    """
    if not known:
        return "not_configured"
    if not meta or "fetched_at" not in meta:
        return "stale"
    return "live" if now - int(meta["fetched_at"]) <= STALE_AFTER_SEC else "stale"


def payload(
    *,
    tool_type: ToolType,
    fab_names: Sequence[str],
    now: int,
    configured: bool,
    meta: dict[str, Any] | None = None,
    unmatched_count: int = 0,
    not_configured_fabs: Sequence[str] = (),
    events: Iterable[AlarmEvent] = (),
) -> LiveAlarmPayload:
    """The one LiveAlarmPayload constructor both providers use.

    Written once rather than per provider because a payload literal per
    provider per empty-state is four copies of the same nine keys — and the
    field this feature most needs to be right (`fetched_at`, which must be
    absent unless a fetch actually succeeded) would be the one most likely to
    drift between them. Adding a field is now one edit, not four.

    `configured` now means "at least one requested fab is configured" — a
    multi-fab request with a partial roster miss still renders a board for
    the fabs that ARE configured, and names the rest in `not_configured_fabs`.
    """
    return {
        "fab_names": list(fab_names),
        "tool_type": tool_type,
        "feed_status": feed_status_for(meta, configured, now=now),
        "fetched_at": iso(meta["fetched_at"]) if meta else None,
        # Only meaningful for a fab that has a board: an unconfigured fab
        # covers nothing, so claiming a window would imply a feed exists.
        "covered_since": iso(now - BOARD_WINDOW_SEC) if configured else None,
        "server_now": iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        "unmatched_count": unmatched_count,
        "not_configured_fabs": list(not_configured_fabs),
        "events": list(events),
    }


def merged_meta(metas: Sequence[dict[str, Any] | None]) -> dict[str, Any] | None:
    """Worst-of merge across facilities: None if ANY fac has never fetched
    (feed_status_for then says stale), else the OLDEST fetched_at — so one
    stale fac makes the merged board stale rather than hiding behind a
    fresher sibling."""
    if not metas or any(m is None or "fetched_at" not in m for m in metas):
        return None
    return {"fetched_at": min(int(m["fetched_at"]) for m in metas)}


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
    """Decode ZSET members, skipping anything unreadable OR wrong-shaped.

    Members outlive the build that wrote them — they sit in Redis for up to
    KEY_TTL_SEC, so a rolling restart or a schema change can leave a member this
    build cannot parse. Dropping that one member beats 500ing the endpoint —
    same leniency `flask_modules`' read_task_logs applies to malformed log
    entries.

    Valid JSON is not enough: a member that decodes to a list, or to a dict
    missing ``id``/``occurred_epoch``, would later raise in dedupe_by_id
    (``.get`` on a list) or in the reader's sort (``e["occurred_epoch"]``).
    Requiring those two keys here keeps the 500 from ever reaching the
    endpoint; other absent fields degrade to blanks in the UI, not a crash.
    """
    out: list[AlarmEvent] = []
    for member in raw:
        try:
            text = member.decode("utf-8") if isinstance(member, bytes) else member
            event = json.loads(text)
        except (UnicodeDecodeError, ValueError, TypeError):
            log.warning("dropping unparseable live_alarm member: %r", member[:120])
            continue
        if not isinstance(event, dict) or "id" not in event or "occurred_epoch" not in event:
            log.warning("dropping wrong-shaped live_alarm member: %r", str(event)[:120])
            continue
        out.append(event)
    return out
