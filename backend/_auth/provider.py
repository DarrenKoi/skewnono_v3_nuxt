"""Who the caller is, in one place, per phase.

Both phases read the same cookie. The company infrastructure sets `LASTUSER`
(the legacy AFM app has read it since before this app existed —
`afm/routes.py:196`), so the cloud needs no SSO library of its own: there is
nothing `hcputil` could tell us about the caller that the cookie does not.

**Reading the cookie is not a provider's job.** It is one step of a four-step
chain the middleware owns, and the declared session (`self_id.py`) sits between
the cookie and the fallback below — so an object owning both ends would leave
no seam for the middle step to occupy. `read_identity_cookie` is a plain
function here; the middleware calls it.

What is left on the providers is the one thing that genuinely differs per
phase: what an *absent* cookie means. That difference is the security boundary,
so the two classes stay separate rather than sharing a `default=` argument
someone could pass the wrong way. Home substitutes a developer (`local-dev`, an
admin); the cloud substitutes `anonymous`, which is nobody in particular and
must never be anybody important.

Each fallback also names its own source. That name is what `admin.py` reads to
decide whether an identity may hold admin at all, and it is why home's
`local-dev` — which arrives from a fallback rather than a cookie — can stay an
admin without the middleware having to pretend it saw a cookie.
"""

from typing import Optional, Protocol

from flask import Request

# Order IS the precedence, and it is user-confirmed (2026-07-31): LASTUSER wins.
# LAST_USER stays as a second spelling because afm/routes.py has always accepted
# either, and a host setting only that one would look exactly like "nobody is
# logged in" — a failure with no distinguishing symptom to debug from.
_IDENTITY_COOKIES = ("LASTUSER", "LAST_USER")

# The id a cloud caller gets when no cookie identifies them. Spelled the same
# as afm/routes.py:196 so one person browsing both apps unauthenticated is one
# id in the logs rather than two.
ANONYMOUS = "anonymous"

# The five ways a request can acquire an identity — the vocabulary of
# `g.identity_source`. They live together because `admin.py` compares against a
# subset of them to decide who may be an admin, and a name that drifted out of
# sync with that set would silently grant or revoke authority.
SOURCE_TOKEN = "token"
SOURCE_COOKIE = "cookie"
SOURCE_DECLARED = "declared"
SOURCE_LOCAL = "local"
SOURCE_ANONYMOUS = ANONYMOUS


def read_identity_cookie(request: Request) -> Optional[str]:
    """The employee number the infrastructure put on this request, if any.

    Returns None rather than a substitute: choosing the substitute belongs to
    whichever provider is installed, and the two phases choose differently.

    A blank value counts as absent. Infrastructure that clears the cookie by
    setting it empty must read as nobody rather than as a user whose id is the
    empty string — that id would flow into activity logs and access-control
    lookups as though it were a real member.
    """
    for name in _IDENTITY_COOKIES:
        value = (request.cookies.get(name) or "").strip()
        if value:
            return value
    return None


class IdentityProvider(Protocol):
    def fallback_identity(self) -> tuple[str, str]:
        """`(user_id, identity_source)` for a caller no cookie identified."""
        ...


class LocalIdentityProvider:
    """Home and office-localhost: a stand-in developer.

    The `local-dev` fallback is a convenience — a fresh browser needs no setup
    to reach the app — and it is an admin id (`_auth/admin.py`). That is
    deliberately absent from the cloud provider below.

    Its source is `local` rather than `cookie` for a reason worth stating: the
    id did not come from a cookie, and labelling it as though it had would make
    `identity_source` lie about the one thing it exists to report. Giving it a
    name of its own lets `admin.py` trust it explicitly — safe, because this
    provider is installed only when `is_cloud()` is false, so `local` cannot
    appear on the cloud at all.
    """

    def fallback_identity(self) -> tuple[str, str]:
        return ("local-dev", SOURCE_LOCAL)


class CloudIdentityProvider:
    """Phase 3: `anonymous`.

    Same convention `afm/routes.py:196` has always used. An unidentified caller
    is a real caller on the private cloud — the network is already internal —
    so they get a usable app rather than a locked door, and the activity log
    gets a name for the traffic instead of a null.

    `anonymous` is a shared id, not an identity: it must never be admin. Three
    independent things keep that true — it is absent from both allowlists in
    `admin.py`, it is not X-prefixed so access control ignores it, and its
    source name is outside `admin.py`'s trusted set — and a test pins each. Do
    not add it to `SKEWNONO_ADMIN_USERS`.
    """

    def fallback_identity(self) -> tuple[str, str]:
        return (ANONYMOUS, SOURCE_ANONYMOUS)
