"""Network-free /admin/logs rows for home and automated tests.

Stands in for a query against the ``skewnono_logging_local`` alias. The rows
carry the same document shape ``_logging/opensearch_handler._record_to_doc``
writes, because ``item_from_hit`` copies the whole ``_source`` into
``LogItem["raw"]`` — a field missing here is a field the raw panel never shows
at home but always shows at the office.

Deliberate differences from real data: ``event_id`` and ``request_id`` are
readable ``demo-*`` strings rather than UUIDs, timestamps are relative to now
so the default time window always has hits, and one row carries the legacy
``request_path`` field to exercise ``item_from_hit``'s fallback for documents
written before ``c11fbc2``. See ``docs/datatables/skewnono_logging.txt``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home.admin_logs.contracts import LogQueryResponse
from back_dev_home.admin_logs.query import (
    _iso_z,
    _split_csv,
    _utc_now,
    item_from_hit,
    page_count_for,
    parse_log_query,
)


def _demo_source(now: datetime) -> list[dict[str, Any]]:
    rows = [
        {
            "@timestamp": _iso_z(now - timedelta(minutes=4)),
            "level": "ERROR",
            "logger": "skewnono.activity",
            "message": "request exception user=kim.minju method=GET path=/api/ebeam/cdsem/storage ms=842 remote=10.20.30.11 error=TimeoutError",
            "host": "local-demo",
            "event": "request_exception",
            "user_id": "kim.minju",
            "method": "GET",
            "path": "/api/ebeam/cdsem/storage",
            "request_path": "/api/ebeam/cdsem/storage",
            "query_string": "fab=M14",
            "status": 500,
            "latency_ms": 842,
            "remote_addr": "10.20.30.11",
            "feature": "ebeam",
            "activity_kind": "operation",
            "activity_weight": 0,
            "fab_name_list": ["M14"],
            "error_code": "TimeoutError",
            "error_name": "OpenSearch request timed out",
            "exception": {
                "type": "TimeoutError",
                "message": "OpenSearch request timed out",
                "stack": "Traceback (most recent call last):\n  File \"back_dev_home/ebeam/.../routes.py\", line 42, in storage\nTimeoutError: OpenSearch request timed out",
            },
        },
        {
            "@timestamp": _iso_z(now - timedelta(minutes=9)),
            "level": "WARNING",
            "logger": "skewnono.activity",
            "message": "user=park.jinho method=GET path=/api/afm/recipes/missing status=404 ms=38 remote=10.20.30.12",
            "host": "local-demo",
            "event": "request",
            "user_id": "park.jinho",
            "method": "GET",
            "path": "/api/afm/recipes/missing",
            "request_path": "/api/afm/recipes/missing",
            "query_string": "",
            "status": 404,
            "latency_ms": 38,
            "remote_addr": "10.20.30.12",
            "feature": "afm",
            "activity_kind": "operation",
            "activity_weight": 0,
            "fab_name_list": [],
            "error_code": "404",
            "error_name": "Not Found",
        },
        {
            "@timestamp": _iso_z(now - timedelta(minutes=16)),
            "level": "INFO",
            "logger": "skewnono.activity",
            "message": "user=lee.soyoung method=GET path=/api/activity/leaderboard status=200 ms=14 remote=10.20.30.13",
            "host": "local-demo",
            "event": "request",
            "user_id": "lee.soyoung",
            "method": "GET",
            "path": "/api/activity/leaderboard",
            "request_path": "/api/activity/leaderboard",
            "query_string": "top=10",
            "status": 200,
            "latency_ms": 14,
            "remote_addr": "10.20.30.13",
            "feature": "activity",
            "activity_kind": "operation",
            "activity_weight": 0,
            "fab_name_list": [],
        },
        {
            "@timestamp": _iso_z(now - timedelta(minutes=31)),
            "level": "INFO",
            "logger": "skewnono.activity",
            "message": "user=choi.eunwoo method=POST path=/api/ebeam/cdsem/recipe-search status=200 ms=126 remote=10.20.30.14",
            "host": "local-demo",
            "event": "request",
            "user_id": "choi.eunwoo",
            "method": "POST",
            "path": "/api/ebeam/cdsem/recipe-search",
            "request_path": "/api/ebeam/cdsem/recipe-search",
            "query_string": "",
            "status": 200,
            "latency_ms": 126,
            "remote_addr": "10.20.30.14",
            "feature": "ebeam",
            "activity_kind": "feature",
            "activity_weight": 1,
            "fab_name_list": ["M16B"],
        },
        {
            "@timestamp": _iso_z(now - timedelta(hours=2, minutes=8)),
            "level": "ERROR",
            "logger": "skewnono.activity",
            "message": "user=jung.hari method=GET path=/api/admin/logs status=503 ms=24 remote=10.20.30.15",
            "host": "local-demo",
            "event": "request",
            "user_id": "jung.hari",
            "method": "GET",
            "path": "/api/admin/logs",
            "request_path": "/api/admin/logs",
            "query_string": "level=ERROR",
            "status": 503,
            "latency_ms": 24,
            "remote_addr": "10.20.30.15",
            "feature": "admin",
            "activity_kind": "operation",
            "activity_weight": 0,
            "fab_name_list": [],
            "error_code": "503",
            "error_name": "Service Unavailable",
        },
    ]
    # _record_to_doc puts these on EVERY document unconditionally, and
    # request_id on every request log. Injected here rather than repeated in
    # each literal above so the two lists cannot drift apart.
    for position, row in enumerate(rows, start=1):
        row.setdefault("event_id", f"demo-event-{position:04d}")
        row.setdefault("service", "skewnono")
        row.setdefault("deployment", "local")
        row.setdefault("request_id", f"demo-req-{position:04d}")
    return rows


def _parse_demo_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _matches_demo(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    row_time = _parse_demo_time(row.get("@timestamp"))
    from_time = _parse_demo_time(filters.get("from"))
    to_time = _parse_demo_time(filters.get("to"))
    if row_time is not None and from_time is not None and row_time < from_time:
        return False
    if row_time is not None and to_time is not None and row_time > to_time:
        return False

    level = str(filters.get("level") or "")
    if level and str(row.get("level")) not in _split_csv(level):
        return False

    for key in ("event", "method", "user_id", "feature", "activity_kind"):
        value = str(filters.get(key) or "")
        if value and str(row.get(key) or "") != value:
            return False

    fab_name = str(filters.get("fab_name") or "")
    if fab_name and not any(
        fab in (row.get("fab_name_list") or [])
        for fab in _split_csv(fab_name)
    ):
        return False

    path = str(filters.get("path") or "").lower()
    if path and path not in str(row.get("path") or "").lower():
        return False

    status = row.get("status")
    status_min = filters.get("status_min")
    status_max = filters.get("status_max")
    if status_min and isinstance(status, int) and status < int(status_min):
        return False
    if status_max and isinstance(status, int) and status > int(status_max):
        return False

    q = str(filters.get("q") or "").lower()
    if q:
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("message", "path", "user_id", "error_name")
        )
        exception = row.get("exception")
        if isinstance(exception, dict):
            haystack += " " + " ".join(str(value or "") for value in exception.values())
        if q not in haystack.lower():
            return False

    return True


def query_logs(params: Mapping[str, Any]) -> LogQueryResponse:
    parsed = parse_log_query(params)
    filters = {**parsed.filters, "demo_mode": True}
    now = _utc_now()
    rows = [
        row
        for row in _demo_source(now)
        if _matches_demo(row, filters)
    ]
    start = (parsed.page - 1) * parsed.page_size
    hits = [
        {
            "_id": f"demo-{start + idx + 1}",
            "_index": "skewnono_logging_local-demo",
            "_source": row,
        }
        for idx, row in enumerate(
            rows[start : start + parsed.page_size]
        )
    ]
    return {
        "generated_at": _iso_z(now),
        "page": parsed.page,
        "page_size": parsed.page_size,
        "total": len(rows),
        "page_count": page_count_for(len(rows), parsed.page_size),
        "filters": filters,
        "items": [item_from_hit(hit) for hit in hits],
    }
