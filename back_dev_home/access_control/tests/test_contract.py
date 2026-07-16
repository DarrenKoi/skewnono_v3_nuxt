"""Contract gate for access_control. Runs against the ACTIVE provider via
data.py.

Home:   .venv/bin/pytest back_dev_home/access_control
Office: SKEWNONO_ACCESS_CONTROL_PROVIDER=office .venv/bin/pytest back_dev_home/access_control

Provider-safe roundtrip: add_exception/remove_exception grant and then
revoke their own synthetic id, so this test cleans up after itself
regardless of which provider is active. Wrapped in try/finally so the
removal always runs, even if the contract assertion fails partway through.
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
# ValueError.
_TEST_USER_ID = "X-CONTRACT-GATE-00000"


def test_list_denied_matches_contract():
    assert_matches(data.list_denied(), DeniedListResponse)


def test_list_exceptions_matches_contract():
    assert_matches(data.list_exceptions(), ExceptionListResponse)


def test_add_then_remove_exception_roundtrip():
    try:
        row = data.add_exception(_TEST_USER_ID)
        assert_matches(row, ExceptionRow)
        assert row["user_id"] == _TEST_USER_ID.upper()
    finally:
        data.remove_exception(_TEST_USER_ID)
