"""Who the caller is, in one place, per phase.

Both phases read the same cookie. The company infrastructure sets `LASTUSER`
(the legacy AFM app has read it since before this app existed —
`afm/routes.py:196`), so the cloud needs no SSO library of its own: there is
nothing `hcputil` could tell us about the caller that the cookie does not.

The phases differ in exactly one thing — what an *absent* cookie means — and
that difference is the security boundary, so the two classes stay separate
rather than sharing a `default=` argument someone could pass the wrong way.
Home substitutes a developer (`local-dev`, an admin); the cloud substitutes
`anonymous`, which is nobody in particular and must never be anybody important.
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


class IdentityProvider(Protocol):
    def identify(self, request: Request) -> Optional[str]: ...


def _cookie_identity(request: Request) -> Optional[str]:
    for name in _IDENTITY_COOKIES:
        value = (request.cookies.get(name) or "").strip()
        if value:
            return value
    return None


class LocalIdentityProvider:
    """Home and office-localhost: the cookie, or a stand-in developer.

    The `local-dev` fallback is a convenience — a fresh browser needs no setup
    to reach the app — and it is an admin id (`_auth/admin.py`). That is
    deliberately absent from the cloud provider below.
    """

    def identify(self, request: Request) -> Optional[str]:
        return _cookie_identity(request) or "local-dev"


class CloudIdentityProvider:
    """Phase 3: the cookie, or `anonymous`.

    Same convention `afm/routes.py:196` has always used. An unidentified caller
    is a real caller on the private cloud — the network is already internal —
    so they get a usable app rather than a locked door, and the activity log
    gets a name for the traffic instead of a null.

    `anonymous` is a shared id, not an identity: it must never be admin. Two
    independent things keep that true — it is absent from both allowlists in
    `admin.py`, and it is not X-prefixed so access control ignores it — and a
    test pins the first. Do not add it to `SKEWNONO_ADMIN_USERS`.
    """

    def identify(self, request: Request) -> Optional[str]:
        return _cookie_identity(request) or ANONYMOUS
