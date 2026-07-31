"""The declared identity's storage.

Everything here rides in Flask's signed session cookie. The signature is what
makes `verified` mean anything — a plaintext cookie would let the person the
identity describes flip it — so these tests pin that every malformed shape
reads as "nobody declared" rather than as a partly trusted identity.

That defensiveness is not paranoia about attackers. `read_declared` runs inside
the app's first `before_request`, where a raised exception answers index.html
along with every bundle: a bad session must degrade, never throw.
"""

import pytest
from flask import Flask, session

from back_dev_home._auth.self_id import (
    SESSION_KEY,
    clear_declared,
    read_declared,
    write_declared,
)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test-key-not-the-real-one"
    return app


def test_nothing_declared_reads_as_none(app):
    with app.test_request_context("/"):
        assert read_declared() is None


def test_a_written_identity_reads_back(app):
    with app.test_request_context("/"):
        write_declared(
            empno="2067928", emp_nm="고대영", verified=True, declared_from="10.0.0.1"
        )

        assert read_declared() == {
            "empno": "2067928",
            "emp_nm": "고대영",
            "verified": True,
            "declared_from": "10.0.0.1",
        }


def test_clearing_removes_it(app):
    with app.test_request_context("/"):
        write_declared(
            empno="2067928", emp_nm="고대영", verified=True, declared_from=None
        )
        clear_declared()

        assert read_declared() is None


def test_clearing_when_nothing_is_declared_is_not_an_error(app):
    """The "본인이 아닙니다" link is reachable from a page whose session may
    already have expired; a KeyError there would 500 on a button meaning
    "undo"."""
    with app.test_request_context("/"):
        clear_declared()

        assert read_declared() is None


def test_a_row_without_an_empno_is_ignored(app):
    """Anything shaped wrong is nobody. A half-written session must not yield
    an identity with an empty id, which would then log as its own "user" and
    accumulate activity nobody can attribute."""
    with app.test_request_context("/"):
        session[SESSION_KEY] = {"emp_nm": "고대영", "verified": True}

        assert read_declared() is None


def test_a_non_dict_payload_is_ignored(app):
    with app.test_request_context("/"):
        session[SESSION_KEY] = "2067928"

        assert read_declared() is None


def test_verified_is_only_true_for_a_real_boolean(app):
    """The flag round-trips through the session's JSON serializer and then
    gates a security-relevant display. A leftover string like "no" is truthy,
    so bool() would promote an unverified identity to a verified one."""
    with app.test_request_context("/"):
        session[SESSION_KEY] = {"empno": "2067928", "verified": "no"}

        declared = read_declared()

        assert declared is not None
        assert declared["verified"] is False


def test_a_missing_name_reads_as_none_not_empty_string(app):
    """The SPA renders this directly; "" would show as a blank name where None
    lets it fall back to the employee number."""
    with app.test_request_context("/"):
        write_declared(empno="2067928", emp_nm="  ", verified=False, declared_from=None)

        declared = read_declared()

        assert declared is not None
        assert declared["emp_nm"] is None


def test_the_session_is_marked_permanent_on_write(app):
    """Without this the cookie is a browser-session cookie and the declaration
    evaporates when the tab closes — the 30-day lifetime the app factory
    configures applies only to sessions marked permanent, so omitting it would
    make that setting silently inert."""
    with app.test_request_context("/"):
        write_declared(empno="2067928", emp_nm=None, verified=False, declared_from=None)

        assert session.permanent is True


def test_surrounding_whitespace_is_stripped_on_write(app):
    with app.test_request_context("/"):
        write_declared(
            empno=" 2067928 ",
            emp_nm=" 고대영 ",
            verified=True,
            declared_from=" 10.0.0.1 ",
        )

        assert read_declared() == {
            "empno": "2067928",
            "emp_nm": "고대영",
            "verified": True,
            "declared_from": "10.0.0.1",
        }
