"""Shared admin-log query parsing and OpenSearch hit normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home.admin_logs.contracts import LogItem, LogQueryResponse

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class ParsedLogQuery:
    query: dict[str, Any]
    filters: dict[str, Any]
    page: int
    page_size: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _read_str(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip()


def _read_int(
    params: Mapping[str, Any],
    key: str,
    default: int,
) -> int:
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


def _build_filter_query(
    params: Mapping[str, Any],
    from_value: str,
    to_value: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
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
        must.append(
            {
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
            }
        )

    bool_query: dict[str, Any] = {"filter": filters}
    if must:
        bool_query["must"] = must
    return {"bool": bool_query}, {
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


def parse_log_query(params: Mapping[str, Any]) -> ParsedLogQuery:
    from_value, to_value = _read_time_range(params)
    page = max(1, _read_int(params, "page", 1))
    page_size = max(
        1,
        min(
            MAX_PAGE_SIZE,
            _read_int(params, "page_size", DEFAULT_PAGE_SIZE),
        ),
    )
    query, filters = _build_filter_query(params, from_value, to_value)
    return ParsedLogQuery(
        query=query,
        filters=filters,
        page=page,
        page_size=page_size,
    )


def _total_from_response(response: dict[str, Any]) -> int:
    total = response.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        value = total.get("value", 0)
        return int(value) if isinstance(value, int) else 0
    return int(total) if isinstance(total, int) else 0


def item_from_hit(hit: dict[str, Any]) -> LogItem:
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


def response_from_result(
    result: dict[str, Any],
    parsed: ParsedLogQuery,
    *,
    extra_filters: Mapping[str, Any] | None = None,
) -> LogQueryResponse:
    filters = dict(parsed.filters)
    if extra_filters:
        filters.update(extra_filters)
    hits = result.get("hits", {}).get("hits", [])
    return {
        "generated_at": _iso_z(_utc_now()),
        "page": parsed.page,
        "page_size": parsed.page_size,
        "total": _total_from_response(result),
        "filters": filters,
        "items": [
            item_from_hit(hit)
            for hit in hits
            if isinstance(hit, dict)
        ],
    }
