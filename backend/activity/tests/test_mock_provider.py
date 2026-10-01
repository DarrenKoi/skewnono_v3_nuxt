"""Mock-adapter internals that the contract gate cannot see."""

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.activity.providers import mock


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


def test_visit_calendar_keeps_90_days_of_page_views_separate_from_requests(
    fresh_store, monkeypatch
):
    monkeypatch.setattr(
        mock, "_now", lambda: datetime(2026, 9, 11, 16, tzinfo=timezone.utc)
    )
    mock.record_request("u1", "mag_pixel", "page_view", [])
    mock.record_request("u1", "storage", "feature", [])
    state = fresh_store["u1"]
    today = date(2026, 9, 12)
    state.visits[today - timedelta(days=89)] = 2
    state.visits[today - timedelta(days=90)] = 3
    mock.record_request("u1", "mag_pixel", "page_view", [])
    visits = mock.get_me("u1")["visits"]
    assert len(visits) == 90
    assert visits[0]["count"] == 2
    assert visits[-1] == {"date": "2026-09-12", "count": 2}
    assert len(state.visits) == 2
    assert mock.get_me("u1")["daily"][-1]["count"] == 1


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


def test_seeded_home_identity_fills_the_visit_calendar_without_losing_counts(
    fresh_store,
):
    mock.seed_demo_users()

    visits = [day["count"] for day in mock.get_me("local-dev")["visits"]]
    _user, _fab, _requests, page_views, _days = next(
        row for row in mock._DEMO_USERS if row[0] == "local-dev"
    )
    assert sum(visits) == sum(page_views.values())
    assert 0 in visits and len(set(visits)) > 5
    # The weighted spread must not drop or invent requests for any peer.
    for user_id, _fab, requests, _views, days_back in mock._DEMO_USERS:
        if days_back <= mock.SPARKLINE_DAYS:
            assert sum(fresh_store[user_id].daily.values()) == sum(requests.values())


def test_daily_visitors_roll_dau_wau_mau_over_60_kst_days(
    fresh_store, monkeypatch
):
    # 2026-09-12 01:00 KST — still the 11th in UTC, so a UTC calendar would
    # put today's visitors on the wrong day.
    monkeypatch.setattr(
        mock, "_now", lambda: datetime(2026, 9, 11, 16, tzinfo=timezone.utc)
    )
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u2", "sem_list", "entry", [])
    u1, u2 = fresh_store["u1"], fresh_store["u2"]
    u1.daily[date(2026, 7, 15)] = 4  # 59 days back: the chart's first day
    u1.daily[date(2026, 6, 15)] = 9  # 89 days back: no window reaches it
    # 88 days back: off the chart, but inside the first day's 30-day MAU
    # window (06-16..07-15), so it has to survive the prune.
    u2.daily[date(2026, 6, 16)] = 1
    # Three requests from one person are one visitor, not three.
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u2", "sem_list", "entry", [])
    # A page open alone is not a visitor: the DAU card counts request rows,
    # and today's bar has to agree with it.
    mock.record_request("u3", "mag_pixel", "page_view", [])

    days = mock.get_daily_visitors()["days"]

    assert len(days) == 60
    assert days[0] == {"date": "2026-07-15", "visitors": 1, "wau": 1, "mau": 2}
    # u2's 06-16 has left the 30-day window; u1's 07-15 is still in both.
    assert days[1] == {"date": "2026-07-16", "visitors": 0, "wau": 1, "mau": 1}
    # 07-15 is the 7th day back from 07-21 and the 8th from 07-22.
    assert days[6] == {"date": "2026-07-21", "visitors": 0, "wau": 1, "mau": 1}
    assert days[7] == {"date": "2026-07-22", "visitors": 0, "wau": 0, "mau": 1}
    # ...and the 30th day back from 08-13, the 31st from 08-14.
    assert days[29] == {"date": "2026-08-13", "visitors": 0, "wau": 0, "mau": 1}
    assert days[30] == {"date": "2026-08-14", "visitors": 0, "wau": 0, "mau": 0}
    assert days[-2] == {"date": "2026-09-11", "visitors": 0, "wau": 0, "mau": 0}
    assert days[-1] == {"date": "2026-09-12", "visitors": 2, "wau": 2, "mau": 2}
    summary = mock.get_summary()
    assert (summary["dau"], summary["wau"], summary["mau"]) == (2, 2, 2)
    assert date(2026, 6, 15) not in u1.daily
    assert date(2026, 6, 16) in u2.daily


def _family_rows(payload, window):
    return {row["family"]: row for row in payload[window]}


def test_family_usage_counts_people_and_page_opens_per_family(fresh_store):
    mock.record_request("u1", "storage", "page_view", [], "cdsem")
    mock.record_request("u1", "storage", "page_view", [], "cdsem")
    mock.record_request("u2", "storage", "page_view", [], "cdsem")
    mock.record_request("u2", "hardware", "page_view", [], "hvsem")
    mock.record_request("u2", "afm", "page_view", [], "afm")
    # Neither of these is a page of a family: a page that belongs to none,
    # and a REQUEST that happens to carry one. The card counts page opens.
    mock.record_request("u3", "mag_pixel", "page_view", [], None)
    mock.record_request("u3", "storage", "feature", ["M14"], "cdsem")

    payload = mock.get_family_page_usage()

    # Every family is listed, in registry order, whether or not anyone came:
    # VeritySEM and Provision have no pages yet and must still read as 0.
    assert payload["families_7d"] == [
        {
            "family": "cdsem",
            "total": 2,
            "pages": [{"feature": "storage", "count": 3}],
        },
        {
            "family": "hvsem",
            "total": 1,
            "pages": [{"feature": "hardware", "count": 1}],
        },
        {"family": "veritysem", "total": 0, "pages": []},
        {"family": "provision", "total": 0, "pages": []},
        {"family": "afm", "total": 1, "pages": [{"feature": "afm", "count": 1}]},
    ]
    assert payload["families_30d"] == payload["families_7d"]


def test_family_usage_windows_are_7_and_30_kst_days_and_stay_bounded(
    fresh_store, monkeypatch
):
    monkeypatch.setattr(
        mock, "_now", lambda: datetime(2026, 9, 11, 16, tzinfo=timezone.utc)
    )
    today = date(2026, 9, 12)
    mock.record_request("u1", "storage", "page_view", [], "cdsem")
    state = fresh_store["u1"]
    state.daily_family_features[today - timedelta(days=6)] = {
        "hvsem": {"hardware": 2}
    }
    state.daily_family_features[today - timedelta(days=7)] = {
        "afm": {"afm": 5}
    }
    state.daily_family_features[today - timedelta(days=200)] = {
        "afm": {"afm": 9}
    }
    mock.record_request("u1", "storage", "page_view", [], "cdsem")

    payload = mock.get_family_page_usage()
    week = _family_rows(payload, "families_7d")
    month = _family_rows(payload, "families_30d")

    assert week["cdsem"]["pages"] == [{"feature": "storage", "count": 2}]
    assert week["hvsem"]["total"] == 1  # 6 days back: the week's first day
    assert week["afm"]["total"] == 0  # 7 days back: outside it
    assert month["afm"]["pages"] == [{"feature": "afm", "count": 5}]
    assert today - timedelta(days=200) not in state.daily_family_features


def test_seeded_demo_users_open_pages_in_more_than_one_family(fresh_store):
    """The card is unreadable at home if every demo user lives in one family."""
    mock.seed_demo_users()

    month = _family_rows(mock.get_family_page_usage(), "families_30d")

    assert month["cdsem"]["total"] > 0
    assert month["hvsem"]["total"] > 0
    assert month["afm"]["total"] > 0
    # Not built yet, and the mock must not pretend otherwise.
    assert month["veritysem"] == {"family": "veritysem", "total": 0, "pages": []}
    assert month["provision"] == {"family": "provision", "total": 0, "pages": []}
    # A page that belongs to no family never shows up under one.
    listed = {
        page["feature"] for row in month.values() for page in row["pages"]
    }
    assert "mag_pixel" not in listed and "chat" not in listed
