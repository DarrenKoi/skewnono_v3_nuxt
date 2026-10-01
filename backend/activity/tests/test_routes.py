"""Route-level auth gate: per-employee enumeration is admin-only.

/activity/me, /activity/summary, /activity/fabs and /activity/families stay
open to every identified user (aggregates), while /activity/users, /activity/users/<id> and
/activity/visitors require a trusted admin identity.
"""

import pytest
from flask import Flask, g

from backend._logging.activity import install_activity_logging
from backend.activity import routes
from backend.activity.providers import mock


@pytest.fixture
def make_client(monkeypatch):
    """Client factory with stubbed loaders and a chosen identity."""

    monkeypatch.delenv("SKEWNONO_ADMIN_USERS", raising=False)
    monkeypatch.setattr(routes, "get_me", lambda user_id: {"user_id": user_id})
    monkeypatch.setattr(routes, "get_summary", lambda: {"dau": 0})
    monkeypatch.setattr(routes, "get_fab_page_usage", lambda: {"fabs_7d": []})
    monkeypatch.setattr(
        routes, "get_family_page_usage", lambda: {"families_7d": []}
    )
    monkeypatch.setattr(
        routes,
        "get_users_list",
        lambda: {"generated_at": "2026-08-05T00:00:00+09:00", "users": []},
    )
    monkeypatch.setattr(
        routes, "get_user_history", lambda user_id: {"user_id": user_id}
    )
    monkeypatch.setattr(routes, "get_daily_visitors", lambda: {"days": []})

    def build(user_id, identity_source):
        app = Flask(__name__)

        @app.before_request
        def identity():
            g.user_id = user_id
            g.identity_source = identity_source

        app.register_blueprint(routes.bp, url_prefix="/api")
        return app.test_client()

    return build


@pytest.mark.parametrize(
    "path",
    [
        "/api/activity/users",
        "/api/activity/users/2067928",
        "/api/activity/visitors",
    ],
)
def test_user_enumeration_is_forbidden_for_non_admins(make_client, path):
    client = make_client("1234567", "cookie")

    response = client.get(path)

    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


@pytest.mark.parametrize(
    "path",
    [
        "/api/activity/users",
        "/api/activity/users/2067928",
        "/api/activity/visitors",
    ],
)
def test_user_enumeration_is_allowed_for_the_home_admin(make_client, path):
    # local-dev via the trusted local identity source is home's admin.
    client = make_client("local-dev", "local")

    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/activity/me",
        "/api/activity/summary",
        "/api/activity/fabs",
        "/api/activity/families",
    ],
)
def test_aggregate_views_stay_open_to_normal_users(make_client, path):
    client = make_client("1234567", "cookie")

    assert client.get(path).status_code == 200


# --- the member-directory join on /activity/users ---------------------------
#
# The providers read the logging store, which records employee numbers and no
# names or teams, so both are attached in the route. These cover the answers
# the directory can give for one row: a full row, no row, no directory, and a
# partial row that has one field and not the other.


@pytest.fixture
def users_route(monkeypatch, make_client):
    """An admin client whose users list is two rows with chosen directory answers."""

    def build(members):
        monkeypatch.setattr(
            routes,
            "get_users_list",
            lambda: {
                "generated_at": "2026-08-05T00:00:00+09:00",
                "users": [
                    {
                        "user_id": "2067928",
                        "requests_30d": 9,
                        "days_active_30d": 3,
                        "last_seen": None,
                        "recent_feature": "storage",
                    },
                    {
                        "user_id": "1234567",
                        "requests_30d": 2,
                        "days_active_30d": 1,
                        "last_seen": None,
                        "recent_feature": None,
                    },
                ],
            },
        )
        monkeypatch.setattr(routes, "lookup_members", lambda ids: members)
        return make_client("local-dev", "local")

    return build


def test_listed_users_carry_their_directory_name_and_team(users_route):
    client = users_route(
        {
            "2067928": {
                "empno": "2067928",
                "emp_nm": "고대영",
                "dept_nm": "계측기술팀",
            },
            "1234567": {
                "empno": "1234567",
                "emp_nm": "홍길동",
                "dept_nm": "공정기술팀",
            },
        }
    )

    users = client.get("/api/activity/users").json["users"]

    assert [(row["user_id"], row["emp_nm"], row["dept_nm"]) for row in users] == [
        ("2067928", "고대영", "계측기술팀"),
        ("1234567", "홍길동", "공정기술팀"),
    ]


def test_a_user_with_no_directory_row_still_appears(users_route):
    """Contractors and service accounts hold a cookie without a member row."""
    client = users_route(
        {"2067928": {"empno": "2067928", "emp_nm": "고대영", "dept_nm": "계측기술팀"}}
    )

    users = client.get("/api/activity/users").json["users"]

    assert [(row["user_id"], row["emp_nm"], row["dept_nm"]) for row in users] == [
        ("2067928", "고대영", "계측기술팀"),
        ("1234567", None, None),
    ]
    # The row is otherwise untouched — a missing profile costs the profile only.
    assert users[1]["requests_30d"] == 2


def test_a_partial_member_row_yields_the_field_it_has(users_route):
    """Everything but empno is optional in a member document, so one field
    being absent must not take the other down with it."""
    client = users_route(
        {
            "2067928": {"empno": "2067928", "emp_nm": "고대영"},
            "1234567": {"empno": "1234567", "dept_nm": "공정기술팀"},
        }
    )

    users = client.get("/api/activity/users").json["users"]

    assert [(row["emp_nm"], row["dept_nm"]) for row in users] == [
        ("고대영", None),
        (None, "공정기술팀"),
    ]


def test_an_unreachable_directory_costs_the_profiles_not_the_table(users_route):
    """lookup_members degrades to bare records rather than raising."""
    client = users_route(
        {
            "2067928": {"empno": "2067928", "emp_nm": None, "dept_nm": None},
            "1234567": {"empno": "1234567", "emp_nm": None, "dept_nm": None},
        }
    )

    response = client.get("/api/activity/users")

    assert response.status_code == 200
    assert [
        (row["emp_nm"], row["dept_nm"]) for row in response.json["users"]
    ] == [(None, None), (None, None)]


def test_a_declared_admin_id_does_not_pass_the_gate(make_client):
    # Typing an admin's id through self-identification proves nothing; only
    # trusted identity sources may hold admin.
    client = make_client("local-dev", "declared")

    assert client.get("/api/activity/users").status_code == 403


# The brief's sketch used a bare `client` fixture; this module only offers
# `make_client(user_id, identity_source)`, so these reuse that factory with a
# normal identified user — the beacon has no admin gate, but the handler still
# expects an identified request, matching every other route in this file.


def test_page_view_beacon_returns_204(make_client):
    client = make_client("1234567", "cookie")

    response = client.post("/api/page-view", json={"path": "/mag-pixel"})

    assert response.status_code == 204
    assert response.get_data() == b""


def test_page_view_beacon_rejects_a_missing_path(make_client):
    client = make_client("1234567", "cookie")

    assert client.post("/api/page-view", json={}).status_code == 400
    assert client.post("/api/page-view", json={"path": ""}).status_code == 400
    assert client.post("/api/page-view", data="not json").status_code == 400


@pytest.fixture
def beacon_client(monkeypatch):
    """A beacon client with the REAL activity middleware and an empty store.

    The plain ``make_client`` app has no after_request middleware, so it can
    only observe the status code. Recording happens in
    ``_logging/activity.py``, so proving "not ranked" needs that installed and
    the mock provider's process-local store swapped for a fresh one.
    """
    monkeypatch.setenv("SKEWNONO_ACTIVITY_PROVIDER", "mock")
    store: dict[str, mock._UserState] = {}
    monkeypatch.setattr(mock, "_users", store)

    app = Flask(__name__)

    @app.before_request
    def identity():
        g.user_id = "1234567"
        g.identity_source = "cookie"

    app.register_blueprint(routes.bp, url_prefix="/api")
    install_activity_logging(app)
    return app.test_client(), store


def test_a_resolvable_page_is_recorded_as_that_page(beacon_client):
    """The positive control: without it, an empty store proves nothing."""
    client, store = beacon_client

    assert client.post("/api/page-view", json={"path": "/mag-pixel"}).status_code == 204

    assert list(store["1234567"].last_opened) == ["mag_pixel"]


@pytest.mark.parametrize(
    "path",
    [
        "/settings",
        "/admin/logs",
        "/ebeam/cd-sem/M14/recipe-status",
    ],
    ids=["ops-page", "ops-child-page", "recipe-status-without-a-tab"],
)
def test_an_unresolvable_page_is_accepted_but_not_ranked(beacon_client, path):
    """An ops page or a tab-less recipe-status is a 204 that records nothing.

    A 400 here would make the browser console noisy for a case that is not an
    error — the plugin cannot know which paths the backend ranks. But the row
    must not be counted either: with no promoted slug the middleware would
    otherwise fall back to route_to_feature("/api/page-view") and rank the
    literal slug "page-view" as if it were a page.
    """
    client, store = beacon_client

    assert client.post("/api/page-view", json={"path": path}).status_code == 204

    assert store == {}


def test_a_beacon_files_the_page_under_its_family(beacon_client):
    """End to end through the real route and middleware: the beacon names a
    page, the page names a family, and the family card reads it back."""
    client, _store = beacon_client

    for path in (
        "/ebeam/hv-sem/R3/storage",
        "/ebeam/hv-sem/m14,r3/storage",
        "/ebeam/cd-sem/M14/storage",
        "/afm/map608/a.tif",
        # A shared page: ranked, but under no family.
        "/mag-pixel",
    ):
        assert client.post("/api/page-view", json={"path": path}).status_code == 204

    rows = {
        row["family"]: row
        for row in client.get("/api/activity/families").json["families_7d"]
    }

    assert rows["hvsem"] == {
        "family": "hvsem",
        "total": 1,
        "pages": [{"feature": "storage", "count": 2}],
    }
    assert rows["cdsem"]["pages"] == [{"feature": "storage", "count": 1}]
    assert rows["afm"]["pages"] == [{"feature": "afm", "count": 1}]
    assert rows["veritysem"]["total"] == 0
    assert sum(len(row["pages"]) for row in rows.values()) == 3
