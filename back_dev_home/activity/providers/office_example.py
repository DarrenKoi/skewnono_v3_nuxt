"""Tracked office adapter for OpenSearch-backed activity aggregation."""

from back_dev_home.activity.providers.opensearch_reader import (
    ActivityOpenSearchReader,
)

_reader = ActivityOpenSearchReader()

get_me = _reader.get_me
get_summary = _reader.get_summary
get_fab_page_usage = _reader.get_fab_page_usage
get_users_list = _reader.get_users_list
get_user_history = _reader.get_user_history


def record_request(*_args, **_kwargs) -> None:
    """Do not duplicate the canonical document written by logging middleware."""

    return None
