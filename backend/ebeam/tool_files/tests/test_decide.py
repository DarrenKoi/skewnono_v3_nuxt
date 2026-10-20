"""The access verdict: admins, then the allowed teams, row by row, in order."""

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
    assert decide(source, "2067928", _never) == "untrusted_identity"


def test_an_admin_is_granted_without_asking_the_directory():
    assert decide("cookie", "2067928", _never) == "granted"


@pytest.mark.parametrize("team", ALLOWED_TEAMS)
def test_a_member_of_each_allowed_team_is_granted(team):
    assert decide("cookie", "12345", _probe("found", team)) == "granted"


def test_surrounding_whitespace_in_dept_nm_is_ignored():
    assert decide("cookie", "12345", _probe("found", " DRAM MI개발 ")) == "granted"


@pytest.mark.parametrize("dept_nm", ["계측기술팀", "DRAM MI개발팀", "dram mi개발", None])
def test_any_other_team_or_none_gets_none(dept_nm):
    assert decide("cookie", "12345", _probe("found", dept_nm)) == "none"


def test_an_absent_member_gets_none():
    assert decide("cookie", "12345", _probe("absent")) == "none"


def test_an_unreachable_directory_is_directory_unavailable():
    assert decide("cookie", "12345", _probe("unavailable")) == "directory_unavailable"
