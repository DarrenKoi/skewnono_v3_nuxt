"""[Office template] live_alarm writer I/O. Copy to office.py to activate.

    cp office_example.py office.py

This is the only file that knows the in-house alarm API addresses, which
is why office.py is gitignored. It is also deliberately free of any
import from the main SKEWNONO backend package: the writer directory is
copied wholesale onto a scheduler service that does not have that
package on its path.

The fab list IS the address map's key set. Adding a fab and registering
its address are the same edit, so the two cannot drift apart.
"""

from __future__ import annotations

import os

import redis
import requests


# (tool_slug, fab_name) -> in-house alarm API base URL. Fill in at the office.
ALARM_API: dict[tuple[str, str], str] = {
    ("cd-sem", "R3"): "http://alarm-r3.example.internal/api/alarms",
    # ("cd-sem", "M11"): "...",
    # ("cd-sem", "M12"): "...",
    # ("cd-sem", "M14"): "...",
    # ("cd-sem", "M15"): "...",
    # ("cd-sem", "M16A"): "...",
}


def _timeout() -> tuple[float, float]:
    connect, _, read = os.environ.get("LIVE_ALARM_HTTP_TIMEOUT", "3,7").partition(",")
    return float(connect), float(read or 7)


def configured_fabs() -> list[tuple[str, str]]:
    return list(ALARM_API.keys())


def redis_client():
    """The Redis SKEWNONO's office adapters read.

    NOTE: db is left at redis-py's default of 0 on purpose. The reader's
    Redis helper passes no db either, so it sits on db 0. Changing one
    side without the other silently splits the writer and reader onto
    different databases.
    """
    return redis.Redis(
        host=os.environ["LIVE_ALARM_REDIS_HOST"],
        port=int(os.environ.get("LIVE_ALARM_REDIS_PORT", "6379")),
        password=os.environ.get("LIVE_ALARM_REDIS_PASSWORD") or None,
        db=int(os.environ.get("LIVE_ALARM_REDIS_DB", "0")),
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=10,
    )


def fetch_alarms(tool_slug: str, fab_name: str, window_sec: int) -> list[dict]:
    """Query one fab's alarm feed for the last `window_sec` seconds.

    Raise on any failure — run_once relies on the exception to decide NOT
    to stamp the heartbeat. Returning [] on error would report a healthy
    feed with no data, which is the exact failure this design prevents.

    `window_sec` is not always 60: after an outage the caller widens it so
    the gap gets backfilled. Honour whatever it passes.
    """
    url = ALARM_API[(tool_slug, fab_name)]
    response = requests.get(
        url,
        params={"range_sec": window_sec},   # adjust to the real API's contract
        timeout=_timeout(),
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else payload.get("rows", [])
