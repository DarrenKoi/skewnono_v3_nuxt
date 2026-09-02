"""Mock-adapter internals that the contract gate cannot see."""

from datetime import date, datetime, timedelta, timezone

import pytest

from back_dev_home.activity.providers import mock


@pytest.fixture
def fresh_store(monkeypatch):
    store: dict[str, mock._UserState] = {}
    monkeypatch.setattr(mock, "_users", store)
    return store


def test_record_request_trims_day_buckets_to_the_read_window(fresh_store):
    """Per-user daily dicts must stay bounded: a long-lived dev server would
    otherwise accumulate one entry per day forever."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    state = fresh_store["u1"]
    stale = mock._today() - timedelta(days=90)
    state.daily[stale] = 5
    state.daily_features[stale] = {"storage": 5}
    state.daily_fabs[stale] = {"M14"}
    state.daily_fab_features[stale] = {"M14": {"storage": 5}}

    mock.record_request("u1", "storage", "feature", ["M14"])

    for bucket in (
        state.daily,
        state.daily_features,
        state.daily_fabs,
        state.daily_fab_features,
    ):
        assert stale not in bucket
    assert state.daily[mock._today()] == 2


def test_record_request_keeps_the_whole_current_month(monkeypatch, fresh_store):
    """this_month reaches one day beyond the 30-day sparkline window on the
    31st of a 31-day month, so trimming must not use the sparkline cutoff
    alone. The clock is pinned because that is the only shape of date where
    ``month_first < today - 29`` — run on any other day this assertion would
    pass against a cutoff that is in fact too aggressive.

    ``record_request`` derives its own day from ``_now()``, so that is what
    gets patched; patching ``_today`` would not reach it.
    """
    # 12:00 KST on 2026-07-31, a 31-day month.
    monkeypatch.setattr(
        mock, "_now", lambda: datetime(2026, 7, 31, 3, 0, tzinfo=timezone.utc)
    )
    day_31 = date(2026, 7, 31)
    month_first = date(2026, 7, 1)
    assert month_first < day_31 - timedelta(days=29), "pinned date lost its point"

    mock.record_request("u1", "storage", "feature", ["M14"])
    state = fresh_store["u1"]
    state.daily[month_first] = 3
    state.daily_features[month_first] = {"storage": 3}

    mock.record_request("u1", "storage", "feature", ["M14"])

    assert state.daily[month_first] == 3
    assert state.daily_features[month_first] == {"storage": 3}
    assert state.daily[day_31] == 2


def test_entry_requests_count_activity_but_not_feature_rankings(fresh_store):
    mock.record_request("u1", "sem_list", "entry", ["M14"])
    state = fresh_store["u1"]

    assert state.daily[mock._today()] == 1
    assert state.last_opened == {}
    assert state.daily_features == {}


def test_non_activity_kinds_are_ignored(fresh_store):
    mock.record_request("u1", "sem_list", "background", ["M14"])

    assert fresh_store == {}


def test_recent_features_come_from_page_views_not_requests(fresh_store):
    """A poller must not outrank a page someone actually opened."""
    for _ in range(50):
        mock.record_request("u1", "live_alarm", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", [])

    recent = mock.get_me("u1")["recent_features"]

    assert [row["feature"] for row in recent] == ["mag_pixel"]


def test_recent_features_are_distinct_newest_first_and_capped(fresh_store):
    """Five features, not five opens: re-opening one must not fill the list."""
    for feature in ("storage", "sem_list", "afm", "chat", "meas_hist"):
        mock.record_request("u1", feature, "page_view", [])
    for _ in range(5):
        mock.record_request("u1", "storage", "page_view", [])
    mock.record_request("u1", "recipe_tat", "page_view", [])

    recent = mock.get_me("u1")["recent_features"]

    assert [row["feature"] for row in recent] == [
        "recipe_tat",
        "storage",
        "meas_hist",
        "chat",
        "afm",
    ]
    assert all(row["at"].endswith("Z") for row in recent)


def test_the_users_list_names_the_most_recent_feature(fresh_store):
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "storage", "page_view", [])
    mock.record_request("u1", "afm", "page_view", [])

    assert mock.get_users_list()["users"][0]["recent_feature"] == "afm"


def test_each_day_carries_what_was_called_that_day(fresh_store):
    """The clickable bar and its breakdown are read from the same rows."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "afm", "feature", ["M16B"])
    mock.record_request("u1", "sem_list", "entry", ["M14"])

    today = mock.get_me("u1")["daily"][-1]

    assert today["count"] == 4
    assert today["features"] == [
        {"feature": "storage", "count": 2},
        {"feature": "afm", "count": 1},
    ]
    # Entry traffic belongs to no feature, and the payload names the gap
    # rather than leaving the caller to subtract it.
    assert today["other_count"] == 1


def test_a_multi_fab_request_counts_once_in_the_day_breakdown(fresh_store):
    """The FAB card counts a request once per FAB; this panel must not.

    Deriving the breakdown from daily_fab_features would report 2 here while
    the office reader, which counts documents, reports 1 — home and office on
    different numbers for one field.
    """
    mock.record_request("u1", "storage", "feature", ["M14", "M16B"])

    today = mock.get_me("u1")["daily"][-1]

    assert today["count"] == 1
    assert today["features"] == [{"feature": "storage", "count": 1}]
    assert today["other_count"] == 0


def test_page_views_do_not_inflate_the_request_counters(fresh_store):
    """this_month.requests and the sparkline stay request-based by decision."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", [])

    assert mock.get_me("u1")["this_month"]["requests"] == 1


def test_a_page_view_only_user_still_has_a_last_seen(fresh_store):
    """Presence, not volume: mag_pixel issues no API calls at all, so a user
    who only opens it would otherwise read as never-seen while ranking in the
    page list."""
    mock.record_request("u1", "mag_pixel", "page_view", [])

    payload = mock.get_me("u1")

    assert payload["last_seen"] is not None
    assert payload["first_seen"] is not None
    # ...while the counters it must not touch stay at zero.
    assert payload["this_month"]["requests"] == 0
    assert all(day["count"] == 0 for day in payload["daily"])
    assert mock.get_fab_page_usage()["fabs_30d"] == []


def test_fab_page_rankings_stay_request_based(fresh_store):
    """Beacons carry no fab_name, so FAB pages must keep counting requests."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", ["M14"])

    fabs = {row["fab"]: row for row in mock.get_fab_page_usage()["fabs_30d"]}

    assert [row["feature"] for row in fabs["M14"]["pages"]] == ["storage"]
