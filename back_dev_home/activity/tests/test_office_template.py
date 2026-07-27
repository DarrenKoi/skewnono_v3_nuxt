from datetime import datetime, timezone

import pytest
from flask import Flask, g

from back_dev_home._logging.target import LoggingTarget
from back_dev_home.activity import routes
from back_dev_home.activity.providers.opensearch_reader import (
    ActivityOpenSearchReader,
)

NOW = datetime(2026, 7, 27, 3, 0, tzinfo=timezone.utc)


class _FakeSearch:
    def __init__(self, responses):
        self.responses = list(responses)
        self.bodies = []

    def search_raw(self, body):
        self.bodies.append(body)
        return self.responses.pop(0)


def _reader(responses, environment="local", admin_check=lambda _user_id: False):
    search = _FakeSearch(responses)
    aliases = []

    def search_factory(alias):
        aliases.append(alias)
        return search

    target = (
        LoggingTarget("local", "skewnono_logging_local", "local")
        if environment == "local"
        else LoggingTarget("production", "skewnono_logging", "production")
    )
    reader = ActivityOpenSearchReader(
        search_factory=search_factory,
        target_resolver=lambda: target,
        now=lambda: NOW,
        admin_check=admin_check,
    )
    return reader, search, aliases


def _history_response(total=5):
    return {
        "hits": {"total": {"value": total, "relation": "eq"}, "hits": []},
        "aggregations": {
            "first_seen": {
                "value": 1,
                "value_as_string": "2026-07-01T01:00:00.000Z",
            },
            "last_seen": {
                "value": 1,
                "value_as_string": "2026-07-27T02:00:00.000Z",
            },
            "this_month": {
                "doc_count": 5,
                "days": {
                    "buckets": [
                        {"key_as_string": "2026-07-26", "doc_count": 2},
                        {"key_as_string": "2026-07-27", "doc_count": 3},
                    ]
                },
            },
            "daily": {
                "doc_count": 5,
                "days": {
                    "buckets": [
                        {"key_as_string": "2026-07-26", "doc_count": 2},
                        {"key_as_string": "2026-07-27", "doc_count": 3},
                    ]
                },
            },
            "features": {
                "doc_count": 3,
                "items": {
                    "buckets": [{"key": "storage", "doc_count": 3}]
                },
            },
        },
    }


def test_history_query_uses_kst_bounds_and_feature_only_ranking():
    reader, search, aliases = _reader([_history_response()])

    payload = reader.get_me("u1")

    assert aliases == ["skewnono_logging_local"]
    common = [
        {"term": {"event": "request"}},
        {"term": {"activity_weight": 1}},
        {"terms": {"activity_kind": ["entry", "feature"]}},
        {"term": {"user_id": "u1"}},
    ]
    body = search.bodies[0]
    assert body["query"]["bool"]["filter"] == common
    histogram = body["aggs"]["daily"]["aggs"]["days"]["date_histogram"]
    assert histogram == {
        "field": "@timestamp",
        "calendar_interval": "day",
        "time_zone": "Asia/Seoul",
        "format": "yyyy-MM-dd",
        "min_doc_count": 0,
        "extended_bounds": {
            "min": "2026-06-28",
            "max": "2026-07-27",
        },
    }
    assert body["aggs"]["features"]["filter"] == {
        "term": {"activity_kind": "feature"}
    }
    assert payload["user_id"] == "u1"
    assert payload["is_admin"] is False
    assert payload["this_month"] == {"requests": 5, "days_active": 2}
    assert payload["top_features"] == [{"feature": "storage", "count": 3}]
    assert len(payload["daily"]) == 30
    assert payload["daily"][-2:] == [
        {"date": "2026-07-26", "count": 2},
        {"date": "2026-07-27", "count": 3},
    ]
    assert payload["first_seen"] == "2026-07-01T01:00:00.000Z"
    assert payload["last_seen"] == "2026-07-27T02:00:00.000Z"


def test_production_target_selects_the_production_alias():
    reader, _search, aliases = _reader([_history_response()], "production")
    reader.get_me("u1")
    assert aliases == ["skewnono_logging"]


def test_missing_user_history_returns_none():
    reader, _search, _aliases = _reader([_history_response(total=0)])
    assert reader.get_user_history("missing") is None


def test_summary_normalizes_cardinality_and_trailing_windows():
    response = {
        "aggregations": {
            "dau": {"doc_count": 3, "users": {"value": 2}},
            "wau": {"doc_count": 8, "users": {"value": 4}},
            "mau": {"doc_count": 13, "users": {"value": 6}},
            "top_features_7d": {
                "doc_count": 5,
                "items": {
                    "buckets": [{"key": "storage", "doc_count": 5}]
                },
            },
            "top_features_30d": {
                "doc_count": 9,
                "items": {
                    "buckets": [{"key": "recipe_search", "doc_count": 9}]
                },
            },
        }
    }
    reader, search, _aliases = _reader([response])

    payload = reader.get_summary()

    assert payload == {
        "generated_at": "2026-07-27T03:00:00Z",
        "dau": 2,
        "wau": 4,
        "mau": 6,
        "top_features_7d": [{"feature": "storage", "count": 5}],
        "top_features_30d": [
            {"feature": "recipe_search", "count": 9}
        ],
    }
    aggs = search.bodies[0]["aggs"]
    assert aggs["dau"]["filter"]["range"]["@timestamp"]["gte"].startswith(
        "2026-07-27T00:00:00+09:00"
    )
    assert aggs["wau"]["filter"]["range"]["@timestamp"]["gte"].startswith(
        "2026-07-21T00:00:00+09:00"
    )
    assert aggs["mau"]["filter"]["range"]["@timestamp"]["gte"].startswith(
        "2026-06-28T00:00:00+09:00"
    )
    assert aggs["top_features_7d"]["filter"]["bool"]["filter"][1] == {
        "term": {"activity_kind": "feature"}
    }


def test_users_are_paged_sorted_and_favorite_is_feature_only():
    responses = [
        {
            "aggregations": {
                "users": {
                    "after_key": {"user_id": "u2"},
                    "buckets": [
                        {
                            "key": {"user_id": "u2"},
                            "doc_count": 2,
                            "days": {"buckets": [{"doc_count": 2}]},
                            "last_seen": {
                                "value_as_string": "2026-07-25T00:00:00Z"
                            },
                            "feature_only": {
                                "favorite": {
                                    "buckets": [
                                        {"key": "storage", "doc_count": 1}
                                    ]
                                }
                            },
                        }
                    ],
                }
            }
        },
        {
            "aggregations": {
                "users": {
                    "buckets": [
                        {
                            "key": {"user_id": "u1"},
                            "doc_count": 5,
                            "days": {
                                "buckets": [
                                    {"doc_count": 2},
                                    {"doc_count": 3},
                                ]
                            },
                            "last_seen": {
                                "value_as_string": "2026-07-27T02:00:00Z"
                            },
                            "feature_only": {
                                "favorite": {"buckets": []}
                            },
                        }
                    ]
                }
            }
        },
    ]
    reader, search, _aliases = _reader(responses)

    payload = reader.get_users_list()

    assert [row["user_id"] for row in payload["users"]] == ["u1", "u2"]
    assert payload["users"][0]["favorite_feature"] is None
    assert payload["users"][1]["favorite_feature"] == "storage"
    assert search.bodies[1]["aggs"]["users"]["composite"]["after"] == {
        "user_id": "u2"
    }
    favorite_filter = search.bodies[0]["aggs"]["users"]["aggs"]["feature_only"]
    assert favorite_filter["filter"] == {
        "term": {"activity_kind": "feature"}
    }


def test_fab_totals_use_distinct_users_and_normalize_missing_keys():
    response_7d = {
        "aggregations": {
            "fabs": {
                "buckets": [
                    {
                        "key": {"fab": "M14"},
                        "doc_count": 9,
                        "active_users": {"value": 2},
                        "feature_only": {
                            "pages": {
                                "buckets": [
                                    {"key": "storage", "doc_count": 7}
                                ]
                            }
                        },
                    },
                    {
                        "key": {"fab": "M16"},
                        "doc_count": 1,
                        "active_users": {"value": 1},
                        "feature_only": {"pages": {"buckets": []}},
                    },
                    {
                        "key": {"fab": None},
                        "doc_count": 4,
                        "active_users": {"value": 1},
                        "feature_only": {"pages": {"buckets": []}},
                    },
                ]
            }
        }
    }
    response_30d = {"aggregations": {"fabs": {"buckets": []}}}
    reader, _search, _aliases = _reader([response_7d, response_30d])

    payload = reader.get_fab_page_usage()

    assert payload["fabs_7d"] == [
        {
            "fab": "M14",
            "total": 2,
            "pages": [{"feature": "storage", "count": 7}],
        },
        {"fab": "M16", "total": 1, "pages": []},
        {"fab": "미지정", "total": 1, "pages": []},
    ]
    assert payload["fabs_30d"] == []


@pytest.mark.parametrize(
    ("path", "loader_name"),
    [
        ("/api/activity/me", "get_me"),
        ("/api/activity/summary", "get_summary"),
        ("/api/activity/fabs", "get_fab_page_usage"),
        ("/api/activity/users", "get_users_list"),
        ("/api/activity/users/u1", "get_user_history"),
    ],
)
def test_activity_query_failures_are_normalized_to_503(
    monkeypatch,
    path,
    loader_name,
):
    def fail(*_args):
        raise ConnectionError("cluster detail must not leak")

    monkeypatch.setattr(routes, loader_name, fail)
    app = Flask(__name__)

    @app.before_request
    def identity():
        g.user_id = "u1"

    app.register_blueprint(routes.bp, url_prefix="/api")
    response = app.test_client().get(path)

    assert response.status_code == 503
    assert response.json == {
        "error": {
            "code": "activity_query_failed",
            "message": "Could not query OpenSearch activity",
        }
    }
