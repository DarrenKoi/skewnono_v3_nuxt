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
- MinIO      : `MINIO_*` (read by `minio_handler`), stats the object named by
               that newest doc's `minio_path` ("bucket/key"), "up" when its
               `last_modified` is < 1h old

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
    _parse_minio_path,
    _parse_ts,
)


__all__ = ["get_services_health"]


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
        client.ping()
        latency = _elapsed_ms(started)
        # DBSIZE is O(1) and confirms the connection is authenticated, not just
        # open — a wrong REDIS_PASSWORD fails here rather than looking healthy.
        keys = client.dbsize()
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
        age = _now() - _parse_ts(doc[OS_TIME_FIELD])
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


def _check_minio(latest_doc: dict[str, Any] | None) -> ServiceHealth:
    started = time.perf_counter()
    try:
        path = (latest_doc or {}).get("minio_path") if latest_doc else None
        if not path:
            return {
                "id": "minio", "label": "MinIO", "status": "down",
                "latency_ms": None, "detail": "no minio_path in latest os doc",
            }

        bucket, key = _parse_minio_path(str(path))

        load_env_file("MINIO_ENDPOINT")
        from minio.error import S3Error
        from minio_handler import MinioObject

        store = MinioObject(bucket=bucket)
        started = time.perf_counter()
        try:
            stat = store.stat(key)
        except S3Error as err:
            # Distinguished from a generic failure: reaching MinIO and being
            # told the object is absent means the storage layer is up but the
            # write path (or the path convention) is broken.
            return {
                "id": "minio", "label": "MinIO", "status": "down",
                "latency_ms": _elapsed_ms(started),
                "detail": f"missing: {bucket}/{key} ({err.code})",
            }
        latency = _elapsed_ms(started)

        age = _now() - _parse_ts(stat.last_modified)
        if age <= FRESHNESS_WINDOW:
            return {
                "id": "minio", "label": "MinIO", "status": "up",
                "latency_ms": latency,
                "detail": f"latest object {_format_age(age)} ago · {bucket}",
            }
        return {
            "id": "minio", "label": "MinIO", "status": "down",
            "latency_ms": latency,
            "detail": f"stale: object {_format_age(age)} ago",
        }
    except Exception as exc:
        return {
            "id": "minio", "label": "MinIO", "status": "down",
            "latency_ms": _elapsed_ms(started), "detail": _reason(exc),
        }


def get_services_health() -> ServicesHealthResponse:
    redis_h = _check_redis()
    os_h, latest_doc = _check_opensearch_latest()
    minio_h = _check_minio(latest_doc)
    return {
        "checked_at": _now().isoformat(timespec="seconds"),
        "services": [redis_h, os_h, minio_h],
    }
