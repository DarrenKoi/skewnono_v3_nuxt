"""The access verdict table (spec "권한 판정"), row by row, in order."""

import pytest

from backend._auth.directory import Probe
from backend.ebeam.tool_files.access import decide

_GRANT = {"granted_at": "2026-10-17T00:00:00Z", "granted_by": "2067928"}


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
    raise AssertionError("the directory must not be asked")


@pytest.fixture(autouse=True)
def pinned_admins(monkeypatch):
    from backend._auth import admin

    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928")
    admin._parse_allowlist.cache_clear()
    yield
    admin._parse_allowlist.cache_clear()


@pytest.mark.parametrize("source", ["declared", "token", "anonymous", None])
def test_an_untrusted_source_is_refused_even_for_an_admin_id(source):
    assert decide(source, "2067928", _never, _never) == "untrusted_identity"


def test_an_admin_is_granted_without_reading_the_store():
    assert decide("cookie", "2067928", _never, _never) == "granted"


def test_an_unreadable_store_is_store_unavailable():
    assert decide("cookie", "12345", lambda: None, _never) == "store_unavailable"


def test_an_empno_grant_wins_without_asking_the_directory():
    assert decide("cookie", "12345", lambda: {"emp:12345": _GRANT}, _never) == "granted"


def test_an_empno_grant_matches_case_insensitively():
    assert decide("cookie", "x12345", lambda: {"emp:X12345": _GRANT}, _never) == "granted"


def test_a_member_of_a_granted_team_is_granted():
    grants = {"team:계측기술팀": _GRANT}
    assert decide("cookie", "12345", lambda: grants, _probe("found")) == "granted"


def test_a_member_of_another_team_gets_none():
    grants = {"team:공정기술팀": _GRANT}
    assert decide("cookie", "12345", lambda: grants, _probe("found")) == "none"


def test_a_profile_without_dept_nm_skips_the_team_check():
    grants = {"team:": _GRANT}
    assert decide("cookie", "12345", lambda: grants, _probe("found", dept_nm=None)) == "none"


def test_an_absent_member_gets_none():
    grants = {"team:계측기술팀": _GRANT}
    assert decide("cookie", "12345", lambda: grants, _probe("absent")) == "none"


def test_an_unreachable_directory_is_directory_unavailable():
    grants = {"team:계측기술팀": _GRANT}
    assert decide("local", "12345", lambda: grants, _probe("unavailable")) == "directory_unavailable"
