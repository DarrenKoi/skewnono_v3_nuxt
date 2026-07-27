"""Tracked office adapter for the configured OpenSearch logging alias."""

from collections.abc import Mapping
from typing import Any

from ops_store import OSSearch

from back_dev_home._logging.target import resolve_logging_target
from back_dev_home.admin_logs.contracts import LogQueryResponse
from back_dev_home.admin_logs.query import (
    parse_log_query,
    response_from_result,
)


def query_logs(params: Mapping[str, Any]) -> LogQueryResponse:
    target = resolve_logging_target()
    parsed = parse_log_query(params)
    body = {
        "from": (parsed.page - 1) * parsed.page_size,
        "size": parsed.page_size,
        "track_total_hits": True,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": parsed.query,
    }
    result = OSSearch(index=target.alias).search_raw(body)
    return response_from_result(
        result,
        parsed,
        extra_filters={
            "deployment": target.deployment,
            "index_alias": target.alias,
        },
    )
