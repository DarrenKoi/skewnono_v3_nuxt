"""Anonymous callers share an ID, so none of their usage is attributable."""

from copy import deepcopy

from backend.activity.providers import mock
from backend.activity.providers.opensearch_reader import _activity_filters


def test_legacy_anonymous_state_is_excluded_from_every_mock_view(monkeypatch):
    store = {}
    monkeypatch.setattr(mock, "_users", store)
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "storage", "page_view", [], "/api/page-view/cdsem")
    views = (
        mock.get_summary,
        mock.get_users_list,
        mock.get_daily_visitors,
        mock.get_fab_page_usage,
        mock.get_family_page_usage,
    )
    expected = [view() for view in views]
    legacy = deepcopy(store["u1"])
    legacy.user_id = "anonymous"
    store["anonymous"] = legacy

    for view, before in zip(views, expected, strict=True):
        after = view()
        after.pop("generated_at")
        before.pop("generated_at")
        assert after == before
    assert mock.get_user_history("anonymous") is None
    me = mock.get_me("anonymous")
    assert me["this_month"] == {"requests": 0, "days_active": 0}
    assert me["recent_features"] == []
    assert all(day["count"] == 0 for day in me["daily"] + me["visits"])
    assert me["first_seen"] is None and me["last_seen"] is None


def test_anonymous_events_never_enter_the_mock_store(monkeypatch):
    store = {}
    monkeypatch.setattr(mock, "_users", store)
    for kind in ("entry", "feature", "page_view"):
        mock.record_request("anonymous", "storage", kind, ["M14"])
    assert store == {}


def test_every_office_query_excludes_anonymous_source_and_legacy_id():
    # All office views share this top-level filter. Missing identity_source
    # on older documents must still exclude the shared anonymous ID.
    for user_id in (None, "u1", "anonymous"):
        assert {
            "bool": {
                "must_not": [
                    {"term": {"identity_source": "anonymous"}},
                    {"term": {"user_id": "anonymous"}},
                ]
            }
        } in _activity_filters(user_id)
