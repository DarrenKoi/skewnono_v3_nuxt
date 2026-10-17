"""Access requests end to end on mock: a member asks, an admin approves or
rejects, and the verdict follows on the next request.

Mock directory (providers/mock.py ``_MEMBERS``): 1000001 and 1000002 are in
계측기술팀, 1000003 in 공정기술팀, anyone else is absent.
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
    return client.get("/api/cdsem/tool-files/access").get_json()


def _ask(client, reason="레시피 백업 확인", **extra):
    return client.post("/api/tool-files/requests", json={"reason": reason, **extra})


def _pending(admin):
    return {r["empno"]: r for r in admin.get("/api/admin/tool-files").get_json()["requests"]}


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
    assert access["request"]["reason"] == "레시피 백업 확인"
    assert _code(_list(member)) == (403, "forbidden")

    row = _pending(admin)["1000003"]
    assert (row["emp_nm"], row["dept_nm"], row["status"]) == ("박공정", "공정기술팀", "pending")
    assert _approve(admin, "1000003", row["request_id"]).status_code == 200

    assert _access(member)["verdict"] == "granted"
    assert _list(member).status_code == 200
    assert _pending(admin) == {}


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
    assert again["request"]["reason"] == "사유를 고쳐 다시 신청"
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
    member = _member(app, "1000003")
    _ask(member)
    request_id = _pending(admin)["1000003"]["request_id"]
    _approve(admin, "1000003", request_id)
    grants = admin.get("/api/admin/tool-files").get_json()["grants"]

    assert _approve(admin, "1000003", request_id).status_code == 200
    assert admin.get("/api/admin/tool-files").get_json()["grants"] == grants


def test_deciding_a_request_that_never_existed_is_409(admin):
    assert _code(_approve(admin, "1000003", "f" * 32)) == (409, "request_changed")
    assert _code(_reject(admin, "1000003", "f" * 32)) == (409, "request_changed")


def test_a_team_approval_grants_the_team_and_clears_only_its_pending_requests(app, admin):
    for empno in ("1000001", "1000002", "1000003", "7777777"):
        _ask(_member(app, empno))
    # Only pending ones go: the admin already turned 1000002's down.
    _reject(admin, "1000002", _pending(admin)["1000002"]["request_id"])

    response = admin.post("/api/admin/tool-files/teams/approve", json={"dept_nm": "계측기술팀"})

    assert response.status_code == 201
    assert response.get_json()["cleared"] == ["1000001"]
    assert sorted(_pending(admin)) == ["1000002", "1000003", "7777777"]
    assert _list(_member(app, "1000001")).status_code == 200
    assert _list(_member(app, "1000002")).status_code == 200
    assert _access(_member(app, "1000003"))["verdict"] == "pending"


def test_a_team_approval_goes_by_the_stored_team_not_the_current_one(app, admin, tmp_path):
    import json

    _ask(_member(app, "1000003"))
    path = tmp_path / "requests.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["1000003"]["dept_nm"] = "계측기술팀"  # asked while still in 계측기술팀
    path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")

    admin.post("/api/admin/tool-files/teams/approve", json={"dept_nm": "계측기술팀"})

    assert _pending(admin) == {}
    # Cleared, but not let in: 1000003 is in 공정기술팀 now.
    assert _access(_member(app, "1000003"))["verdict"] == "none"


@pytest.mark.parametrize("body", [{}, {"dept_nm": "  "}, {"dept_nm": 3}, ["계측기술팀"]])
def test_a_malformed_team_approval_is_400(admin, body):
    response = admin.post("/api/admin/tool-files/teams/approve", json=body)
    assert _code(response) == (400, "bad_request")


@pytest.mark.parametrize("source", ["declared", "token"])
def test_an_untrusted_identity_cannot_request(app, admin, monkeypatch, source):
    monkeypatch.setattr(middleware, "resolve_identity", lambda: ("1000003", source))

    assert _code(_ask(app.test_client())) == (403, "untrusted_identity")
    monkeypatch.undo()
    assert _pending(admin) == {}


def test_a_granted_member_asking_changes_nothing(app, admin):
    admin.post("/api/admin/tool-files/grants", json={"kind": "team", "value": "계측기술팀"})

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
    _ask(_member(app, "1000003"), empno="1000001", dept_nm="계측기술팀", status="rejected")

    rows = _pending(admin)
    assert list(rows) == ["1000003"]
    assert (rows["1000003"]["dept_nm"], rows["1000003"]["status"]) == ("공정기술팀", "pending")


def test_an_absent_member_may_request_and_has_no_team(app, admin):
    _ask(_member(app, "7777777"))

    row = _pending(admin)["7777777"]
    assert (row["emp_nm"], row["dept_nm"]) == (None, None)


def test_a_corrupt_request_file_is_503_and_is_left_alone(app, admin, tmp_path):
    (tmp_path / "requests.json").write_text("{not json", encoding="utf-8")
    member = _member(app, "1000003")

    assert _access(member)["verdict"] == "store_unavailable"
    assert _code(_ask(member)) == (503, "store_unavailable")
    assert _code(admin.get("/api/admin/tool-files")) == (503, "store_unavailable")
    assert (tmp_path / "requests.json").read_text(encoding="utf-8") == "{not json"


@pytest.mark.parametrize(
    "path",
    [
        "/api/admin/tool-files/requests/approve",
        "/api/admin/tool-files/requests/reject",
        "/api/admin/tool-files/teams/approve",
    ],
)
def test_a_member_cannot_decide_requests(app, path):
    body = {"empno": "1000003", "request_id": "x", "dept_nm": "공정기술팀"}
    response = _member(app, "1000003").post(path, json=body)
    assert _code(response) == (403, "forbidden")


def test_request_and_decisions_each_leave_one_audit_line(app, admin, caplog):
    caplog.set_level("INFO", logger="skewnono.tool_files")
    member = _member(app, "1000003")
    _ask(member)
    first = _pending(admin)["1000003"]["request_id"]
    _reject(admin, "1000003", first)
    _ask(member)
    second = _pending(admin)["1000003"]["request_id"]
    _approve(admin, "1000003", first)
    _approve(admin, "1000003", second)
    admin.post("/api/admin/tool-files/teams/approve", json={"dept_nm": "공정기술팀"})

    lines = [r.getMessage() for r in caplog.records if r.name == "skewnono.tool_files"]
    assert [line.split()[1] for line in lines] == [
        "request", "reject", "request", "approve", "approve", "team_approve"
    ]
    assert "target=1000003 result=request_changed request_id=" in lines[3]
    assert lines[3].endswith(f"access_request_id={first}")
    assert "result=ok" in lines[4] and lines[4].endswith(f"access_request_id={second}")
    assert "target=team:공정기술팀 result=ok cleared=-" in lines[5]
