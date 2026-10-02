from datetime import datetime, timezone

import pytest
from flask import Flask, g

from backend._logging.target import LoggingTarget
from backend.activity import routes
from backend.activity.providers.opensearch_reader import (
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
    response = _history_response()
    response["aggregations"]["visits"] = {
        "days": {
            "buckets": [
                {"key_as_string": "2026-07-27", "doc_count": 3},
            ]
        }
    }
    reader, search, aliases = _reader([response])

    payload = reader.get_me("u1")

    assert aliases == ["skewnono_logging_local"]
    assert payload["visits"] == [{"date": "2026-07-27", "count": 3}]
    visits = search.bodies[0]["aggs"]["visits"]
    assert _kind_terms(visits["filter"]) == ["page_view"]
    visit_histogram = visits["aggs"]["days"]["date_histogram"]
    assert visit_histogram["time_zone"] == "Asia/Seoul"
    assert visit_histogram["extended_bounds"] == {
        "min": "2026-04-29",
        "max": "2026-07-27",
    }
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
        ("/api/activity/families", "get_family_page_usage"),
        ("/api/activity/users", "get_users_list"),
        ("/api/activity/users/u1", "get_user_history"),
        ("/api/activity/visitors", "get_daily_visitors"),
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


def _user_days(user_id, *days):
    return {
        "key": {"user_id": user_id},
        "doc_count": sum(count for _day, count in days),
        "days": {
            "buckets": [
                {"key_as_string": day, "doc_count": count}
                for day, count in days
            ]
        },
    }


def test_daily_visitors_roll_dau_wau_mau_from_each_persons_active_days():
    reader, search, _aliases = _reader(
        [
            {
                "aggregations": {
                    "users": {
                        "buckets": [
                            # 30 requests in a day is still one visitor.
                            _user_days(
                                "u1", ("2026-07-26", 30), ("2026-07-27", 2)
                            ),
                            _user_days("u2", ("2026-07-26", 1)),
                        ],
                        "after_key": {"user_id": "u2"},
                    }
                }
            },
            {
                "aggregations": {
                    "users": {
                        "buckets": [
                            # Off the chart (88 days back) but inside the
                            # first day's MAU window. The empty bucket is what
                            # a date_histogram emits between two active days;
                            # it must not read as a visit.
                            _user_days(
                                "u3", ("2026-04-30", 4), ("2026-07-27", 0)
                            ),
                        ]
                    }
                }
            },
        ]
    )

    payload = reader.get_daily_visitors()

    assert payload["generated_at"] == "2026-07-27T03:00:00Z"
    days = payload["days"]
    assert len(days) == 60
    assert days[0] == {"date": "2026-05-29", "visitors": 0, "wau": 0, "mau": 1}
    assert days[1] == {"date": "2026-05-30", "visitors": 0, "wau": 0, "mau": 0}
    assert days[-2:] == [
        {"date": "2026-07-26", "visitors": 2, "wau": 2, "mau": 2},
        # u2 did not come back today, but is still this week's and this
        # month's user — the reason these cannot be summed from `visitors`.
        {"date": "2026-07-27", "visitors": 1, "wau": 2, "mau": 2},
    ]

    first, second = search.bodies
    filters = first["query"]["bool"]["filter"]
    # Same population as the summary cards: request rows only, so a
    # page-view-only opener is not a visitor and today's row equals them.
    assert filters[:3] == [
        {"term": {"event": "request"}},
        {"term": {"activity_weight": 1}},
        {"terms": {"activity_kind": ["entry", "feature"]}},
    ]
    # 88 days back, not 59: the first charted day's MAU reaches that far.
    assert filters[3]["range"]["@timestamp"]["gte"].startswith(
        "2026-04-30T00:00:00+09:00"
    )
    users = first["aggs"]["users"]
    assert users["composite"]["sources"] == [
        {"user_id": {"terms": {"field": "user_id"}}}
    ]
    assert "after" not in users["composite"]
    assert second["aggs"]["users"]["composite"]["after"] == {"user_id": "u2"}
    histogram = users["aggs"]["days"]["date_histogram"]
    assert histogram["calendar_interval"] == "day"
    assert histogram["time_zone"] == "Asia/Seoul"
    assert histogram["format"] == "yyyy-MM-dd"
    # Users per page x days per user must stay under search.max_buckets
    # (65,535 by default), or the cluster answers 503 instead of a page.
    assert users["composite"]["size"] * 89 < 65_535


def _family_bucket(family, people, *pages):
    return {
        # The bucket key is the beacon URL the page open was posted to.
        "key": f"/api/page-view/{family}",
        "doc_count": sum(count for _page, count in pages),
        "openers": {"value": people},
        "pages": {
            "buckets": [
                {"key": page, "doc_count": count} for page, count in pages
            ]
        },
    }


def test_family_usage_lists_every_family_from_page_view_rows():
    reader, search, _aliases = _reader(
        [
            {
                "aggregations": {
                    "families_7d": {
                        "doc_count": 9,
                        "families": {
                            "buckets": [
                                _family_bucket(
                                    "cdsem", 2, ("storage", 5), ("hardware", 1)
                                ),
                                _family_bucket("afm", 1, ("afm", 3)),
                            ]
                        },
                    },
                    "families_30d": {
                        "doc_count": 0,
                        "families": {"buckets": []},
                    },
                }
            }
        ]
    )

    payload = reader.get_family_page_usage()

    assert payload["generated_at"] == "2026-07-27T03:00:00Z"
    # Registry order with the absent families filled in as zeros — a terms
    # aggregation returns no bucket at all for a family nobody opened.
    assert payload["families_7d"] == [
        {
            "family": "cdsem",
            "total": 2,
            "pages": [
                {"feature": "storage", "count": 5},
                {"feature": "hardware", "count": 1},
            ],
        },
        {"family": "hvsem", "total": 0, "pages": []},
        {"family": "veritysem", "total": 0, "pages": []},
        {"family": "provision", "total": 0, "pages": []},
        {"family": "afm", "total": 1, "pages": [{"feature": "afm", "count": 3}]},
    ]
    assert [row["total"] for row in payload["families_30d"]] == [0, 0, 0, 0, 0]

    (body,) = search.bodies
    # Page opens only, for the whole query: a request row can carry a family
    # too, and counting it would turn "opened a page" into "made a request".
    assert body["query"]["bool"]["filter"] == [
        {"term": {"event": "request"}},
        {"term": {"activity_weight": 1}},
        {"terms": {"activity_kind": ["page_view"]}},
    ]

    def window_start(name):
        clauses = body["aggs"][name]["filter"]["bool"]["filter"]
        return clauses[0]["range"]["@timestamp"]["gte"]

    assert window_start("families_7d").startswith("2026-07-21T00:00:00+09:00")
    assert window_start("families_30d").startswith("2026-06-28T00:00:00+09:00")
    families = body["aggs"]["families_7d"]["aggs"]["families"]
    # `path` is a keyword the index has always mapped: grouping on the beacon
    # URL is what lets this run with no change to the index.
    assert families["terms"]["field"] == "path"
    # Only the known vocabulary: a stray URL is not a sixth family, and the
    # plain /api/page-view (a page with no family) is not a row at all.
    assert families["terms"]["include"] == [
        "/api/page-view/cdsem",
        "/api/page-view/hvsem",
        "/api/page-view/veritysem",
        "/api/page-view/provision",
        "/api/page-view/afm",
    ]
    assert families["aggs"]["openers"]["cardinality"]["field"] == "user_id"
    assert families["aggs"]["pages"]["terms"]["field"] == "feature"


# ---------------------------------------------------------------------------
# Partial results. OpenSearch answers 200 with whatever the healthy shards
# returned unless told otherwise, so "the search did not finish" arrives as
# two fields on an otherwise ordinary response.


@pytest.mark.parametrize(
    "incomplete",
    [
        {"timed_out": True},
        {
            "timed_out": False,
            "_shards": {
                "total": 4,
                "successful": 3,
                "failed": 1,
                "failures": [{"shard": 2, "reason": {"type": "boom"}}],
            },
        },
    ],
    ids=["timed-out", "failed-shard"],
)
def test_a_partial_search_result_is_refused_not_served(incomplete):
    """Served as-is, a search that lost a shard reads as a quiet week: the
    numbers are low, plausible and wrong, and nobody re-checks a number that
    looks plausible. Same rule ebeam/_office_search.aggregate applies."""
    reader, _search, _aliases = _reader([{**_summary_response(), **incomplete}])

    with pytest.raises(RuntimeError, match="partial"):
        reader.get_summary()


def test_the_refusal_names_what_failed():
    """The message is all an operator gets — the route answers a generic 503
    and logs this."""
    failure = {"shard": 2, "index": "skewnono_logging-000007", "reason": "x"}
    response = {
        **_summary_response(),
        "_shards": {"total": 4, "successful": 3, "failed": 1, "failures": [failure]},
    }
    reader, _search, _aliases = _reader([response])

    with pytest.raises(RuntimeError) as raised:
        reader.get_summary()

    message = str(raised.value)
    assert "skewnono_logging_local" in message
    assert "failed=1" in message
    assert "skewnono_logging-000007" in message


@pytest.mark.parametrize(
    "complete",
    [
        {},
        {"timed_out": False, "_shards": {"total": 4, "successful": 4, "failed": 0}},
        # Skipped shards are an optimisation, not a failure.
        {"_shards": {"total": 4, "successful": 4, "skipped": 2, "failed": 0}},
    ],
    ids=["no-metadata", "all-shards-ok", "skipped-shards"],
)
def test_a_complete_search_result_is_served(complete):
    """Only a response that SAYS it is incomplete is refused. A missing field
    is not evidence of anything."""
    reader, _search, _aliases = _reader([{**_summary_response(), **complete}])

    assert reader.get_summary()["dau"] == 2


def test_a_partial_page_stops_a_paged_query_instead_of_being_skipped():
    """A composite walk must not return the pages it could read: half the
    users is not a smaller answer, it is a wrong one."""
    reader, search, _aliases = _reader(
        [
            {
                "aggregations": {
                    "users": {
                        "buckets": [_user_days("u1", ("2026-07-27", 1))],
                        "after_key": {"user_id": "u1"},
                    }
                }
            },
            {
                "timed_out": True,
                "aggregations": {"users": {"buckets": []}},
            },
        ]
    )

    with pytest.raises(RuntimeError, match="partial"):
        reader.get_daily_visitors()

    assert len(search.bodies) == 2
