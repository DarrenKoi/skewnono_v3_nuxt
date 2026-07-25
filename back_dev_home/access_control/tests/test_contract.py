"""Contract gate for access_control. Runs against the ACTIVE provider via
data.py.

Home:   .venv/bin/pytest back_dev_home/access_control
Office: SKEWNONO_ACCESS_CONTROL_PROVIDER=office .venv/bin/pytest back_dev_home/access_control

Provider-safe roundtrip: add_exception/remove_exception grant and then
revoke their own synthetic id, so this test cleans up after itself
regardless of which provider is active. Wrapped in try/finally so the
removal always runs, even if the contract assertion fails partway through.

Nothing here is fenced behind the provider. Because the roundtrip writes the
data it then reads back, every assertion below is a rule MIGRATION.md requires
of the office adapter too — the two list shapes, `.strip().upper()`
normalization, and the enforcement path (is_blocked/record_denied) reading the
SAME store as the admin CRUD functions. No row counts, orderings or fabricated
values are asserted, so there is no mock-only invariant to keep out of the
office run.
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.access_control import data
from back_dev_home.access_control.contracts import (
    DeniedListResponse,
    ExceptionListResponse,
    ExceptionRow,
)


# add_exception only accepts ids starting with 'X' (BLOCKED_PREFIX) — the
# synthetic id is prefixed accordingly so the roundtrip below exercises the
# real grant path instead of tripping the "only X-ids need an exception"
# ValueError. Deliberately padded and lower-cased: an already-normalized id
# would let a provider that skips .strip().upper() pass the check below.
_TEST_USER_ID = "  x-contract-gate-00000  "


def test_list_denied_matches_contract():
    assert_matches(data.list_denied(), DeniedListResponse)


def test_list_exceptions_matches_contract():
    assert_matches(data.list_exceptions(), ExceptionListResponse)


def test_add_then_remove_exception_roundtrip():
    try:
        row = data.add_exception(_TEST_USER_ID)
        assert_matches(row, ExceptionRow)
        # Id normalization is a documented requirement of BOTH providers
        # (MIGRATION.md), not a mock detail — is_blocked and the exception
        # store would disagree about the same member otherwise.
        assert row["user_id"] == _TEST_USER_ID.strip().upper()
    finally:
        data.remove_exception(_TEST_USER_ID)


def test_is_blocked_reflects_exceptions():
    # is_blocked is a store-coupled ENFORCEMENT function (used by
    # _auth/middleware.py), so it must switch with the CRUD store. Verify the
    # rule tracks the exception list: an X-prefixed id is blocked, granting an
    # exception unblocks it, revoking blocks it again.
    uid = "X-CONTRACT-GATE-BLOCK1"
    assert data.is_blocked(uid) is True
    try:
        data.add_exception(uid)
        assert data.is_blocked(uid) is False
    finally:
        data.remove_exception(uid)
    assert data.is_blocked(uid) is True


def test_record_denied_appears_in_list():
    # record_denied is the other enforcement-path write (middleware logs a
    # blocked attempt). It has no un-record by design (capped audit log), so
    # this only appends one clearly-synthetic row.
    uid = "X-CONTRACT-GATE-DENY1"
    data.record_denied(uid)
    denied = data.list_denied()
    assert_matches(denied, DeniedListResponse)
    assert any(row["user_id"] == uid.upper() for row in denied), (
        "a recorded denied attempt must appear in list_denied()"
    )
