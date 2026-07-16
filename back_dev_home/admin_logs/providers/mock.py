from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home._runtime.env import is_cloud
from back_dev_home.admin_logs.contracts import LogItem, LogQueryResponse

INDEX_ALIAS = "skewnono_logging"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_str(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip()


def _read_int(params: Mapping[str, Any], key: str, default: int) -> int:
    raw = _read_str(params, key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _read_time_range(params: Mapping[str, Any]) -> tuple[str, str]:
    from_value = _read_str(params, "from")
    to_value = _read_str(params, "to")
    if from_value and to_value:
        return from_value, to_value
    now = _utc_now()
    return (
        from_value or _iso_z(now - timedelta(hours=24)),
        to_value or _iso_z(now),
    )


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _build_query(params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], int, int]:
    from_value, to_value = _read_time_range(params)
    page = max(1, _read_int(params, "page", 1))
    page_size = max(1, min(MAX_PAGE_SIZE, _read_int(params, "page_size", DEFAULT_PAGE_SIZE)))

    filters: list[dict[str, Any]] = [
        {"range": {"@timestamp": {"gte": from_value, "lte": to_value}}}
    ]

    level = _read_str(params, "level").upper()
    if level:
        filters.append({"terms": {"level": _split_csv(level)}})

    event = _read_str(params, "event")
    if event:
        filters.append({"term": {"event": event}})

    method = _read_str(params, "method").upper()
    if method:
        filters.append({"term": {"method": method}})

    user_id = _read_str(params, "user_id")
    if user_id:
        filters.append({"term": {"user_id": user_id}})

    feature = _read_str(params, "feature")
    if feature:
        filters.append({"term": {"feature": feature}})

    path = _read_str(params, "path")
    if path:
        filters.append({"wildcard": {"path": f"*{path}*"}})

    status_range: dict[str, int] = {}
    status_min = _read_str(params, "status_min")
    status_max = _read_str(params, "status_max")
    if status_min:
        status_range["gte"] = _read_int(params, "status_min", 0)
    if status_max:
        status_range["lte"] = _read_int(params, "status_max", 0)
    if status_range:
        filters.append({"range": {"status": status_range}})

    must: list[dict[str, Any]] = []
    q = _read_str(params, "q")
    if q:
        must.append({
            "bool": {
                "should": [
                    {"match_phrase": {"message": q}},
                    {"match_phrase": {"exception.message": q}},
                    {"match_phrase": {"exception.stack": q}},
                    {"match_phrase": {"error_name": q}},
                    {"wildcard": {"path": f"*{q}*"}},
                    {"wildcard": {"user_id": f"*{q}*"}},
                ],
                "minimum_should_match": 1,
            }
        })

    bool_query: dict[str, Any] = {"filter": filters}
    if must:
        bool_query["must"] = must

    query = {"bool": bool_query}
    applied_filters = {
        "from": from_value,
        "to": to_value,
        "level": level,
        "event": event,
        "method": method,
        "user_id": user_id,
        "feature": feature,
        "path": path,
        "status_min": status_min,
        "status_max": status_max,
        "q": q,
    }
    return query, applied_filters, page, page_size


def _total_from_response(response: dict[str, Any]) -> int:
    total = response.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        value = total.get("value", 0)
        return int(value) if isinstance(value, int) else 0
    return int(total) if isinstance(total, int) else 0


def _item_from_hit(hit: dict[str, Any]) -> LogItem:
    source = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
    exception = source.get("exception")
    return {
        "id": str(hit.get("_id", "")),
        "index": str(hit.get("_index", "")),
        "timestamp": source.get("@timestamp"),
        "level": source.get("level"),
        "event": source.get("event"),
        "logger": source.get("logger"),
        "user_id": source.get("user_id"),
        "method": source.get("method"),
        "path": source.get("path") or source.get("request_path"),
        "status": source.get("status"),
        "latency_ms": source.get("latency_ms"),
        "feature": source.get("feature"),
        "message": source.get("message"),
        "exception": exception if isinstance(exception, dict) else None,
        "raw": dict(source),
    }


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
            "activity_weight": 0,
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
            "activity_weight": 0,
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
            "activity_weight": 0,
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
            "activity_weight": 1,
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
            "activity_weight": 0,
            "error_code": "503",
            "error_name": "Service Unavailable",
        },
    ]
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

    for key in ("event", "method", "user_id", "feature"):
        value = str(filters.get(key) or "")
        if value and str(row.get(key) or "") != value:
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


def _demo_logs(params: Mapping[str, Any]) -> LogQueryResponse:
    _query, applied_filters, page, page_size = _build_query(params)
    applied_filters["demo_mode"] = True
    now = _utc_now()
    rows = [
        row for row in _demo_source(now)
        if _matches_demo(row, applied_filters)
    ]
    start = (page - 1) * page_size
    hits = [
        {
            "_id": f"demo-{start + idx + 1}",
            "_index": f"{INDEX_ALIAS}-demo",
            "_source": row,
        }
        for idx, row in enumerate(rows[start:start + page_size])
    ]
    return {
        "generated_at": _iso_z(now),
        "page": page,
        "page_size": page_size,
        "total": len(rows),
        "filters": applied_filters,
        "items": [_item_from_hit(hit) for hit in hits],
    }


def query_logs(params: Mapping[str, Any]) -> LogQueryResponse:
    if not os.environ.get("OPENSEARCH_PASSWORD"):
        if not is_cloud():
            return _demo_logs(params)
        raise RuntimeError("OPENSEARCH_PASSWORD is not configured")

    from ops_store import OSSearch

    query, applied_filters, page, page_size = _build_query(params)
    body = {
        "from": (page - 1) * page_size,
        "size": page_size,
        "track_total_hits": True,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": query,
    }
    result = OSSearch(index=INDEX_ALIAS).search_raw(body)
    hits = result.get("hits", {}).get("hits", [])
    return {
        "generated_at": _iso_z(_utc_now()),
        "page": page,
        "page_size": page_size,
        "total": _total_from_response(result),
        "filters": applied_filters,
        "items": [_item_from_hit(hit) for hit in hits if isinstance(hit, dict)],
    }
