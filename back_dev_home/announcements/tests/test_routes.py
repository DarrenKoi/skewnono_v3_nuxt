"""Route-level gate for announcements. Runs against the ACTIVE provider.

The SPA fetches GET /api/announcements on every page load and routes.py has no
try/except, so what is worth pinning through the HTTP hop is that a 200 carries
the contract shape, and that a malformed row degrades to "that row skipped"
rather than a 500 on every page.

The malformed-row test drives the mock's JSON file, so it is fenced behind
get_data_provider("announcements") == "mock" — the office run answers from Redis
and would never see what this test wrote. The same tolerance is pinned
office-side, against an injected fake, in test_office_template.py.
"""

import json

import pytest

from back_dev_home import create_app
from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.announcements.contracts import AnnouncementsResponse
from back_dev_home.announcements.providers import mock

ROW = {
    "id": "2026-07-31-notice",
    "level": "info",
    "title": "정기 점검 안내",
    "body": "07-31 02:00~04:00 사이 조회가 지연될 수 있습니다.",
}

mock_only = pytest.mark.skipif(
    get_data_provider("announcements") != "mock",
    reason="drives the mock's announcements.json; office answers from Redis",
)


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _serve_from_file(monkeypatch, tmp_path, rows):
    """Point the mock at a temp announcements.json holding ``rows``.

    ``_cache`` is monkeypatched as well as ``_PATH``: it is a module global
    keyed on mtime, so replacing it (rather than mutating it) is what keeps
    these rows from leaking into later tests once it is restored.
    """
    path = tmp_path / "announcements.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(mock, "_PATH", path)
    monkeypatch.setattr(mock, "_cache", {"mtime": 0.0, "items": []})


def test_get_announcements_is_200_with_the_contract_shape():
    response = _client().get("/api/announcements")

    assert response.status_code == 200
    assert_matches(response.get_json(), AnnouncementsResponse)
    # Deliberately no assertion on the row COUNT. The shipped
    # announcements.json is empty and operators add a row only when there is
    # something to post, so both `[]` and a live banner are correct here —
    # pinning either would make a routine operator edit fail the suite. That
    # the file is actually read is pinned below, against a temp file.


@mock_only
def test_a_non_dict_row_in_the_file_is_skipped_not_a_500(monkeypatch, tmp_path):
    """A bare string from a bad hand edit must not take the SPA down."""
    _serve_from_file(monkeypatch, tmp_path, ["oops", 42, None, ROW])

    response = _client().get("/api/announcements")

    assert response.status_code == 200
    assert response.get_json() == [ROW]
