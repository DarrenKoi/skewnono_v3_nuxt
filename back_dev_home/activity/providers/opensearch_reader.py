"""Aggregate canonical request documents for the activity APIs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from typing import Any

from back_dev_home._auth.admin import is_admin
from back_dev_home._logging.target import resolve_logging_target
from back_dev_home.activity.contracts import (
    DailyCount,
    FabUsageResponse,
    FabUsageRow,
    FeatureCount,
    MeResponse,
    SummaryResponse,
    UserHistoryResponse,
    UserListResponse,
    UserListRow,
)
from back_dev_home.activity.providers.shared import KST, TOP_FEATURES_CAP

COMPOSITE_PAGE_SIZE = 1000
CARDINALITY_PRECISION = 40000

# Two units share one index. Request rows answer "how much work happened";
# page_view rows answer "which page did people open". Every aggregation must
# say which it means — see the beacon design spec.
REQUEST_KINDS = ["entry", "feature"]
RANKING_KIND = "page_view"
ALL_KINDS = [*REQUEST_KINDS, RANKING_KIND]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _kst_day_start(now: datetime, days_ago: int) -> datetime:
    local = now.astimezone(KST)
    day = local.date() - timedelta(days=days_ago)
    return datetime.combine(day, time.min, tzinfo=KST)


def _kind_window(
    start: datetime,
    now: datetime,
    kinds: list[str],
) -> dict[str, Any]:
    return {
        "bool": {
            "filter": [
                {
                    "range": {
                        "@timestamp": {
                            "gte": start.isoformat(),
                            "lte": now.isoformat(),
                        }
                    }
                },
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
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _feature_rows(node: dict[str, Any]) -> list[FeatureCount]:
    return [
        {
            "feature": str(bucket.get("key", "")),
            "count": int(bucket.get("doc_count", 0)),
        }
        for bucket in node.get("buckets", [])
        if bucket.get("key") not in (None, "")
    ]


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
        return self._search_service.search_raw(body)

    def _history_query(
        self,
        user_id: str,
        now: datetime,
    ) -> dict[str, Any]:
        day_30 = _kst_day_start(now, 29)
        local = now.astimezone(KST)
        month_start = datetime.combine(
            local.date().replace(day=1),
            time.min,
            tzinfo=KST,
        )
        daily_histogram = {
            "field": "@timestamp",
            "calendar_interval": "day",
            "time_zone": "Asia/Seoul",
            "format": "yyyy-MM-dd",
            "min_doc_count": 0,
            "extended_bounds": {
                "min": day_30.date().isoformat(),
                "max": local.date().isoformat(),
            },
        }
        return {
            "size": 0,
            "track_total_hits": True,
            "query": {"bool": {"filter": _activity_filters(user_id)}},
            "aggs": {
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
                        }
                    },
                },
                "features": {
                    "filter": {"term": {"activity_kind": RANKING_KIND}},
                    "aggs": {
                        "items": {
                            "terms": {
                                "field": "feature",
                                "size": TOP_FEATURES_CAP,
                                "order": {"_count": "desc"},
                            }
                        }
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
        daily_node = aggregations.get("daily", {}).get("days", {})
        counts = {
            str(bucket.get("key_as_string", "")).split("T", 1)[0]: int(
                bucket.get("doc_count", 0)
            )
            for bucket in daily_node.get("buckets", [])
        }
        daily: list[DailyCount] = [
            {
                "date": (day := day_30 + timedelta(days=offset)).isoformat(),
                "count": counts.get(day.isoformat(), 0),
            }
            for offset in range(30)
        ]
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
            "top_features": _feature_rows(features),
            "daily": daily,
            "first_seen": metric("first_seen"),
            "last_seen": metric("last_seen"),
        }

    def get_me(self, user_id: str) -> MeResponse:
        _total, history = self._history(user_id)
        return {
            "user_id": user_id,
            "is_admin": self._admin_check(user_id),
            "this_month": history["this_month"],
            "top_features": history["top_features"],
            "daily": history["daily"],
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
                    "users": {
                        "cardinality": {
                            "field": "user_id",
                            "precision_threshold": CARDINALITY_PRECISION,
                        }
                    }
                },
            }

        def feature_window(start: datetime) -> dict[str, Any]:
            return {
                "filter": _kind_window(start, now, [RANKING_KIND]),
                "aggs": {
                    "items": {
                        "terms": {
                            "field": "feature",
                            "size": TOP_FEATURES_CAP,
                            "order": {"_count": "desc"},
                        }
                    }
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
                                {
                                    "range": {
                                        "@timestamp": {
                                            "gte": day_30.isoformat(),
                                            "lte": now.isoformat(),
                                        }
                                    }
                                },
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
                                        "favorite": {
                                            "terms": {
                                                "field": "feature",
                                                "size": 1,
                                            }
                                        }
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
                favorites = (
                    bucket.get("feature_only", {})
                    .get("favorite", {})
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
                        "favorite_feature": (
                            str(favorites[0].get("key"))
                            if favorites
                            else None
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
                                {
                                    "range": {
                                        "@timestamp": {
                                            "gte": start.isoformat(),
                                            "lte": now.isoformat(),
                                        }
                                    }
                                },
                            ]
                        }
                    },
                    "aggs": {
                        "fabs": {
                            "composite": composite,
                            "aggs": {
                                "active_users": {
                                    "cardinality": {
                                        "field": "user_id",
                                        "precision_threshold": (
                                            CARDINALITY_PRECISION
                                        ),
                                    }
                                },
                                "feature_only": {
                                    "filter": {
                                        "term": {
                                            # Stays request-based: beacons
                                            # carry no fab_name (it is only
                                            # known once the user has picked a
                                            # fab and a data request goes
                                            # out), so page views cannot
                                            # answer a per-FAB question.
                                            "activity_kind": "feature"
                                        }
                                    },
                                    "aggs": {
                                        "pages": {
                                            "terms": {
                                                "field": "feature",
                                                "size": TOP_FEATURES_CAP,
                                                "order": {
                                                    "_count": "desc"
                                                },
                                            }
                                        }
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
                            str(raw_fab)
                            if raw_fab not in (None, "")
                            else "미지정"
                        ),
                        "total": int(
                            bucket.get("active_users", {}).get("value", 0)
                        ),
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
