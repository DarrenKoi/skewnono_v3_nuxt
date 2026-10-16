"""Team and empno grants end to end on mock: the admin API writes the store,
and the browser routes read the verdict from it on every request.

Mock directory (providers/mock.py ``_MEMBERS``): 1000001 and 1000002 are in
계측기술팀, 1000003 in 공정기술팀, 1000004 has no dept_nm, 1000005 is a
directory outage, anyone else is absent.
"""

import pytest

from backend import create_app
from backend._auth import middleware
from backend.ebeam._tool_specs import model_to_tool_type
from backend.sem_list.providers.mock import get_sem_list


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_GRANTS_FILE", str(tmp_path / "grants.json"))
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def admin(app):
    return app.test_client()


def _member(app, empno):
    client = app.test_client()
    client.set_cookie("LASTUSER", empno)
    return client


def _row():
    return next(
        row
        for row in get_sem_list()
        if model_to_tool_type(row["eqp_model_cd"]) == "cd-sem"
        and row["available"] == "On"
        and sum(r["eqp_id"] == row["eqp_id"] for r in get_sem_list()) == 1
    )


def _list(client):
    row = _row()
    return client.get(
        "/api/cdsem/tool-files/list",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"]},
    )


def _verdict(client):
    return client.get("/api/cdsem/tool-files/access").get_json()["verdict"]


def _grant(admin, kind, value):
    return admin.post("/api/admin/tool-files/grants", json={"kind": kind, "value": value})


def _revoke(admin, kind, value):
    return admin.post("/api/admin/tool-files/grants/revoke", json={"kind": kind, "value": value})


def _code(response):
    return response.status_code, response.get_json()["error"]["code"]


def test_a_member_with_no_grant_is_refused(app):
    member = _member(app, "1000001")

    assert _verdict(member) == "none"
    assert _code(_list(member)) == (403, "forbidden")


def test_an_empno_grant_lets_the_member_in_and_revoking_it_shuts_them_out(app, admin):
    member = _member(app, "1000003")

    assert _grant(admin, "emp", "1000003").status_code == 201
    assert _verdict(member) == "granted"
    assert _list(member).status_code == 200

    assert _revoke(admin, "emp", "1000003").get_json() == {"revoked": True}
    assert _code(_list(member)) == (403, "forbidden")


def test_a_team_grant_admits_its_members_and_nobody_else(app, admin):
    _grant(admin, "team", "계측기술팀")

    assert _list(_member(app, "1000001")).status_code == 200
    assert _list(_member(app, "1000002")).status_code == 200
    assert _code(_list(_member(app, "1000003"))) == (403, "forbidden")
    assert _code(_list(_member(app, "1000004"))) == (403, "forbidden")
    assert _code(_list(_member(app, "7777777"))) == (403, "forbidden")


def test_revoking_an_empno_grant_keeps_access_through_the_team(app, admin):
    _grant(admin, "team", "계측기술팀")
    _grant(admin, "emp", "1000001")
    _revoke(admin, "emp", "1000001")

    assert _list(_member(app, "1000001")).status_code == 200


def test_a_directory_outage_is_503_not_a_refusal(app, admin):
    _grant(admin, "team", "계측기술팀")
    member = _member(app, "1000005")

    assert _verdict(member) == "directory_unavailable"
    assert _code(_list(member)) == (503, "directory_unavailable")


@pytest.mark.parametrize("source", ["declared", "token"])
def test_an_untrusted_identity_is_refused_even_with_an_empno_grant(app, admin, monkeypatch, source):
    _grant(admin, "emp", "1000001")
    monkeypatch.setattr(middleware, "resolve_identity", lambda: ("1000001", source))

    caller = app.test_client()
    assert _verdict(caller) == "untrusted_identity"
    assert _code(_list(caller)) == (403, "untrusted_identity")


def test_a_corrupt_grant_file_is_503_for_members_and_admin_api_alike(app, admin, tmp_path):
    (tmp_path / "grants.json").write_text("{not json", encoding="utf-8")
    member = _member(app, "1000001")

    assert _verdict(member) == "store_unavailable"
    assert _code(_list(member)) == (503, "store_unavailable")
    assert _code(admin.get("/api/admin/tool-files")) == (503, "store_unavailable")
    assert _code(_grant(admin, "emp", "1000001")) == (503, "store_unavailable")
    assert (tmp_path / "grants.json").read_text(encoding="utf-8") == "{not json"


def test_the_admin_still_browses_while_the_store_is_corrupt(admin, tmp_path):
    (tmp_path / "grants.json").write_text("{not json", encoding="utf-8")

    assert _list(admin).status_code == 200


def test_granted_by_is_the_server_identity_and_a_repeat_grant_keeps_the_first(admin):
    first = admin.post(
        "/api/admin/tool-files/grants",
        json={"kind": "emp", "value": " 1000003 ", "granted_by": "9999999"},
    ).get_json()
    again = _grant(admin, "emp", "1000003").get_json()

    assert first["granted_by"] == "local-dev"
    assert again == first
    rows = admin.get("/api/admin/tool-files").get_json()["grants"]
    assert [(r["kind"], r["value"], r["granted_by"]) for r in rows] == [
        ("emp", "1000003", "local-dev")
    ]


def test_the_admin_list_names_an_empno_grantees_current_team(admin):
    _grant(admin, "emp", "1000001")
    _grant(admin, "emp", "7777777")
    _grant(admin, "team", "공정기술팀")

    rows = admin.get("/api/admin/tool-files").get_json()["grants"]
    assert [(r["kind"], r["value"], r["dept_nm"]) for r in rows] == [
        ("emp", "1000001", "계측기술팀"),
        ("emp", "7777777", None),
        ("team", "공정기술팀", None),
    ]


def test_revoking_what_was_never_granted_reports_false(admin):
    assert _revoke(admin, "team", "없는팀").get_json() == {"revoked": False}


@pytest.mark.parametrize(
    "body",
    [{}, {"kind": "group", "value": "x"}, {"kind": "emp", "value": "  "}, {"kind": "team", "value": 3}],
)
def test_a_malformed_grant_is_400(admin, body):
    response = admin.post("/api/admin/tool-files/grants", json=body)
    assert _code(response) == (400, "bad_request")


def test_the_team_list_counts_directory_members(admin):
    body = admin.get("/api/admin/tool-files/teams").get_json()

    assert body == {
        "teams": [
            {"dept_nm": "계측기술팀", "members": 2},
            {"dept_nm": "공정기술팀", "members": 1},
        ],
        "complete": True,
    }


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/api/admin/tool-files"),
        ("get", "/api/admin/tool-files/teams"),
        ("post", "/api/admin/tool-files/grants"),
        ("post", "/api/admin/tool-files/grants/revoke"),
    ],
)
def test_the_admin_api_refuses_a_member(app, method, path):
    response = getattr(_member(app, "1000001"), method)(path, json={"kind": "emp", "value": "1000001"})
    assert _code(response) == (403, "forbidden")
