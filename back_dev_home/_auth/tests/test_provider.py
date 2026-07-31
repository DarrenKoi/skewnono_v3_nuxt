"""Identity providers: the cookie read, and the fallback that must not exist.

Both phases read `LASTUSER`. The one asymmetry — home invents `local-dev` when
the cookie is missing, the cloud invents nothing — is the security boundary,
so it gets more tests than the happy path does.
"""

import ast
from pathlib import Path

import pytest
from flask import Flask

from back_dev_home._auth.admin import is_admin
from back_dev_home._auth.provider import (
    ANONYMOUS,
    CloudIdentityProvider,
    LocalIdentityProvider,
)


@pytest.fixture
def request_with():
    """Build a real Flask request carrying the given cookies.

    A real request rather than a stub: `request.cookies` is a Werkzeug
    MultiDict populated by header parsing, and a dict-shaped fake would not
    reproduce how a blank or repeated cookie actually arrives.
    """
    app = Flask(__name__)

    def make(**cookies):
        header = "; ".join(f"{name}={value}" for name, value in cookies.items())
        ctx = app.test_request_context(
            "/", headers={"Cookie": header} if header else {}
        )
        ctx.push()
        from flask import request

        return request

    return make


@pytest.mark.parametrize(
    "provider", [LocalIdentityProvider(), CloudIdentityProvider()]
)
def test_both_phases_read_the_same_cookie(provider, request_with):
    assert provider.identify(request_with(LASTUSER="2067928")) == "2067928"


@pytest.mark.parametrize(
    "provider", [LocalIdentityProvider(), CloudIdentityProvider()]
)
def test_both_phases_accept_the_legacy_spelling(provider, request_with):
    """afm/routes.py has read both spellings since before this app existed; a
    host that sets only LAST_USER would otherwise look deserted."""
    assert provider.identify(request_with(LAST_USER="1234567")) == "1234567"


def test_the_canonical_spelling_wins_when_both_are_present(request_with):
    identity = CloudIdentityProvider().identify(
        request_with(LASTUSER="2067928", LAST_USER="9999999")
    )

    assert identity == "2067928"


def test_the_cloud_substitutes_anonymous_without_a_cookie(request_with):
    """An unidentified caller is still a real caller on an internal network, so
    they get a usable app under a shared id rather than a locked door."""
    assert CloudIdentityProvider().identify(request_with()) == ANONYMOUS


@pytest.mark.parametrize("blank", ["", "   "])
def test_the_cloud_treats_a_blank_cookie_as_anonymous(request_with, blank):
    """Infrastructure that clears the cookie by setting it empty must read as
    anonymous, not as a user whose id is the empty string — that id would flow
    into activity logs and access-control lookups as if it were a real member."""
    assert (
        CloudIdentityProvider().identify(request_with(LASTUSER=blank))
        == ANONYMOUS
    )


def test_the_cloud_never_yields_an_admin_by_default(request_with):
    """The security property the anonymous fallback rests on. `anonymous` is a
    shared id, so if it were ever admin, the admin panel would be reachable by
    anyone whose cookie is missing."""
    assert not is_admin(CloudIdentityProvider().identify(request_with()))


def test_anonymous_is_not_admin_under_either_phase_default(monkeypatch):
    """Directly, against both allowlists rather than through identify().

    admin.py picks its default set from is_cloud(), so a fallback id that is
    safe at home could still be admin on the cloud — and the test above, which
    only ever runs in one phase, would not notice.
    """
    monkeypatch.delenv("SKEWNONO_ADMIN_USERS", raising=False)

    for cloud in (True, False):
        monkeypatch.setattr(
            "back_dev_home._auth.admin.is_cloud", lambda cloud=cloud: cloud
        )
        assert not is_admin(ANONYMOUS)


def test_anonymous_is_not_x_prefixed_so_access_control_ignores_it():
    """The second, independent guard on the same property: access control
    blocks X-prefixed member ids, and `anonymous` must not resemble one."""
    assert not ANONYMOUS.upper().startswith("X")


def test_home_falls_back_to_the_local_developer(request_with):
    """The convenience that makes a fresh home browser work with no setup."""
    assert LocalIdentityProvider().identify(request_with()) == "local-dev"


def test_no_provider_imports_a_cloud_only_module():
    """The cloud identity path used to import `hcputil`, which exists only on
    the cloud image — so it could not be constructed at home, and the mismatch
    between what it probed and what the library actually offered stayed
    invisible until a deploy served a redirect loop. Nothing in this module may
    become untestable at home again.

    Read as an import graph rather than as text: prose is free to name the
    library it no longer needs, and an `importlib.import_module("hcputil...")`
    call would evade a substring check on `import` lines anyway.
    """
    source = Path(__file__).resolve().parents[1] / "provider.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not [name for name in imported if name.split(".")[0] == "hcputil"]
    # importlib is how the old loader reached it without an import statement.
    assert "importlib" not in imported
