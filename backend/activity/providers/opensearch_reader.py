"""Aggregate canonical request documents for the activity APIs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from backend._auth.admin import is_admin
from backend._core.timefmt import iso_z
from backend._logging.target import resolve_logging_target
from backend.activity.contracts import (
    DailyCount,
    FabUsageResponse,
    FabUsageRow,
    FamilyUsageResponse,
    FamilyUsageRow,
    FeatureCount,
    FeatureUse,
    MeResponse,
    SummaryResponse,
    UserHistoryResponse,
    UserListResponse,
    UserListRow,
    VisitorsResponse,
)
from backend.activity.providers.shared import (
    KST,
    FAMILY_BY_BEACON_PATH,
    RECENT_FEATURES_CAP,
    TOP_FEATURES_CAP,
    VISIT_DAYS,
    VISITOR_LOOKBACK_DAYS,
    daily_visitor_rows,
    family_usage_rows,
)

COMPOSITE_PAGE_SIZE = 1000
# Smaller than COMPOSITE_PAGE_SIZE on purpose. Every user bucket of the
# visitors query carries up to VISITOR_LOOKBACK_DAYS (89) day buckets, and the
# cluster refuses a response over search.max_buckets — 65,535 by default — with
# a 503. 500 x 89 stays under it; 1000 x 89 would not. OFFICE-VERIFY: the
# office cluster's actual max_buckets has not been read.
VISITOR_PAGE_SIZE = 500
CARDINALITY_PRECISION = 40000

# Two units share one index. Request rows answer "how much work happened";
# page_view rows answer "which page did people open". Every aggregation must
# say which it means — see the beacon design spec.
FEATURE_KIND = "feature"
REQUEST_KINDS = ["entry", FEATURE_KIND]
RANKING_KIND = "page_view"
ALL_KINDS = [*REQUEST_KINDS, RANKING_KIND]

# A terms agg ordered by a sub-aggregation is approximate: each shard returns
# its own top `shard_size` and a feature that ranks low on one shard can be
# dropped before the max-timestamp comparison ever happens. The feature
# vocabulary is a few dozen slugs (see _logging/feature_map.py), so asking
# every shard for 100 makes the recency order exact rather than nearly right.
FEATURE_SHARD_SIZE = 100


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _kst_day_start(now: datetime, days_ago: int) -> datetime:
    local = now.astimezone(KST)
    day = local.date() - timedelta(days=days_ago)
    return datetime.combine(day, time.min, tzinfo=KST)


def _time_range(start: datetime, now: datetime) -> dict[str, Any]:
    return {
        "range": {
            "@timestamp": {
                "gte": start.isoformat(),
                "lte": now.isoformat(),
            }
        }
    }


def _distinct_users_agg() -> dict[str, Any]:
    return {
        "cardinality": {
            "field": "user_id",
            "precision_threshold": CARDINALITY_PRECISION,
        }
    }


def _top_features_agg() -> dict[str, Any]:
    return {
        "terms": {
            "field": "feature",
            "size": TOP_FEATURES_CAP,
            "order": {"_count": "desc"},
        }
    }


def _kind_window(
    start: datetime,
    now: datetime,
    kinds: list[str],
) -> dict[str, Any]:
    return {
        "bool": {
            "filter": [
                _time_range(start, now),
                {"terms": {"activity_kind": kinds}},
            ]
        }
    }


def _activity_filters(
    user_id: str | None = None,
    kinds: list[str] = ALL_KINDS,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"term": {"event": "request"}},
        {"term": {"activity_weight": 1}},
        # Defaults to every kind, page views included. Because this is the
        # TOP-LEVEL query, an aggregation under it that omits its own kind
        # would silently start counting page views — so each one states it.
        # A query needing none of them narrows here instead (see _fab_window).
        {"terms": {"activity_kind": kinds}},
    ]
    if user_id is not None:
        filters.append({"term": {"user_id": user_id}})
    return filters


def _default_search_factory(alias: str) -> Any:
    from ops_store import OSSearch

    return OSSearch(index=alias)


def _iso_utc(value: datetime) -> str:
    return iso_z(value, timespec="auto")


def _feature_rows(node: dict[str, Any]) -> list[FeatureCount]:
    return [
        {
            "feature": str(bucket.get("key", "")),
            "count": int(bucket.get("doc_count", 0)),
        }
        for bucket in node.get("buckets", [])
        if bucket.get("key") not in (None, "")
    ]


def _recent_feature_agg(size: int) -> dict[str, Any]:
    """Features ordered by when they were last opened, newest first.

    Written once and used by both callers: the ``order`` clause is the whole
    difference between this card and a popularity list, and it fails silently
    if a refactor drops it — so there is one copy to drop.
    """
    return {
        "terms": {
            "field": "feature",
            "size": size,
            "shard_size": FEATURE_SHARD_SIZE,
            "order": {"last_at": "desc"},
        },
        "aggs": {"last_at": {"max": {"field": "@timestamp"}}},
    }


def _recent_feature_rows(node: dict[str, Any]) -> list[FeatureUse]:
    return [
        {"feature": str(bucket.get("key", "")), "at": str(last_at)}
        for bucket in node.get("buckets", [])
        if bucket.get("key") not in (None, "")
        and (last_at := bucket.get("last_at", {}).get("value_as_string"))
    ]


def _day_buckets(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``{YYYY-MM-DD: bucket}`` for a ``days`` date_histogram under ``node``."""
    return {
        str(bucket.get("key_as_string", "")).split("T", 1)[0]: bucket
        for bucket in node.get("days", {}).get("buckets", [])
    }


def _hits_total(response: dict[str, Any]) -> int:
    total = response.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        return int(total.get("value", 0))
    return int(total or 0)


class ActivityOpenSearchReader:
    """Read activity contracts from one environment-selected logging alias."""

    def __init__(
        self,
        *,
        search_factory: Callable[[str], Any] = _default_search_factory,
        target_resolver: Callable[[], Any] = resolve_logging_target,
        now: Callable[[], datetime] = _utc_now,
        admin_check: Callable[[str], bool] = is_admin,
    ) -> None:
        self._search_factory = search_factory
        self._target_resolver = target_resolver
        self._now_factory = now
        self._admin_check = admin_check
        self._search_service: Any = None
        self._search_alias: str | None = None

    def _now(self) -> datetime:
        value = self._now_factory()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _search(self, body: dict[str, Any]) -> dict[str, Any]:
        target = self._target_resolver()
        if self._search_service is None or self._search_alias != target.alias:
            self._search_service = self._search_factory(target.alias)
            self._search_alias = target.alias
        response = self._search_service.search_raw(body)
        # OpenSearch answers 200 with whatever the healthy shards returned, so
        # a search that timed out or lost a shard looks like a quiet week:
        # low, plausible, wrong. Refuse it — the route turns the raise into a
        # 503 and the page offers a retry. Same rule, same reason, as
        # ebeam/_office_search.aggregate.
        #
        # Only a response that SAYS it is incomplete is refused. The metadata
        # is not required to be present: its absence is not evidence, and
        # demanding it would add a second way to fail that proves nothing.
        shards = response.get("_shards")
        failed = shards.get("failed") if isinstance(shards, dict) else None
        if response.get("timed_out") or (type(failed) is int and failed > 0):
            raise RuntimeError(
                f"OpenSearch returned a partial result for {target.alias!r}: "
                f"timed_out={response.get('timed_out')!r} failed={failed!r} "
                f"failures={shards.get('failures') if isinstance(shards, dict) else None!r}"
            )
        return response

    def _history_query(
        self,
        user_id: str,
        now: datetime,
    ) -> dict[str, Any]:
        day_30 = _kst_day_start(now, 29)
        day_90 = _kst_day_start(now, VISIT_DAYS - 1)
        local = now.astimezone(KST)
        month_start = datetime.combine(
            local.date().replace(day=1),
            time.min,
            tzinfo=KST,
        )

        def day_histogram(start: datetime) -> dict[str, Any]:
            return {
                "field": "@timestamp",
                "calendar_interval": "day",
                "time_zone": "Asia/Seoul",
                "format": "yyyy-MM-dd",
                "min_doc_count": 0,
                "extended_bounds": {
                    "min": start.date().isoformat(),
                    "max": local.date().isoformat(),
                },
            }

        daily_histogram = day_histogram(day_30)
        return {
            "size": 0,
            "track_total_hits": True,
            "query": {"bool": {"filter": _activity_filters(user_id)}},
            "aggs": {
                "visits": {
                    "filter": _kind_window(day_90, now, [RANKING_KIND]),
                    "aggs": {"days": {"date_histogram": day_histogram(day_90)}},
                },
                # Deliberately NOT kind-filtered. "When did we first/last see
                # this person" is a presence question, not a request-volume
                # one, so page views count. Some pages (mag-pixel) issue no
                # API calls at all; a user who only opens those would
                # otherwise show a null last_seen while ranking in the page
                # list.
                "first_seen": {"min": {"field": "@timestamp"}},
                "last_seen": {"max": {"field": "@timestamp"}},
                "this_month": {
                    "filter": _kind_window(month_start, now, REQUEST_KINDS),
                    "aggs": {
                        "days": {
                            "date_histogram": {
                                "field": "@timestamp",
                                "calendar_interval": "day",
                                "time_zone": "Asia/Seoul",
                                "format": "yyyy-MM-dd",
                            }
                        }
                    },
                },
                "daily": {
                    "filter": _kind_window(day_30, now, REQUEST_KINDS),
                    "aggs": {
                        "days": {
                            "date_histogram": daily_histogram,
                            "aggs": {
                                # What was called that day. Narrowed to the
                                # feature kind inside a bucket the entry kind
                                # also counts toward, so these deliberately do
                                # not sum to the bar — entry traffic belongs
                                # to no feature. DailyCount says so.
                                "features": {
                                    "filter": {
                                        "term": {
                                            "activity_kind": FEATURE_KIND
                                        }
                                    },
                                    "aggs": {
                                        "items": _top_features_agg()
                                    },
                                }
                            },
                        }
                    },
                },
                "features": {
                    "filter": {"term": {"activity_kind": RANKING_KIND}},
                    "aggs": {
                        "items": _recent_feature_agg(RECENT_FEATURES_CAP)
                    },
                },
            },
        }

    def _history(
        self,
        user_id: str,
    ) -> tuple[int, dict[str, Any]]:
        now = self._now()
        response = self._search(self._history_query(user_id, now))
        total = _hits_total(response)
        aggregations = response.get("aggregations", {})
        day_30 = _kst_day_start(now, 29).date()
        by_day = _day_buckets(aggregations.get("daily", {}))
        daily: list[DailyCount] = []
        for offset in range(30):
            day = (day_30 + timedelta(days=offset)).isoformat()
            bucket = by_day.get(day, {})
            # NOT `total` — that name already holds the hits count this
            # function returns alongside the payload.
            day_total = int(bucket.get("doc_count", 0))
            features = bucket.get("features", {})
            daily.append(
                {
                    "date": day,
                    "count": day_total,
                    "features": _feature_rows(features.get("items", {})),
                    # The filter agg's own doc_count, not a subtraction from
                    # the capped bucket list: a day with more distinct
                    # features than the cap must still report entry traffic
                    # honestly rather than folding the dropped ones into it.
                    "other_count": day_total
                    - int(features.get("doc_count", 0)),
                }
            )
        this_month = aggregations.get("this_month", {})
        active_days = sum(
            1
            for bucket in this_month.get("days", {}).get("buckets", [])
            if int(bucket.get("doc_count", 0)) > 0
        )
        features = aggregations.get("features", {}).get("items", {})

        def metric(name: str) -> str | None:
            node = aggregations.get(name, {})
            if node.get("value") is None:
                return None
            return node.get("value_as_string")

        return total, {
            "user_id": user_id,
            "this_month": {
                "requests": int(this_month.get("doc_count", 0)),
                "days_active": active_days,
            },
            "recent_features": _recent_feature_rows(features),
            "daily": daily,
            "visits": [
                {"date": day, "count": int(bucket.get("doc_count", 0))}
                for day, bucket in _day_buckets(aggregations.get("visits", {})).items()
            ],
            "first_seen": metric("first_seen"),
            "last_seen": metric("last_seen"),
        }

    def get_me(self, user_id: str) -> MeResponse:
        _total, history = self._history(user_id)
        return {
            "user_id": user_id,
            "is_admin": self._admin_check(user_id),
            "this_month": history["this_month"],
            "recent_features": history["recent_features"],
            "daily": history["daily"],
            "visits": history["visits"],
            "first_seen": history["first_seen"],
            "last_seen": history["last_seen"],
        }

    def get_user_history(
        self,
        user_id: str,
    ) -> UserHistoryResponse | None:
        total, history = self._history(user_id)
        if total == 0:
            return None
        return history  # type: ignore[return-value]

    def get_summary(self) -> SummaryResponse:
        now = self._now()
        day_1 = _kst_day_start(now, 0)
        day_7 = _kst_day_start(now, 6)
        day_30 = _kst_day_start(now, 29)

        def user_window(start: datetime) -> dict[str, Any]:
            return {
                "filter": _kind_window(start, now, REQUEST_KINDS),
                "aggs": {
                    "users": _distinct_users_agg()
                },
            }

        def feature_window(start: datetime) -> dict[str, Any]:
            return {
                "filter": _kind_window(start, now, [RANKING_KIND]),
                "aggs": {
                    "items": _top_features_agg()
                },
            }

        response = self._search(
            {
                "size": 0,
                "query": {"bool": {"filter": _activity_filters()}},
                "aggs": {
                    "dau": user_window(day_1),
                    "wau": user_window(day_7),
                    "mau": user_window(day_30),
                    "top_features_7d": feature_window(day_7),
                    "top_features_30d": feature_window(day_30),
                },
            }
        )
        aggregations = response.get("aggregations", {})
        return {
            "generated_at": _iso_utc(now),
            "dau": int(aggregations.get("dau", {}).get("users", {}).get("value", 0)),
            "wau": int(aggregations.get("wau", {}).get("users", {}).get("value", 0)),
            "mau": int(aggregations.get("mau", {}).get("users", {}).get("value", 0)),
            "top_features_7d": _feature_rows(
                aggregations.get("top_features_7d", {}).get("items", {})
            ),
            "top_features_30d": _feature_rows(
                aggregations.get("top_features_30d", {}).get("items", {})
            ),
        }

    def get_daily_visitors(self) -> VisitorsResponse:
        """DAU with rolling WAU and MAU, one row per KST day.

        Reads each person's active days rather than a per-day cardinality:
        OpenSearch has no rolling distinct count, and a weekly user is not a
        sum of daily ones. ``daily_visitor_rows`` does the counting, the same
        function the mock calls.
        """
        now = self._now()
        start = _kst_day_start(now, VISITOR_LOOKBACK_DAYS - 1)
        active_days: list[list[date]] = []
        after_key: dict[str, Any] | None = None

        while True:
            composite: dict[str, Any] = {
                "size": VISITOR_PAGE_SIZE,
                "sources": [
                    {"user_id": {"terms": {"field": "user_id"}}},
                ],
            }
            if after_key is not None:
                composite["after"] = after_key
            response = self._search(
                {
                    "size": 0,
                    "query": {
                        "bool": {
                            "filter": [
                                # Narrowed for the whole query, as in
                                # _fab_window: the summary cards count request
                                # rows, so admitting page views here would
                                # make today's row disagree with them.
                                *_activity_filters(kinds=REQUEST_KINDS),
                                _time_range(start, now),
                            ]
                        }
                    },
                    "aggs": {
                        "users": {
                            "composite": composite,
                            "aggs": {
                                "days": {
                                    "date_histogram": {
                                        "field": "@timestamp",
                                        "calendar_interval": "day",
                                        "time_zone": "Asia/Seoul",
                                        "format": "yyyy-MM-dd",
                                        # Only the days someone came: the
                                        # default 0 pads every gap between two
                                        # visits with an empty bucket, which
                                        # is most of the response.
                                        "min_doc_count": 1,
                                    }
                                }
                            },
                        }
                    },
                }
            )
            users = response.get("aggregations", {}).get("users", {})
            for bucket in users.get("buckets", []):
                active_days.append(
                    [
                        date.fromisoformat(day)
                        for day, day_bucket in _day_buckets(bucket).items()
                        # Still checked: min_doc_count is a request, and a
                        # padded bucket read as a visit would inflate all
                        # three series.
                        if int(day_bucket.get("doc_count", 0)) > 0
                    ]
                )
            after_key = users.get("after_key")
            if not after_key:
                break

        return {
            "generated_at": _iso_utc(now),
            "days": daily_visitor_rows(
                active_days, now.astimezone(KST).date()
            ),
        }

    def get_users_list(self) -> UserListResponse:
        now = self._now()
        day_30 = _kst_day_start(now, 29)
        rows: list[UserListRow] = []
        after_key: dict[str, Any] | None = None

        while True:
            composite: dict[str, Any] = {
                "size": COMPOSITE_PAGE_SIZE,
                "sources": [
                    {"user_id": {"terms": {"field": "user_id"}}},
                ],
            }
            if after_key is not None:
                composite["after"] = after_key
            response = self._search(
                {
                    "size": 0,
                    "query": {
                        "bool": {
                            "filter": [
                                *_activity_filters(),
                                _time_range(day_30, now),
                            ]
                        }
                    },
                    "aggs": {
                        "users": {
                            # A composite agg may not be nested under a filter
                            # agg, so the kind split happens per user bucket:
                            # requests_only holds everything that COUNTS.
                            "composite": composite,
                            "aggs": {
                                "requests_only": {
                                    "filter": {
                                        "terms": {
                                            "activity_kind": REQUEST_KINDS
                                        }
                                    },
                                    "aggs": {
                                        "days": {
                                            "date_histogram": {
                                                "field": "@timestamp",
                                                "calendar_interval": "day",
                                                "time_zone": "Asia/Seoul",
                                            }
                                        }
                                    },
                                },
                                # Deliberately NOT kind-filtered: last_seen is
                                # a presence signal, so a page open counts as
                                # having seen the user even though it is not
                                # a request.
                                "last_seen": {
                                    "max": {"field": "@timestamp"}
                                },
                                "feature_only": {
                                    "filter": {
                                        "term": {
                                            "activity_kind": RANKING_KIND
                                        }
                                    },
                                    "aggs": {
                                        "recent": _recent_feature_agg(1)
                                    },
                                },
                            },
                        }
                    },
                }
            )
            users = response.get("aggregations", {}).get("users", {})
            for bucket in users.get("buckets", []):
                requests_only = bucket.get("requests_only", {})
                requests = int(requests_only.get("doc_count", 0))
                if requests <= 0:
                    continue
                recent = (
                    bucket.get("feature_only", {})
                    .get("recent", {})
                    .get("buckets", [])
                )
                rows.append(
                    {
                        "user_id": str(
                            bucket.get("key", {}).get("user_id", "")
                        ),
                        "requests_30d": requests,
                        "days_active_30d": sum(
                            1
                            for day in requests_only.get("days", {}).get(
                                "buckets",
                                [],
                            )
                            if int(day.get("doc_count", 0)) > 0
                        ),
                        "last_seen": bucket.get("last_seen", {}).get(
                            "value_as_string"
                        ),
                        "recent_feature": (
                            str(recent[0].get("key")) if recent else None
                        ),
                    }
                )
            after_key = users.get("after_key")
            if not after_key:
                break

        rows.sort(key=lambda row: (-row["requests_30d"], row["user_id"]))
        return {"generated_at": _iso_utc(now), "users": rows}

    def _fab_window(
        self,
        now: datetime,
        start: datetime,
    ) -> list[FabUsageRow]:
        rows: list[FabUsageRow] = []
        after_key: dict[str, Any] | None = None

        while True:
            composite: dict[str, Any] = {
                "size": COMPOSITE_PAGE_SIZE,
                "sources": [
                    {
                        "fab": {
                            "terms": {
                                "field": "fab_name_list",
                                "missing_bucket": True,
                                "missing_order": "last",
                            }
                        }
                    }
                ],
            }
            if after_key is not None:
                composite["after"] = after_key
            response = self._search(
                {
                    "size": 0,
                    "query": {
                        "bool": {
                            "filter": [
                                # Narrowed for the WHOLE fab query: no
                                # aggregation here wants page views, and a
                                # beacon carries no fab_name, so admitting one
                                # would invent a "미지정" fab bucket and count
                                # its opener as an active user of a fab they
                                # never selected.
                                *_activity_filters(kinds=REQUEST_KINDS),
                                _time_range(start, now),
                            ]
                        }
                    },
                    "aggs": {
                        "fabs": {
                            "composite": composite,
                            "aggs": {
                                "active_users": _distinct_users_agg(),
                                "feature_only": {
                                    "filter": {
                                        "term": {
                                            # Stays request-based: beacons
                                            # carry no fab_name (it is only
                                            # known once the user has picked a
                                            # fab and a data request goes
                                            # out), so page views cannot
                                            # answer a per-FAB question.
                                            "activity_kind": FEATURE_KIND
                                        }
                                    },
                                    "aggs": {
                                        "pages": _top_features_agg()
                                    },
                                },
                            },
                        }
                    },
                }
            )
            fabs = response.get("aggregations", {}).get("fabs", {})
            for bucket in fabs.get("buckets", []):
                raw_fab = bucket.get("key", {}).get("fab")
                rows.append(
                    {
                        "fab": (
                            str(raw_fab) if raw_fab not in (None, "") else "미지정"
                        ),
                        "total": int(bucket.get("active_users", {}).get("value", 0)),
                        "pages": _feature_rows(
                            bucket.get("feature_only", {}).get("pages", {})
                        ),
                    }
                )
            after_key = fabs.get("after_key")
            if not after_key:
                break

        rows.sort(key=lambda row: (-row["total"], row["fab"]))
        return rows

    def get_fab_page_usage(self) -> FabUsageResponse:
        now = self._now()
        return {
            "generated_at": _iso_utc(now),
            "fabs_7d": self._fab_window(
                now,
                _kst_day_start(now, 6),
            ),
            "fabs_30d": self._fab_window(
                now,
                _kst_day_start(now, 29),
            ),
        }

    def get_family_page_usage(self) -> FamilyUsageResponse:
        """Page opens per tool family over the last 7 and 30 KST days.

        One request: the vocabulary is five values, so a plain ``terms`` holds
        every family and no composite paging is needed.

        There is no family field in the index. A page open is posted to
        /api/page-view/<family>, so the family is the row's ``path`` — a
        keyword that has been mapped from the start — and grouping on it needs
        no change to the index.
        """
        now = self._now()
        day_30 = _kst_day_start(now, 29)

        def window(start: datetime) -> dict[str, Any]:
            return {
                "filter": _time_range(start, now),
                "aggs": {
                    "families": {
                        "terms": {
                            "field": "path",
                            "size": len(FAMILY_BY_BEACON_PATH),
                            # Exact URLs only. The plain /api/page-view is a
                            # page with no family and is not a row; anything
                            # else under it is not a sixth family.
                            "include": list(FAMILY_BY_BEACON_PATH),
                        },
                        "aggs": {
                            "openers": _distinct_users_agg(),
                            "pages": _top_features_agg(),
                        },
                    }
                },
            }

        def rows(node: dict[str, Any]) -> list[FamilyUsageRow]:
            # Page opens from before the family URLs existed were all posted
            # to the plain path and so fall in no bucket — see MIGRATION.md.
            buckets = {
                FAMILY_BY_BEACON_PATH[key]: bucket
                for bucket in node.get("families", {}).get("buckets", [])
                if (key := str(bucket.get("key"))) in FAMILY_BY_BEACON_PATH
            }
            return family_usage_rows(
                {
                    family: int(bucket.get("openers", {}).get("value", 0))
                    for family, bucket in buckets.items()
                },
                {
                    family: _feature_rows(bucket.get("pages", {}))
                    for family, bucket in buckets.items()
                },
            )

        response = self._search(
            {
                "size": 0,
                "query": {
                    "bool": {
                        "filter": [
                            # Page opens only, stated once for the whole
                            # query, and bounded to the wider window: the
                            # alias holds up to a year, and matching all of it
                            # only for the two windows to discard most of it
                            # is work that grows with retention.
                            *_activity_filters(kinds=[RANKING_KIND]),
                            _time_range(day_30, now),
                        ]
                    }
                },
                "aggs": {
                    "families_7d": window(_kst_day_start(now, 6)),
                    "families_30d": window(day_30),
                },
            }
        )
        aggregations = response.get("aggregations", {})
        return {
            "generated_at": _iso_utc(now),
            "families_7d": rows(aggregations.get("families_7d", {})),
            "families_30d": rows(aggregations.get("families_30d", {})),
        }
