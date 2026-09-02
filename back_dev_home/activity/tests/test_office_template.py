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
                        {
                            "key_as_string": "2026-07-26",
                            "doc_count": 2,
                            "features": {
                                "doc_count": 1,
                                "items": {
                                    "buckets": [
                                        {"key": "storage", "doc_count": 1}
                                    ]
                                },
                            },
                        },
                        {
                            "key_as_string": "2026-07-27",
                            "doc_count": 3,
                            # doc_count 3 with only 2 in the listed bucket:
                            # the day had a feature the cap dropped, and
                            # other_count must still be 0 rather than 1.
                            "features": {
                                "doc_count": 3,
                                "items": {
                                    "buckets": [
                                        {"key": "afm", "doc_count": 2}
                                    ]
                                },
                            },
                        },
                    ]
                },
            },
            "features": {
                "doc_count": 3,
                "items": {
                    "buckets": [
                        {
                            "key": "storage",
                            "doc_count": 3,
                            "last_at": {
                                "value": 1,
                                "value_as_string": "2026-07-27T02:00:00.000Z",
                            },
                        }
                    ]
                },
            },
        },
    }


def _summary_response():
    return {
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


def _fab_response():
    return {
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


def _empty_fab_response():
    return {"aggregations": {"fabs": {"buckets": []}}}


def _kind_terms(node, found=None):
    """Every activity_kind value asserted anywhere in a query body."""
    found = [] if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                key in ("term", "terms")
                and isinstance(value, dict)
                and "activity_kind" in value
            ):
                entry = value["activity_kind"]
                found.extend(entry if isinstance(entry, list) else [entry])
            else:
                _kind_terms(value, found)
    elif isinstance(node, list):
        for item in node:
            _kind_terms(item, found)
    return found


def test_history_query_uses_kst_bounds_and_page_view_ranking():
    reader, search, aliases = _reader([_history_response()])

    payload = reader.get_me("u1")

    assert aliases == ["skewnono_logging_local"]
    common = [
        {"term": {"event": "request"}},
        {"term": {"activity_weight": 1}},
        {"terms": {"activity_kind": ["entry", "feature", "page_view"]}},
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
        "term": {"activity_kind": "page_view"}
    }
    # The widened top-level query means the request-based windows must state
    # their own kinds; if they stop doing so they silently count page views.
    assert _kind_terms(body["aggs"]["this_month"]) == ["entry", "feature"]
    # The window itself, not the whole subtree: the per-day breakdown nested
    # under it states its own kind, which is the point of it.
    assert _kind_terms(body["aggs"]["daily"]["filter"]) == ["entry", "feature"]
    assert payload["user_id"] == "u1"
    assert payload["is_admin"] is False
    assert payload["this_month"] == {"requests": 5, "days_active": 2}
    assert payload["recent_features"] == [
        {"feature": "storage", "at": "2026-07-27T02:00:00.000Z"}
    ]
    # Ordered by when each feature was last opened, not by how often — the
    # whole point of the card, and the one clause a refactor can silently drop.
    assert body["aggs"]["features"]["aggs"]["items"]["terms"]["order"] == {
        "last_at": "desc"
    }
    assert len(payload["daily"]) == 30
    assert payload["daily"][-2:] == [
        {
            "date": "2026-07-26",
            "count": 2,
            "features": [{"feature": "storage", "count": 1}],
            "other_count": 1,
        },
        {
            "date": "2026-07-27",
            "count": 3,
            "features": [{"feature": "afm", "count": 2}],
            "other_count": 0,
        },
    ]
    assert payload["daily"][0] == {
        "date": "2026-06-28",
        "count": 0,
        "features": [],
        "other_count": 0,
    }
    # The per-day breakdown narrows to the feature kind inside a bucket the
    # entry kind also counts toward, so the parts need not sum to the bar.
    day_features = body["aggs"]["daily"]["aggs"]["days"]["aggs"]["features"]
    assert day_features["filter"] == {"term": {"activity_kind": "feature"}}
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
    reader, search, _aliases = _reader([_summary_response()])

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

    def window_start(name):
        clauses = aggs[name]["filter"]["bool"]["filter"]
        return clauses[0]["range"]["@timestamp"]["gte"]

    assert window_start("dau").startswith("2026-07-27T00:00:00+09:00")
    assert window_start("wau").startswith("2026-07-21T00:00:00+09:00")
    assert window_start("mau").startswith("2026-06-28T00:00:00+09:00")
    assert aggs["top_features_7d"]["filter"]["bool"]["filter"][1] == {
        "terms": {"activity_kind": ["page_view"]}
    }


def test_summary_ranks_page_views_but_counts_users_from_requests():
    reader, search, _ = _reader([_summary_response()])

    reader.get_summary()

    body = search.bodies[-1]
    ranking = body["aggs"]["top_features_7d"]["filter"]
    assert _kind_terms(ranking) == ["page_view"]

    dau = body["aggs"]["dau"]["filter"]
    assert sorted(_kind_terms(dau)) == ["entry", "feature"]


def test_fab_page_ranking_stays_request_based():
    """Beacons carry no fab_name, so this aggregation cannot switch."""
    # get_fab_page_usage issues TWO searches — a 7d window then a 30d one — so
    # the fake client needs two responses queued or the second call pops an
    # empty list. Only the last body is asserted on here.
    reader, search, _ = _reader([_fab_response(), _empty_fab_response()])

    reader.get_fab_page_usage()

    body = search.bodies[-1]
    fab_agg = body["aggs"]
    assert "page_view" not in _kind_terms(fab_agg)
    assert "feature" in _kind_terms(fab_agg)
    # The whole fab query is narrowed, so the composite bucketing and the
    # active_users cardinality cannot see a beacon either — otherwise a page
    # open would invent a "미지정" fab and an active user for it.
    assert "page_view" not in _kind_terms(body["query"])
    assert {"terms": {"activity_kind": ["entry", "feature"]}} in (
        body["query"]["bool"]["filter"]
    )


def test_users_are_paged_sorted_and_recent_is_page_view_only():
    responses = [
        {
            "aggregations": {
                "users": {
                    "after_key": {"user_id": "u2"},
                    "buckets": [
                        {
                            "key": {"user_id": "u2"},
                            # doc_count on the bucket now spans page views
                            # too; only requests_only may be counted.
                            "doc_count": 40,
                            "requests_only": {
                                "doc_count": 2,
                                "days": {"buckets": [{"doc_count": 2}]},
                            },
                            "last_seen": {
                                "value_as_string": "2026-07-25T00:00:00Z"
                            },
                            "feature_only": {
                                "recent": {
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
                            "doc_count": 99,
                            "requests_only": {
                                "doc_count": 5,
                                "days": {
                                    "buckets": [
                                        {"doc_count": 2},
                                        {"doc_count": 3},
                                    ]
                                },
                            },
                            "last_seen": {
                                "value_as_string": "2026-07-27T02:00:00Z"
                            },
                            "feature_only": {
                                "recent": {"buckets": []}
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
    assert payload["users"][0]["recent_feature"] is None
    assert payload["users"][1]["recent_feature"] == "storage"
    assert search.bodies[1]["aggs"]["users"]["composite"]["after"] == {
        "user_id": "u2"
    }
    recent_filter = search.bodies[0]["aggs"]["users"]["aggs"]["feature_only"]
    assert recent_filter["aggs"]["recent"]["terms"]["order"] == {
        "last_at": "desc"
    }
    assert recent_filter["filter"] == {
        "term": {"activity_kind": "page_view"}
    }
    # The counters read requests_only, not the widened bucket doc_count.
    assert [row["requests_30d"] for row in payload["users"]] == [5, 2]
    assert [row["days_active_30d"] for row in payload["users"]] == [2, 1]
    user_aggs = search.bodies[0]["aggs"]["users"]["aggs"]
    assert user_aggs["requests_only"]["filter"] == {
        "terms": {"activity_kind": ["entry", "feature"]}
    }
    # last_seen stays outside the kind split on purpose: presence, not volume.
    assert _kind_terms(user_aggs["last_seen"]) == []
    assert [row["last_seen"] for row in payload["users"]] == [
        "2026-07-27T02:00:00Z",
        "2026-07-25T00:00:00Z",
    ]


def test_fab_totals_use_distinct_users_and_normalize_missing_keys():
    reader, _search, _aliases = _reader(
        [_fab_response(), _empty_fab_response()]
    )

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
    # The /users routes are admin-gated, so the failure path needs an admin
    # caller — otherwise the gate answers 403 before the loader ever runs.
    monkeypatch.delenv("SKEWNONO_ADMIN_USERS", raising=False)
    app = Flask(__name__)

    @app.before_request
    def identity():
        g.user_id = "local-dev"
        g.identity_source = "local"

    app.register_blueprint(routes.bp, url_prefix="/api")
    response = app.test_client().get(path)

    assert response.status_code == 503
    assert response.json == {
        "error": {
            "code": "activity_query_failed",
            "message": "Could not query OpenSearch activity",
        }
    }
