"""The member directory and its refusal to fail.

Every test here is really the same assertion from a different angle: whatever
goes wrong between the cookie and Redis, the caller keeps their identity. The
directory adds a name to an identity that is already complete, so a directory
problem may cost the name and must never cost the identity.

That makes the failure paths the subject rather than the edge cases — a
directory that raises would take down every page for every user the moment
Redis blinked, which is a worse outage than the one it was reporting.
"""

import json

import pytest

from back_dev_home._auth import directory as directory_mod
from back_dev_home._auth.directory import (
    MEMBERS_KEY,
    bare_member,
    lookup_member,
    reset_cache,
)

MEMBER_DOC = {
    "empno": "2067928",
    "emp_nm": "고대영",
    "dept_nm": "계측기술팀",
    "organ_cd": "A1234",
    "upper_organ_nm": "제조기술",
}


class _FakeRedis:
    """Minimal stand-in: records HGETs, returns whatever was planted."""

    def __init__(self, values=None, raises=None):
        self._values = values or {}
        self._raises = raises
        self.calls = []

    def hget(self, key, field):
        self.calls.append((key, field))
        if self._raises is not None:
            raise self._raises
        value = self._values.get(field)
        return value if value is None else value.encode("utf-8")


@pytest.fixture(autouse=True)
def clean_cache():
    """The cache is process-global and would leak one test's Redis into another."""
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def redis_returning(monkeypatch):
    """Put the directory in office mode behind a fake Redis.

    Office mode is part of the fixture because it is what makes the module
    reach for Redis at all — at home it short-circuits to a fabricated row and
    the client is never consulted.
    """

    def install(values=None, raises=None):
        client = _FakeRedis(values, raises)
        monkeypatch.setattr(directory_mod, "get_mode", lambda: "office")
        monkeypatch.setattr(
            directory_mod, "redis_client_or_none", lambda: client
        )
        return client

    return install


def test_a_member_row_becomes_the_profile(redis_returning):
    redis_returning({"2067928": json.dumps(MEMBER_DOC)})

    assert lookup_member("2067928") == MEMBER_DOC


def test_the_lookup_is_one_hget_against_the_members_hash(redis_returning):
    client = redis_returning({"2067928": json.dumps(MEMBER_DOC)})

    lookup_member("2067928")

    assert client.calls == [(MEMBERS_KEY, "2067928")]


def test_an_unknown_member_keeps_their_id(redis_returning):
    """Contractors and service accounts hold a cookie with no directory row.
    Ordinary, not exceptional — they still get to use the app."""
    redis_returning({})

    assert lookup_member("9999999") == bare_member("9999999")


def test_redis_being_down_costs_the_name_not_the_identity(redis_returning):
    """The whole reason this module swallows instead of raising. An office
    adapter would 503 here; that behaviour would take every page down."""
    redis_returning(raises=OSError("connection refused"))

    assert lookup_member("2067928") == bare_member("2067928")


def test_home_fabricates_the_shape(monkeypatch):
    """Degrading to an empno alone at home would mean the UI is built against a
    field set the cloud never sends, so home gets a fabricated row instead —
    obviously fake, but the right shape."""
    monkeypatch.setattr(directory_mod, "get_mode", lambda: "mock")

    member = lookup_member("2067928")

    assert member["empno"] == "2067928"
    assert member["emp_nm"] and member["dept_nm"]


def test_home_never_dials_redis(monkeypatch):
    """The latency fix, pinned. Home's REDIS_HOST points at an office host it
    cannot reach, so a connect attempt costs the full socket timeout (10s: 5s
    connect plus one retry) on every cold lookup and yields nothing anyway.
    A configured-but-unreachable client is exactly the home situation, so
    "no client" is not enough to prove we skipped it — assert nothing was
    asked of the client at all."""
    monkeypatch.setattr(directory_mod, "get_mode", lambda: "mock")
    client = _FakeRedis({}, raises=AssertionError("home must not dial Redis"))
    monkeypatch.setattr(directory_mod, "redis_client_or_none", lambda: client)

    lookup_member("2067928")

    assert client.calls == []


def test_office_mode_without_redis_invents_nothing(monkeypatch, caplog):
    """Missing config in office mode means an incomplete .env. Filling a real
    person's name with a placeholder there would be worse than showing an
    employee number, so this path stays bare — and says so in the log."""
    monkeypatch.setattr(directory_mod, "get_mode", lambda: "office")
    monkeypatch.setattr(directory_mod, "redis_client_or_none", lambda: None)

    with caplog.at_level("WARNING"):
        assert lookup_member("2067928") == bare_member("2067928")

    assert "Redis is unconfigured" in caplog.text


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        '"a bare string"',
        "[1, 2, 3]",
        "",
    ],
)
def test_an_unexpected_value_encoding_degrades_rather_than_raising(
    redis_returning, raw
):
    """The value being JSON is this module's one unverified assumption
    (OFFICE-VERIFY). If it is wrong, users must still get in — and the warning
    log is what tells us to go fix the decoder."""
    redis_returning({"2067928": raw})

    assert lookup_member("2067928") == bare_member("2067928")


def test_a_wrong_encoding_is_logged_so_the_assumption_can_be_corrected(
    redis_returning, caplog
):
    redis_returning({"2067928": "not json at all"})

    with caplog.at_level("WARNING"):
        lookup_member("2067928")

    assert "not the expected JSON object" in caplog.text


def test_a_partial_row_fills_only_what_it_has(redis_returning):
    """Directory rows are not guaranteed complete, and a missing dept is not
    worth failing a page over."""
    redis_returning({"2067928": json.dumps({"emp_nm": "고대영"})})

    assert lookup_member("2067928") == {
        **bare_member("2067928"),
        "emp_nm": "고대영",
    }


def test_the_cookie_wins_over_a_disagreeing_document(redis_returning):
    """empno in the row is expected to match the cookie. If it does not, the
    cookie is authoritative — access control, the admin allowlist and the
    activity log all keyed on it already, and letting the directory rename the
    caller mid-request would split one person across two identities."""
    redis_returning(
        {"2067928": json.dumps({**MEMBER_DOC, "empno": "SOMEONE-ELSE"})}
    )

    assert lookup_member("2067928")["empno"] == "2067928"


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_blank_directory_fields_read_as_absent(redis_returning, blank):
    """An office row that spells 'not set' as an empty string must not surface
    as an empty name in the UI."""
    redis_returning({"2067928": json.dumps({**MEMBER_DOC, "dept_nm": blank})})

    assert lookup_member("2067928")["dept_nm"] is None


def test_a_numeric_field_is_coerced_to_text(redis_returning):
    """organ_cd is plausibly stored as a number; the contract says str|None and
    the SPA renders it directly."""
    redis_returning({"2067928": json.dumps({**MEMBER_DOC, "organ_cd": 1234})})

    assert lookup_member("2067928")["organ_cd"] == "1234"


def test_an_unidentified_caller_has_no_member(redis_returning):
    client = redis_returning({})

    assert lookup_member(None) is None
    assert lookup_member("") is None
    assert client.calls == []  # and Redis was never troubled about it


def test_repeat_lookups_are_cached(redis_returning):
    """identify() runs on every request; without this, showing a name would
    cost an HGET per page view."""
    client = redis_returning({"2067928": json.dumps(MEMBER_DOC)})

    lookup_member("2067928")
    lookup_member("2067928")
    lookup_member("2067928")

    assert len(client.calls) == 1


def test_the_cache_expires_on_the_ttl_bucket(redis_returning, monkeypatch):
    """Entries must not live for the lifetime of a uwsgi worker, which is weeks.

    Drives the clock rather than sleeping: the cache key carries a time bucket,
    so crossing a TTL boundary is what makes the next call a miss.
    """
    client = redis_returning({"2067928": json.dumps(MEMBER_DOC)})
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(directory_mod.time, "time", lambda: clock["now"])

    lookup_member("2067928")
    clock["now"] += directory_mod._TTL_SECONDS + 1
    lookup_member("2067928")

    assert len(client.calls) == 2
