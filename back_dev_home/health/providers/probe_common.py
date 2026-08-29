"""The live Redis / OpenSearch / MinIO probes, shared by both health providers.

`mock.py` and `office_example.py` used to carry a copy of these three probes
each, which is how they drifted: the office copy stopped chaining MinIO to the
OpenSearch doc while the home copy kept doing it, and a rule fixed in one was
not fixed in the other. One implementation lives here; each provider keeps
only what actually differs —

* `mock.py`           : the mode gate and the canned home rows.
* `office_example.py` : the standalone self-check and its raw payload dump.

`capture` is that dump. Pass a dict and each probe records what it pulled off
the wire, doing the extra reads that are worth it for a human (Redis SCAN, a
longer MinIO page); pass nothing — the request path — and the probes stay a
plain liveness check. It is a parameter rather than a module-level flag
because the server answers every request on a fresh thread, and a shared
capture dict raced across them.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Any

from back_dev_home._core.timefmt import iso_z
from back_dev_home._runtime.office_redis import load_env_file, redis_client
from back_dev_home.health.contracts import ServiceHealth, ServicesHealthResponse, Status


__all__ = [
    "FRESHNESS_WINDOW",
    "LIST_SAMPLE",
    "OS_INDEX",
    "OS_TIME_FIELD",
    "check_minio",
    "check_opensearch",
    "check_redis",
    "checked_at",
    "elapsed_ms",
    "failure_row",
    "format_age",
    "now",
    "parse_ts",
    "probe_services",
    "row",
]


logger = logging.getLogger("skewnono.health")

FRESHNESS_WINDOW = timedelta(hours=1)
OS_INDEX = "meas_hist_cdsem"
OS_TIME_FIELD = "timestamp"

# Request-path cap on the MinIO listing: a few entries prove reachability and
# authorization, and the listing is lazy, so the rest is latency the health
# card would pay for nothing.
LIST_SAMPLE = 8

# Capture-path cap. Higher because a human is reading the dump and wants to see
# what the prefix actually holds; still bounded, because a prefix can hold
# thousands of objects.
CAPTURE_LIST_LIMIT = 200


def now() -> datetime:
    return datetime.now(timezone.utc)


def checked_at() -> str:
    """UTC stamp at second resolution, `Z`-suffixed like the rest of the API."""
    return iso_z(now())


def parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def format_age(delta: timedelta) -> str:
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h{minutes:02d}m" if minutes else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d{hours:02d}h" if hours else f"{days}d"


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def row(
    service_id: str,
    label: str,
    status: Status,
    latency_ms: int | None,
    detail: str,
) -> ServiceHealth:
    return {
        "id": service_id,
        "label": label,
        "status": status,
        "latency_ms": latency_ms,
        "detail": detail,
    }


def failure_row(
    service_id: str, label: str, started: float, exc: Exception
) -> ServiceHealth:
    """The one probe-failure row: safe client detail, full detail server-side.

    `/api/health/services` is open to every user, and `str(exc)` off a driver
    typically carries internal hostnames and ports. The client gets the
    exception CLASS only; the message and traceback go to the server log.

    The phrase is "probe failed", not "unreachable": this trap also catches
    schema drift and missing libraries, and an ImportError or an AttributeError
    reported as "unreachable" sends an operator to the network when the network
    is fine. The class name carries the specificity.

    `latency_ms` is None because docs/api-contracts/health.yaml defines it as
    "null when status is down (no successful response)" — a timeout's duration
    describes the timeout setting, not the service. The elapsed time still goes
    to the log, where it separates "refused instantly" from "hung to the
    deadline".
    """
    logger.warning(
        "health probe %s failed after %dms: %s: %s",
        service_id,
        elapsed_ms(started),
        type(exc).__name__,
        exc,
        exc_info=exc,
    )
    return row(service_id, label, "down", None, f"probe failed ({type(exc).__name__})")


def check_redis(capture: dict[str, Any] | None = None) -> ServiceHealth:
    started = time.perf_counter()
    try:
        client = redis_client()
        # PING only on the request path. It already proves the connection is
        # open AND authenticated — a wrong REDIS_PASSWORD fails the AUTH that
        # precedes it — so the DBSIZE + SCAN this used to run per request
        # bought nothing but load.
        pong = client.ping()
        latency = elapsed_ms(started)
        if capture is not None:
            capture["redis"] = {"ping": pong, **_redis_sample(client)}
        return row("redis", "Redis", "up", latency, "ping ok")
    except Exception as exc:
        return failure_row("redis", "Redis", started, exc)


def _redis_sample(client) -> dict[str, Any]:
    """Keyspace peek for the standalone dump — never on the request path.

    SCAN (not KEYS) with a small COUNT: one bounded cursor step instead of a
    full keyspace walk that would block the server on a large DB.
    """
    _, sample = client.scan(cursor=0, count=12)
    return {
        "dbsize": client.dbsize(),
        "sample_keys": [
            k.decode("utf-8", "replace") if isinstance(k, bytes) else k
            for k in sample
        ],
    }


def check_opensearch(capture: dict[str, Any] | None = None) -> ServiceHealth:
    started = time.perf_counter()
    try:
        load_env_file("OPENSEARCH_HOST")
        from ops_store import OSSearch

        result = OSSearch(index=OS_INDEX).latest(OS_TIME_FIELD, size=1)
        latency = elapsed_ms(started)

        hits = (result or {}).get("hits", {}).get("hits", [])
        if not hits:
            return row(
                "opensearch", "OpenSearch", "down", latency,
                f"no data in {OS_INDEX}",
            )

        doc = hits[0].get("_source", {}) or {}
        raw_ts = doc.get(OS_TIME_FIELD)
        try:
            parsed_ts = parse_ts(raw_ts)
        except (TypeError, ValueError) as exc:
            # Separated from the outer trap on purpose: the cluster answered,
            # so this is schema drift — a renamed or reformatted time field —
            # and calling it a failed probe would send an operator hunting a
            # network problem that isn't there.
            logger.warning(
                "health probe opensearch: unusable %s %r (%s)",
                OS_TIME_FIELD, raw_ts, exc,
            )
            return row(
                "opensearch", "OpenSearch", "down", latency,
                f"unusable {OS_TIME_FIELD} in latest doc",
            )

        if capture is not None:
            capture["opensearch"] = {
                "index": OS_INDEX,
                "total_hits": (result or {}).get("hits", {}).get("total"),
                # Both forms on purpose: the office stores `timestamp` as a
                # string, so this is where you see whether parse_ts read it
                # correctly (and whether it carried a timezone) before the age
                # math runs on it.
                f"{OS_TIME_FIELD}_raw": raw_ts,
                f"{OS_TIME_FIELD}_parsed": parsed_ts.isoformat(),
                "field_names": sorted(doc.keys()),
                "latest_doc": doc,
            }

        age = now() - parsed_ts
        if age <= FRESHNESS_WINDOW:
            return row(
                "opensearch", "OpenSearch", "up", latency,
                f"latest {format_age(age)} ago · {OS_INDEX}",
            )
        # Stale is "down" on purpose: the cluster answers, but the ingest
        # pipeline behind it has stopped — the user-visible symptom (searches
        # return yesterday's data) is an outage, not a healthy service.
        return row(
            "opensearch", "OpenSearch", "down", latency,
            f"stale: latest {format_age(age)} ago",
        )
    except Exception as exc:
        return failure_row("opensearch", "OpenSearch", started, exc)


def check_minio(capture: dict[str, Any] | None = None) -> ServiceHealth:
    """Connectivity check only: list the bucket/prefix, bounded.

    Deliberately NOT chained to the OpenSearch doc. Statting the object named
    by the latest `minio_path` proves more (the write path works end to end),
    but it leaves MinIO unverifiable whenever OpenSearch is unconfigured or
    down — the row reports "no minio_path" and says nothing about MinIO
    itself. Listing answers the question actually being asked on the landing
    card, "can we reach storage and are we authorized", and it answers it on
    its own.

    Bucket and prefix come from minio_handler/minio_config.py, not from .env.
    """
    started = time.perf_counter()
    try:
        # No load_env_file here: MinIO reads no env at all — endpoint, keys and
        # TLS flags come from minio_handler/minio_config.py.
        from minio_handler import MinioObject

        store = MinioObject()
        bucket = store.default_bucket
        prefix = store.default_prefix or ""

        # list() is lazy — iterating is what performs the request, so the timer
        # must wrap the materialization, not the call.
        limit = CAPTURE_LIST_LIMIT if capture is not None else LIST_SAMPLE
        entries = list(islice(store.list(recursive=False), limit))
        latency = elapsed_ms(started)

        where = f"{bucket}/{prefix}".rstrip("/")
        if capture is not None:
            capture["minio"] = {
                "endpoint": store.config.endpoint if store.config else None,
                "secure": store.config.secure if store.config else None,
                "bucket": bucket,
                "prefix": prefix,
                "folders": [
                    e.object_name for e in entries if e.object_name.endswith("/")
                ],
                "files": [
                    {
                        "name": e.object_name,
                        "size": e.size,
                        # last_modified is None on common prefixes and on some
                        # gateway implementations — surfaced as-is rather than
                        # coerced, so a missing value is visible here.
                        "last_modified": e.last_modified,
                    }
                    for e in entries
                    if not e.object_name.endswith("/")
                ],
            }

        # An empty listing still proves connection + credentials: MinIO
        # answered and authorized the request. Report it as up, but say so, so
        # an unexpectedly empty prefix is visible rather than reassuring.
        if not entries:
            return row(
                "minio", "MinIO", "up", latency, f"connected · {where} is empty"
            )
        return row("minio", "MinIO", "up", latency, f"connected · {where}")
    except Exception as exc:
        return failure_row("minio", "MinIO", started, exc)


def probe_services(capture: dict[str, Any] | None = None) -> ServicesHealthResponse:
    """All three probes, always — never short-circuited, never raising.

    Exactly three rows in the order [redis, opensearch, minio]; each probe
    traps its own exceptions, so even a total outage is three "down" rows
    rather than an exception out of the provider.
    """
    return {
        "checked_at": checked_at(),
        "services": [
            check_redis(capture),
            check_opensearch(capture),
            check_minio(capture),
        ],
    }
