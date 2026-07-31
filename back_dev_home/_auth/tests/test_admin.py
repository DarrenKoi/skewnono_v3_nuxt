"""Admin is the only thing this feature enforces on the server.

The self-identification gate is client-side by design (spec §4) — `curl`
bypasses it entirely — so the whole security surface of the feature is the rule
below: an identity the user typed in for themselves can never hold admin, no
matter which employee number they typed. Everything else about a declared
identity is attribution, not authority.

The second property here is the inverse, and it is a regression risk rather
than a security one: home's `local-dev` arrives from a fallback rather than a
cookie, and if its source were left out of the trusted set every home developer
would lose the admin panel to a bare 403.
"""

import pytest
from flask import Flask, g

from back_dev_home._auth import admin as admin_mod
from back_dev_home._auth.admin import is_admin, is_admin_request
from back_dev_home._auth.provider import (
    SOURCE_ANONYMOUS,
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    SOURCE_LOCAL,
    SOURCE_TOKEN,
)


@pytest.fixture
def app():
    return Flask(__name__)


@pytest.fixture(autouse=True)
def pinned_allowlist(monkeypatch):
    """Pin the allowlist so these tests do not depend on is_cloud() or on the
    developer's SKEWNONO_ADMIN_USERS."""
    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928,LOCAL-DEV")
    admin_mod._parse_allowlist.cache_clear()
    yield
    admin_mod._parse_allowlist.cache_clear()


@pytest.fixture
def as_caller(app):
    """Run the assertion inside a request context with an identity attached."""

    def _run(user_id, source=...):
        with app.test_request_context("/"):
            g.user_id = user_id
            if source is not ...:
                g.identity_source = source
            return is_admin_request()

    return _run


@pytest.mark.parametrize("source", [SOURCE_COOKIE, SOURCE_TOKEN, SOURCE_LOCAL])
def test_trusted_sources_can_hold_admin(as_caller, source):
    assert as_caller("2067928", source) is True


def test_home_local_dev_keeps_admin(as_caller):
    """The regression this refactor could introduce.

    `local-dev` arrives from the home provider's fallback, not from a cookie.
    Leaving `local` out of the trusted set would remove the admin panel from
    every home session, and the symptom — a bare 403 — points at nothing that
    would lead anyone to a source name.
    """
    assert as_caller("local-dev", SOURCE_LOCAL) is True


@pytest.mark.parametrize("source", [SOURCE_DECLARED, SOURCE_ANONYMOUS])
def test_untrusted_sources_can_never_hold_admin(as_caller, source):
    """Typing an admin's employee number into the form must not confer admin,
    even though `is_admin` alone says yes to that id."""
    assert is_admin("2067928") is True

    assert as_caller("2067928", source) is False


def test_an_unrecognized_source_is_not_trusted(as_caller):
    """The trusted set is a whitelist: a step added to the chain later holds no
    admin until someone deliberately adds it here."""
    assert as_caller("2067928", "some-future-source") is False


def test_a_missing_source_is_not_trusted(as_caller):
    """A code path that sets g.user_id without g.identity_source is a bug, and
    it must fail closed rather than inherit admin from an id alone."""
    assert as_caller("2067928") is False


def test_a_trusted_source_with_an_ordinary_id_is_not_admin(as_caller):
    assert as_caller("1234567", SOURCE_COOKIE) is False


def test_is_admin_still_answers_about_the_id_alone():
    """The two questions stay separate. `is_admin` is kept for callers that
    genuinely have only an id — the access-control rule layer, the activity
    classifier — and must not start consulting request state."""
    assert is_admin("2067928") is True
    assert is_admin("1234567") is False
    assert is_admin(None) is False
