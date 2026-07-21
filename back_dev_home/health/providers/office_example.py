# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for health — live Redis / OpenSearch / MinIO probes.

Difference from `providers/mock.py`: **no fallback**. mock.py runs the same
three probes but swallows every exception into a canned `"mock · "` row so the
home environment (where none of the three servers exist) still renders a card.
At the office those servers DO exist, so a swallowed exception would be a lie —
a real outage or a wrong `MINIO_*` credential would show up as a green
"mock · 12 buckets" instead of red. Here every failure surfaces as
`status: "down"` with the exception on the `detail` line.

Config (all from `back_dev_home/.env`, loaded by the app factory; the helpers
below self-load it for standalone runs):

- Redis      : `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD`
               — via the shared fail-fast client in `_runtime/office_redis.py`
- OpenSearch : `OPENSEARCH_*` (read by `ops_store`), index `meas_hist_cdsem`,
               "up" when the newest doc's `timestamp` is < 1h old
- MinIO      : `minio_handler/minio_config.py` (gitignored — NOT .env; env
               vars would override that file), lists the folders under the
               configured bucket/prefix — a plain connectivity + auth check,
               independent of the other two

Self-check at the office, from the repo root:

    python -m back_dev_home.health.providers.office

Prints one line per service and exits 1 if any is down.

Contract invariant preserved from mock: `get_services_health()` never raises
and always returns exactly three rows in the order [redis, opensearch, minio].
Each probe traps its own exceptions, so flipping health to office can never
500 the endpoint or break app startup.

The pure helpers (timestamp parsing, age formatting, `minio_path` splitting,
the freshness window) are imported from mock.py rather than copied — they hold
no home-specific behavior, and one copy means office and home can't drift on
what "stale" means.
"""

from __future__ import annotations

import json
import time
from typing import Any

from back_dev_home._runtime.office_redis import load_env_file, redis_client
from back_dev_home.health.contracts import ServiceHealth, ServicesHealthResponse
from back_dev_home.health.providers.mock import (
    FRESHNESS_WINDOW,
    OS_INDEX,
    OS_TIME_FIELD,
    _elapsed_ms,
    _format_age,
    _now,
    _parse_ts,
)


__all__ = ["get_services_health"]


# Raw payload each probe pulled off its server, keyed by service id. Written on
# every run but read ONLY by _main() — the HTTP response is `ServiceHealth`, a
# summary, which is deliberately too small to tell you whether a field name or
# a timestamp parsed the way you expected. Running this file directly dumps
# what came back verbatim so schema drift (a renamed column, a str where a
# datetime was assumed) is visible instead of hiding behind "up".
_RAW: dict[str, Any] = {}

# Cap per dumped section: a meas_hist doc can carry dozens of fields and a
# prefix can hold hundreds of folders. Enough to verify parsing, short enough
# to read in a terminal.
_DUMP_CHAR_LIMIT = 4000


def _reason(exc: Exception) -> str:
    """One-line, bounded failure text for the `detail` field.

    Kept short and single-line: `detail` renders inside a narrow card row, and
    an OpenSearch/MinIO traceback string can run to hundreds of characters.
    """
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    label = f"{type(exc).__name__}: {text}" if text else type(exc).__name__
    return label[:160]


def _check_redis() -> ServiceHealth:
    started = time.perf_counter()
    try:
        client = redis_client()
        pong = client.ping()
        latency = _elapsed_ms(started)
        # DBSIZE is O(1) and confirms the connection is authenticated, not just
        # open — a wrong REDIS_PASSWORD fails here rather than looking healthy.
        keys = client.dbsize()
        # SCAN (not KEYS) with a small COUNT: one bounded cursor step instead of
        # a full keyspace walk that would block the server on a large DB.
        _, sample = client.scan(cursor=0, count=12)
        _RAW["redis"] = {
            "ping": pong,
            "dbsize": keys,
            "sample_keys": [
                k.decode("utf-8", "replace") if isinstance(k, bytes) else k
                for k in sample
            ],
        }
        return {
            "id": "redis", "label": "Redis", "status": "up",
            "latency_ms": latency, "detail": f"ping ok · {keys} keys",
        }
    except Exception as exc:
        return {
            "id": "redis", "label": "Redis", "status": "down",
            "latency_ms": _elapsed_ms(started), "detail": _reason(exc),
        }


def _check_opensearch_latest() -> tuple[ServiceHealth, dict[str, Any] | None]:
    """Probe OpenSearch and hand the newest doc to the MinIO check.

    The doc is the MinIO probe's input (it carries `minio_path`), so the two
    checks are chained rather than independent — when OpenSearch is down there
    is no object to stat, and MinIO reports that explicitly.
    """
    started = time.perf_counter()
    try:
        load_env_file("OPENSEARCH_HOST")
        from ops_store import OSSearch

        result = OSSearch(index=OS_INDEX).latest(OS_TIME_FIELD, size=1)
        latency = _elapsed_ms(started)

        hits = (result or {}).get("hits", {}).get("hits", []) if result else []
        if not hits:
            return ({
                "id": "opensearch", "label": "OpenSearch", "status": "down",
                "latency_ms": latency, "detail": f"no data in {OS_INDEX}",
            }, None)

        doc = hits[0].get("_source", {}) or {}
        raw_ts = doc.get(OS_TIME_FIELD)
        parsed_ts = _parse_ts(raw_ts)
        _RAW["opensearch"] = {
            "index": OS_INDEX,
            "total_hits": (result or {}).get("hits", {}).get("total"),
            # Both forms on purpose: the office stores `timestamp` as a string,
            # so this is where you see whether _parse_ts read it correctly (and
            # whether it carried a timezone) before the age math runs on it.
            f"{OS_TIME_FIELD}_raw": raw_ts,
            f"{OS_TIME_FIELD}_parsed": parsed_ts.isoformat(),
            "field_names": sorted(doc.keys()),
            "latest_doc": doc,
        }
        age = _now() - parsed_ts
        if age <= FRESHNESS_WINDOW:
            return ({
                "id": "opensearch", "label": "OpenSearch", "status": "up",
                "latency_ms": latency,
                "detail": f"latest {_format_age(age)} ago · {OS_INDEX}",
            }, doc)
        # Stale is "down" on purpose: the cluster answers, but the ingest
        # pipeline behind it has stopped — the user-visible symptom (searches
        # return yesterday's data) is an outage, not a healthy service.
        return ({
            "id": "opensearch", "label": "OpenSearch", "status": "down",
            "latency_ms": latency,
            "detail": f"stale: latest {_format_age(age)} ago",
        }, doc)
    except Exception as exc:
        return ({
            "id": "opensearch", "label": "OpenSearch", "status": "down",
            "latency_ms": _elapsed_ms(started), "detail": _reason(exc),
        }, None)


def _check_minio() -> ServiceHealth:
    """Connectivity check only: list the folders under bucket/prefix.

    Deliberately NOT chained to the OpenSearch doc. Statting the object named
    by the latest `minio_path` proves more (the write path works end to end),
    but it makes MinIO unverifiable whenever OpenSearch is unconfigured or
    down — the row reports "no minio_path" and says nothing about MinIO
    itself. Listing answers the question actually being asked on the landing
    card, "can we reach storage and are we authenticated", and it answers it
    on its own.

    Bucket and prefix come from minio_handler/minio_config.py ("user" /
    "2067928/"); the listing is non-recursive, so it reads one page of common
    prefixes no matter how many objects sit underneath.
    """
    started = time.perf_counter()
    try:
        # No load_env_file here: MinIO reads no env at all — endpoint, keys and
        # TLS flags come from minio_handler/minio_config.py.
        from minio_handler import MinioObject

        store = MinioObject()
        bucket = store.default_bucket
        prefix = store.default_prefix or ""

        # list_objects is lazy — iterating is what performs the request, so the
        # timer must wrap the materialization, not the call.
        entries = list(store.list(recursive=False))
        latency = _elapsed_ms(started)

        folders = [e.object_name for e in entries if e.object_name.endswith("/")]
        files = len(entries) - len(folders)
        where = f"{bucket}/{prefix}".rstrip("/")

        _RAW["minio"] = {
            "endpoint": store.config.endpoint if store.config else None,
            "secure": store.config.secure if store.config else None,
            "bucket": bucket,
            "prefix": prefix,
            "folders": folders,
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
            return {
                "id": "minio", "label": "MinIO", "status": "up",
                "latency_ms": latency, "detail": f"connected · {where} is empty",
            }

        summary = f"{len(folders)} folders"
        if files:
            summary += f" · {files} files"
        return {
            "id": "minio", "label": "MinIO", "status": "up",
            "latency_ms": latency, "detail": f"{summary} · {where}",
        }
    except Exception as exc:
        return {
            "id": "minio", "label": "MinIO", "status": "down",
            "latency_ms": _elapsed_ms(started), "detail": _reason(exc),
        }


def get_services_health() -> ServicesHealthResponse:
    redis_h = _check_redis()
    os_h, _latest_doc = _check_opensearch_latest()
    minio_h = _check_minio()
    return {
        "checked_at": _now().isoformat(timespec="seconds"),
        "services": [redis_h, os_h, minio_h],
    }


def _dump(label: str, payload: Any) -> None:
    """Print a raw payload as readable JSON.

    `default=str` because these payloads carry datetimes and bytes straight
    off the wire — a TypeError from the serializer would hide the very data
    the dump exists to show. ensure_ascii=False keeps Korean field values
    legible instead of \\uXXXX escapes.
    """
    print(f"\n── {label} ─────────────────────────────────")
    if not payload:
        print("  (nothing extracted — the probe failed before reading data)")
        return
    text = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    if len(text) > _DUMP_CHAR_LIMIT:
        text = text[:_DUMP_CHAR_LIMIT] + f"\n  … truncated at {_DUMP_CHAR_LIMIT} chars"
    print(text)


def _main() -> int:
    """Standalone probe: `python -m back_dev_home.health.providers.office`.

    Run from the repo root at the office to check this adapter end to end
    without Flask, Nuxt or the provider switch in the way. Prints the summary
    each service would return over HTTP, then dumps the raw payload pulled
    from each server so you can confirm the parsing — field names, timestamp
    formats, object keys — rather than trusting a green "up". Exits 1 if any
    service is down, so it doubles as a shell check.
    """
    load_env_file("REDIS_HOST")

    result = get_services_health()
    print(f"checked_at: {result['checked_at']}")
    for svc in result["services"]:
        mark = "OK  " if svc["status"] == "up" else "DOWN"
        latency = "—" if svc["latency_ms"] is None else f"{svc['latency_ms']}ms"
        print(f"  [{mark}] {svc['label']:<11} {latency:>8}  {svc['detail']}")

    print("\n=== RAW DATA AS EXTRACTED ===")
    for svc in result["services"]:
        _dump(svc["label"], _RAW.get(svc["id"]))

    down = [s["label"] for s in result["services"] if s["status"] == "down"]
    if down:
        print(f"\n{len(down)} down: {', '.join(down)}")
        return 1
    print("\nall services up")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
