"""Mock-adapter internals that the contract gate cannot see."""

from datetime import date, datetime, timedelta, timezone

import pytest

from back_dev_home.activity.providers import mock


@pytest.fixture
def fresh_store(monkeypatch):
    store: dict[str, mock._UserState] = {}
    monkeypatch.setattr(mock, "_users", store)
    return store


@pytest.fixture
def reset_state(monkeypatch):
    """Like fresh_store, but for tests that read back through get_me /
    get_fab_page_usage rather than poking _UserState directly."""
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
    assert state.by_feature == {}
    assert state.daily_features == {}


def test_non_activity_kinds_are_ignored(fresh_store):
    mock.record_request("u1", "sem_list", "background", ["M14"])

    assert fresh_store == {}


def test_rankings_come_from_page_views_not_requests(reset_state):
    """A poller must not outrank a page someone actually opened."""
    for _ in range(50):
        mock.record_request("u1", "live_alarm", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", [])

    top = mock.get_me("u1")["top_features"]

    assert [row["feature"] for row in top] == ["mag_pixel"]


def test_page_views_do_not_inflate_the_request_counters(reset_state):
    """this_month.requests and the sparkline stay request-based by decision."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", [])

    assert mock.get_me("u1")["this_month"]["requests"] == 1


def test_a_page_view_only_user_still_has_a_last_seen(reset_state):
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


def test_fab_page_rankings_stay_request_based(reset_state):
    """Beacons carry no fab_name, so FAB pages must keep counting requests."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", ["M14"])

    fabs = {row["fab"]: row for row in mock.get_fab_page_usage()["fabs_30d"]}

    assert [row["feature"] for row in fabs["M14"]["pages"]] == ["storage"]
