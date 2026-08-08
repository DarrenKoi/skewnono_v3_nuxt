"""Shared admin-log query parsing and OpenSearch hit normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home._core.opensearch import wildcard_clause
from back_dev_home._logging.policy import normalize_fab_name_list
from back_dev_home.admin_logs.contracts import LogItem, LogQueryResponse

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
# OpenSearch rejects from+size beyond index.max_result_window (default 10k);
# fail as a 400 up front instead of surfacing a generic 503 at query time.
MAX_RESULT_WINDOW = 10_000

# Fields the `q` free-text search covers. The office query builds per-field
# clauses from these tuples; the mock substring-matches FREE_TEXT_FIELDS. The
# field set is part of the contract, so both providers read it from here.
_FREE_TEXT_PHRASE_FIELDS = ("message", "exception.message", "exception.stack")
# Keyword-mapped: match_phrase would only hit exact full values, so these are
# substring-matched with a wildcard instead.
_FREE_TEXT_WILDCARD_FIELDS = ("error_name", "path", "user_id")
FREE_TEXT_FIELDS = _FREE_TEXT_PHRASE_FIELDS + _FREE_TEXT_WILDCARD_FIELDS


@dataclass(frozen=True)
class ParsedLogQuery:
    query: dict[str, Any]
    filters: dict[str, Any]
    page: int
    page_size: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 datetime into aware UTC. Raises ValueError.

    A trailing ``Z`` is accepted. A value carrying no offset is read as UTC
    rather than local time — OFFICE-VERIFY: believed to match how OpenSearch
    reads an offset-less date in a range query, but unverified against the real
    cluster. Only the mock's own filtering depends on it; the office adapter
    forwards the caller's string to OpenSearch untouched, so the two could
    disagree for a naive value until this is confirmed.
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
    # Reject malformed values here so the route answers 400 invalid_log_query;
    # passed through, they would surface as a 503 outage message at the office
    # and be silently ignored by the mock.
    for key, value in (("from", from_value), ("to", to_value)):
        if value:
            try:
                parse_iso_utc(value)
            except ValueError as exc:
                raise ValueError(
                    f"{key} must be an ISO-8601 datetime, got {value!r}"
                ) from exc
    now = utc_now()
    return (
        from_value or iso_z(now - timedelta(hours=24)),
        to_value or iso_z(now),
    )


def split_csv(value: str) -> list[str]:
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
        filters.append({"terms": {"level": split_csv(level)}})

    term_values = {
        "event": _read_str(params, "event"),
        "method": _read_str(params, "method").upper(),
        "user_id": _read_str(params, "user_id"),
        "feature": _read_str(params, "feature"),
        "activity_kind": _read_str(params, "activity_kind"),
    }
    for field, value in term_values.items():
        if value:
            filters.append({"term": {field: value}})

    # The writer indexes fab_name_list through the same normalization, so a
    # hand-rolled .upper() here could never match comma-separated input.
    fab_names = normalize_fab_name_list([_read_str(params, "fab_name")])
    if fab_names:
        filters.append({"terms": {"fab_name_list": fab_names}})

    path = _read_str(params, "path")
    if path:
        filters.append(wildcard_clause("path", path))

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
        should: list[dict[str, Any]] = [
            {"match_phrase": {field: q}} for field in _FREE_TEXT_PHRASE_FIELDS
        ]
        should += [
            wildcard_clause(field, q) for field in _FREE_TEXT_WILDCARD_FIELDS
        ]
        must.append({"bool": {"should": should, "minimum_should_match": 1}})

    bool_query: dict[str, Any] = {"filter": filters}
    if must:
        bool_query["must"] = must
    return {"bool": bool_query}, {
        "from": from_value,
        "to": to_value,
        "level": level,
        **term_values,
        "fab_name": ",".join(fab_names),
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
    if page * page_size > MAX_RESULT_WINDOW:
        raise ValueError(
            f"page {page} with page_size {page_size} is beyond the "
            f"{MAX_RESULT_WINDOW}-document result window; "
            "narrow the time range or filters instead"
        )
    query, filters = _build_filter_query(params, from_value, to_value)
    return ParsedLogQuery(
        query=query,
        filters=filters,
        page=page,
        page_size=page_size,
    )


def page_count_for(total: int, page_size: int) -> int:
    """Last servable page: total-derived, clamped to the result window."""
    by_total = -(-total // page_size)
    return max(1, min(by_total, MAX_RESULT_WINDOW // page_size))


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
    total = _total_from_response(result)
    return {
        "generated_at": iso_z(utc_now()),
        "page": parsed.page,
        "page_size": parsed.page_size,
        "total": total,
        "page_count": page_count_for(total, parsed.page_size),
        "filters": filters,
        "items": [
            item_from_hit(hit)
            for hit in hits
            if isinstance(hit, dict)
        ],
    }
