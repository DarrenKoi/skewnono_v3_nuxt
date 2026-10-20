"""Person grants end to end on mock: someone outside the allowed teams asks,
an admin approves or rejects (or grants and revokes directly), and the
verdict follows on the next request.

Mock directory (providers/mock.py ``_MEMBERS``): 1000001 is in an allowed
team, 1000002 and 1000003 are not, 1000005 is a directory outage, anyone
else is absent.
"""

import pytest

from backend import create_app
from backend._auth import middleware
from backend.ebeam._tool_specs import model_to_tool_type
from backend.sem_list.providers.mock import get_sem_list


@pytest.fixture
def app():
    # The autouse isolated_grants fixture points the store at tmp_path.
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


def _list(client):
    row = next(
        row
        for row in get_sem_list()
        if model_to_tool_type(row["eqp_model_cd"]) == "cd-sem"
        and row["available"] == "On"
        and sum(r["eqp_id"] == row["eqp_id"] for r in get_sem_list()) == 1
    )
    return client.get(
        "/api/cdsem/tool-files/list",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"]},
    )


def _access(client):
    return client.get("/api/tool-files/access").get_json()


def _ask(client, reason="파견 중 레시피 백업 확인", **extra):
    return client.post("/api/tool-files/requests", json={"reason": reason, **extra})


def _overview(admin):
    return admin.get("/api/admin/tool-files").get_json()


def _pending(admin):
    return {r["empno"]: r for r in _overview(admin)["requests"]}


def _grants(admin):
    return {r["empno"]: r for r in _overview(admin)["grants"]}


def _approve(admin, empno, request_id):
    return admin.post(
        "/api/admin/tool-files/requests/approve", json={"empno": empno, "request_id": request_id}
    )


def _reject(admin, empno, request_id):
    return admin.post(
        "/api/admin/tool-files/requests/reject", json={"empno": empno, "request_id": request_id}
    )


def _code(response):
    return response.status_code, response.get_json()["error"]["code"]


def test_a_request_waits_then_an_approval_opens_the_files(app, admin):
    member = _member(app, "1000003")

    assert _ask(member).status_code == 201
    access = _access(member)
    assert access["verdict"] == "pending"
    assert access["request"]["reason"] == "파견 중 레시피 백업 확인"
    assert _code(_list(member)) == (403, "forbidden")

    row = _pending(admin)["1000003"]
    # dept_nm is the request-time team from probe; emp_nm is a display lookup
    # (lookup_members, home placeholders).
    assert (row["emp_nm"], row["dept_nm"], row["status"]) == ("홍길동(1000003)", "공정기술팀", "pending")
    assert _approve(admin, "1000003", row["request_id"]).status_code == 200

    assert _access(member)["verdict"] == "granted"
    assert _list(member).status_code == 200
    assert _pending(admin) == {}
    grant = _grants(admin)["1000003"]
    assert (grant["emp_nm"], grant["granted_by"]) == ("홍길동(1000003)", "local-dev")


def test_a_rejected_request_can_be_made_again_under_a_new_id(app, admin):
    member = _member(app, "1000003")
    _ask(member)
    first = _pending(admin)["1000003"]["request_id"]

    assert _reject(admin, "1000003", first).status_code == 200
    access = _access(member)
    assert (access["verdict"], access["request"]["status"]) == ("rejected", "rejected")
    assert _code(_list(member)) == (403, "forbidden")

    _ask(member, reason="사유를 고쳐 다시 신청")
    again = _access(member)
    assert again["verdict"] == "pending"
    assert again["request"]["request_id"] != first


@pytest.mark.parametrize("decide", [_approve, _reject])
def test_a_re_request_between_view_and_decision_is_409_and_changes_nothing(app, admin, decide):
    member = _member(app, "1000003")
    _ask(member)
    seen = _pending(admin)["1000003"]["request_id"]
    _ask(member, reason="다시 신청")

    assert _code(decide(admin, "1000003", seen)) == (409, "request_changed")
    access = _access(member)
    assert (access["verdict"], access["request"]["reason"]) == ("pending", "다시 신청")


def test_a_retried_approval_whose_request_is_gone_succeeds_without_change(app, admin):
    _ask(_member(app, "1000003"))
    request_id = _pending(admin)["1000003"]["request_id"]
    _approve(admin, "1000003", request_id)
    grants = _grants(admin)

    assert _approve(admin, "1000003", request_id).status_code == 200
    assert _grants(admin) == grants


def test_deciding_a_request_that_never_existed_is_409(admin):
    assert _code(_approve(admin, "1000003", "f" * 32)) == (409, "request_changed")
    assert _code(_reject(admin, "1000003", "f" * 32)) == (409, "request_changed")


def test_a_direct_grant_and_revoke_follow_on_the_next_request(app, admin):
    member = _member(app, "1000002")
    assert _code(_list(member)) == (403, "forbidden")

    response = admin.post("/api/admin/tool-files/grants", json={"empno": " 1000002 "})
    assert response.status_code == 201
    assert response.get_json()["empno"] == "1000002"
    assert _list(member).status_code == 200

    revoked = admin.post("/api/admin/tool-files/grants/revoke", json={"empno": "1000002"})
    assert revoked.get_json() == {"revoked": True}
    assert _code(_list(member)) == (403, "forbidden")
    again = admin.post("/api/admin/tool-files/grants/revoke", json={"empno": "1000002"})
    assert again.get_json() == {"revoked": False}


def test_a_repeat_grant_keeps_the_first_stamp(admin):
    first = admin.post("/api/admin/tool-files/grants", json={"empno": "1000002"}).get_json()
    second = admin.post("/api/admin/tool-files/grants", json={"empno": "1000002"}).get_json()
    assert second["granted_at"] == first["granted_at"]


def test_a_granted_person_gets_in_through_a_directory_outage(app, admin):
    admin.post("/api/admin/tool-files/grants", json={"empno": "1000005"})
    assert _list(_member(app, "1000005")).status_code == 200


@pytest.mark.parametrize("body", [{}, {"empno": "  "}, {"empno": 3}, ["1000002"]])
@pytest.mark.parametrize("leaf", ["grants", "grants/revoke"])
def test_a_malformed_grant_body_is_400(admin, body, leaf):
    assert _code(admin.post(f"/api/admin/tool-files/{leaf}", json=body)) == (400, "bad_request")


@pytest.mark.parametrize("source", ["declared", "token"])
def test_an_untrusted_identity_cannot_request(app, admin, monkeypatch, source):
    monkeypatch.setattr(middleware, "resolve_identity", lambda: ("1000003", source))

    assert _code(_ask(app.test_client())) == (403, "untrusted_identity")
    monkeypatch.undo()
    assert _pending(admin) == {}


def test_a_team_member_asking_changes_nothing(app, admin):
    response = _ask(_member(app, "1000001"))

    assert (response.status_code, response.get_json()) == (200, {"verdict": "granted"})
    assert _pending(admin) == {}


@pytest.mark.parametrize("body", [{}, {"reason": "   "}, {"reason": 3}, {"reason": "가" * 201}, ["사유"]])
def test_a_malformed_reason_is_400(app, admin, body):
    response = _member(app, "1000003").post("/api/tool-files/requests", json=body)

    assert _code(response) == (400, "bad_request")
    assert _pending(admin) == {}


def test_a_reason_of_exactly_200_characters_is_taken(app):
    assert _ask(_member(app, "1000003"), reason="가" * 200).status_code == 201


def test_the_server_decides_empno_team_and_status_whatever_the_client_sends(app, admin):
    _ask(_member(app, "1000003"), empno="1000001", dept_nm="DRAM MI개발", status="rejected")

    rows = _pending(admin)
    assert list(rows) == ["1000003"]
    assert (rows["1000003"]["dept_nm"], rows["1000003"]["status"]) == ("공정기술팀", "pending")


def test_an_absent_member_may_request_and_has_no_team(app, admin):
    _ask(_member(app, "7777777"))

    assert _pending(admin)["7777777"]["dept_nm"] is None


def test_a_corrupt_store_file_is_503_for_outsiders_only_and_is_left_alone(app, admin, tmp_path):
    (tmp_path / "grants.json").write_text("{not json", encoding="utf-8")
    member = _member(app, "1000003")

    assert _access(member)["verdict"] == "store_unavailable"
    assert _code(_list(member)) == (503, "store_unavailable")
    assert _code(_ask(member)) == (503, "store_unavailable")
    assert _code(admin.get("/api/admin/tool-files")) == (503, "store_unavailable")
    assert _list(_member(app, "1000001")).status_code == 200
    assert (tmp_path / "grants.json").read_text(encoding="utf-8") == "{not json"


@pytest.mark.parametrize(
    "path",
    [
        "/api/admin/tool-files/requests/approve",
        "/api/admin/tool-files/requests/reject",
        "/api/admin/tool-files/grants",
        "/api/admin/tool-files/grants/revoke",
    ],
)
def test_a_member_cannot_decide_or_grant(app, path):
    body = {"empno": "1000003", "request_id": "x"}
    assert _code(_member(app, "1000001").post(path, json=body)) == (403, "forbidden")


def test_a_member_cannot_read_the_overview(app):
    assert _code(_member(app, "1000001").get("/api/admin/tool-files")) == (403, "forbidden")


def test_every_mutation_leaves_one_audit_line(app, admin, caplog):
    caplog.set_level("INFO", logger="skewnono.tool_files")
    member = _member(app, "1000003")
    _ask(member)
    first = _pending(admin)["1000003"]["request_id"]
    _reject(admin, "1000003", first)
    _ask(member)
    second = _pending(admin)["1000003"]["request_id"]
    _approve(admin, "1000003", first)
    _approve(admin, "1000003", second)
    admin.post("/api/admin/tool-files/grants/revoke", json={"empno": "1000003"})
    admin.post("/api/admin/tool-files/grants", json={"empno": "1000002"})

    lines = [r.getMessage() for r in caplog.records if r.name == "skewnono.tool_files"]
    assert [line.split()[1] for line in lines] == [
        "request", "reject", "request", "approve", "approve", "revoke", "grant"
    ]
    assert "target=1000003 result=request_changed request_id=" in lines[3]
    assert lines[3].endswith(f"access_request_id={first}")
    assert "result=ok" in lines[4] and lines[4].endswith(f"access_request_id={second}")
