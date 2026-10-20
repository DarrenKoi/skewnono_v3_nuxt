"""The access verdict: admins, the allowed teams, then person grants and
requests, row by row, in order."""

import pytest

from backend._auth.directory import Probe
from backend.ebeam.tool_files.access import ALLOWED_TEAMS, decide


def _member(dept_nm):
    return {
        "empno": "12345",
        "emp_nm": "홍길동",
        "dept_nm": dept_nm,
        "organ_cd": None,
        "upper_organ_nm": None,
    }


def _probe(status, dept_nm="계측기술팀"):
    member = _member(dept_nm) if status == "found" else None
    return lambda: Probe(member, status)


def _never():
    raise AssertionError("must not be asked")


_GRANT = {"granted_at": "2026-10-21T00:00:00Z", "granted_by": "2067928"}


def _request(status):
    return {
        "request_id": "r1",
        "reason": "파견 중 로그 확인",
        "dept_nm": "계측기술팀",
        "requested_at": "2026-10-21T00:00:00Z",
        "status": status,
    }


def _verdict(probe, grants=dict, requests=dict, empno="12345", source="cookie"):
    return decide(source, empno, probe, grants, requests)


@pytest.fixture(autouse=True)
def pinned_admins(monkeypatch):
    from backend._auth import admin

    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928")
    admin._parse_allowlist.cache_clear()
    yield
    admin._parse_allowlist.cache_clear()


@pytest.mark.parametrize("source", ["declared", "token", "anonymous", None])
def test_an_untrusted_source_is_refused_even_for_an_admin_id(source):
    assert _verdict(_never, _never, _never, "2067928", source) == "untrusted_identity"


def test_an_admin_is_granted_without_asking_the_directory():
    assert _verdict(_never, _never, _never, "2067928") == "granted"


@pytest.mark.parametrize("team", ALLOWED_TEAMS)
def test_a_member_of_each_allowed_team_is_granted_without_reading_the_store(team):
    assert _verdict(_probe("found", team), _never, _never) == "granted"


def test_surrounding_whitespace_in_dept_nm_is_ignored():
    assert _verdict(_probe("found", " DRAM MI개발 ")) == "granted"


@pytest.mark.parametrize("dept_nm", ["계측기술팀", "DRAM MI개발팀", "dram mi개발", None])
def test_any_other_team_or_none_gets_none(dept_nm):
    assert _verdict(_probe("found", dept_nm)) == "none"


def test_an_absent_member_gets_none():
    assert _verdict(_probe("absent")) == "none"


def test_an_unreachable_directory_is_directory_unavailable():
    assert _verdict(_probe("unavailable")) == "directory_unavailable"


def test_a_person_grant_lets_in_someone_outside_the_teams():
    assert _verdict(_probe("found"), lambda: {"12345": _GRANT}, _never) == "granted"


def test_a_person_grant_matches_the_normalised_empno():
    grants = lambda: {"X12345": _GRANT}  # noqa: E731
    assert _verdict(_probe("found"), grants, _never, empno=" x12345 ") == "granted"


def test_a_person_grant_survives_a_directory_outage():
    assert _verdict(_probe("unavailable"), lambda: {"12345": _GRANT}, _never) == "granted"


def test_an_unreadable_store_outside_the_teams_is_store_unavailable():
    assert _verdict(_probe("found"), lambda: None) == "store_unavailable"


def test_both_down_reports_the_directory():
    assert _verdict(_probe("unavailable"), lambda: None) == "directory_unavailable"


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_the_own_request_status_is_the_verdict(status):
    requests = lambda: {"12345": _request(status)}  # noqa: E731
    assert _verdict(_probe("found"), dict, requests) == status


def test_an_unreadable_request_store_is_store_unavailable():
    assert _verdict(_probe("found"), dict, lambda: None) == "store_unavailable"
