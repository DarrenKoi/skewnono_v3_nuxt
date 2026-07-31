"""Verification, tested without a directory.

Home fabricates member rows, so if this logic lived inside the route it would
never execute here — and would meet a real `members` hash for the first time on
the cloud. That is the mock blind spot `CLAUDE.md` warns about, and keeping the
decision pure is what closes it: every row of the spec's §6.2 table is checked
below on a laptop with no Redis, no Flask and no request.

The table has exactly one rejecting cell. Several tests exist only to keep it
that way, because widening rejection is the change most likely to look harmless
and lock people out.
"""

import pytest

from back_dev_home._auth.directory import Probe
from back_dev_home._auth.verify import decide, names_match

_MEMBER = {
    "empno": "2067928",
    "emp_nm": "고대영",
    "dept_nm": "계측기술팀",
    "organ_cd": "A1234",
    "upper_organ_nm": "제조기술",
}


def test_an_exact_name_is_accepted_and_verified():
    decision = decide(Probe(_MEMBER, "found"), "고대영")

    assert decision.accept is True
    assert decision.verified is True
    assert decision.emp_nm == "고대영"
    assert decision.reason == "match"


def test_the_directory_name_is_what_gets_stored():
    """The entered name is a check, not data. On success we keep the
    directory's spelling, which is the one that arrives with dept and org
    attached."""
    decision = decide(Probe(_MEMBER, "found"), "  고대영  ")

    assert decision.emp_nm == "고대영"


def test_surrounding_whitespace_is_forgiven():
    assert names_match("  고대영 ", "고대영") is True


def test_internal_spacing_is_not_forgiven():
    """Two different people can differ by exactly an internal space, so
    collapsing it would let one of them verify as the other."""
    assert names_match("고 대영", "고대영") is False


def test_a_wrong_name_is_rejected():
    decision = decide(Probe(_MEMBER, "found"), "홍길동")

    assert decision.accept is False
    assert decision.verified is False
    assert decision.reason == "mismatch"


def test_a_rejection_stores_nothing():
    """A refused declaration must not leave a name behind for a later caller
    to mistake for a confirmed one."""
    assert decide(Probe(_MEMBER, "found"), "홍길동").emp_nm is None


def test_an_absent_row_is_accepted_unverified():
    """The 2026-07-31 revision. `directory.py` documents contractors and
    service accounts as holding a cookie without a row, so rejecting on
    `absent` locks out a population the code asserts exists — before anyone has
    measured how large it is."""
    decision = decide(Probe(None, "absent"), "홍길동")

    assert decision.accept is True
    assert decision.verified is False
    assert decision.reason == "absent"


def test_an_unavailable_directory_is_accepted_unverified():
    decision = decide(Probe(None, "unavailable"), "홍길동")

    assert decision.accept is True
    assert decision.verified is False
    assert decision.reason == "unavailable"


@pytest.mark.parametrize("status", ["absent", "unavailable"])
def test_an_unverifiable_declaration_keeps_the_entered_name(status):
    """Storing nothing would leave an employee number with no name at all,
    which defeats attribution — the point of the entire feature."""
    assert decide(Probe(None, status), " 홍길동 ").emp_nm == "홍길동"


def test_only_a_name_mismatch_ever_rejects():
    """The single rejecting cell, stated on its own so that widening rejection
    has to delete an assertion that explains why it should not."""
    assert decide(Probe(None, "absent"), "홍길동").accept is True
    assert decide(Probe(None, "unavailable"), "홍길동").accept is True

    assert decide(Probe(_MEMBER, "found"), "홍길동").accept is False


def test_a_found_row_with_no_name_cannot_verify():
    """A partial directory row carries an employee number and nothing else.
    There is nothing to compare against, so it must not pass as verified — but
    the user did nothing wrong, so it must not reject either."""
    partial = {**_MEMBER, "emp_nm": None}

    decision = decide(Probe(partial, "found"), "고대영")

    assert decision.accept is True
    assert decision.verified is False
    assert decision.emp_nm == "고대영"


@pytest.mark.parametrize("entered", ["", "   "])
def test_an_empty_entered_name_never_verifies(entered):
    """Empty input must not match an empty or missing directory name into a
    verified identity."""
    assert decide(Probe(_MEMBER, "found"), entered).verified is False


def test_names_match_refuses_a_missing_directory_name():
    """Guards the same hole from the other side: `None` is not something a
    user can successfully type."""
    assert names_match("", None) is False
    assert names_match("고대영", None) is False
