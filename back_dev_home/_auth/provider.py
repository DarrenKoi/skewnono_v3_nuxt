"""Who the caller is, in one place, per phase.

Both phases read the same cookie. The company infrastructure sets `LASTUSER`
(the legacy AFM app has read it since before this app existed —
`afm/routes.py:196`), so the cloud needs no SSO library of its own: there is
nothing `hcputil` could tell us about the caller that the cookie does not.

The phases differ in exactly one thing — what an *absent* cookie means — and
that difference is the security boundary, so the two classes stay separate
rather than sharing a `default=` argument someone could pass the wrong way.
"""

from typing import Optional, Protocol

from flask import Request

# Order IS the precedence, and it is user-confirmed (2026-07-31): LASTUSER wins.
# LAST_USER stays as a second spelling because afm/routes.py has always accepted
# either, and a host setting only that one would look exactly like "nobody is
# logged in" — a failure with no distinguishing symptom to debug from.
_IDENTITY_COOKIES = ("LASTUSER", "LAST_USER")


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
    """Phase 3: the cookie, or nobody.

    Returning None is the whole point of this class existing separately. A
    fallback id here would be handed to every unidentified visitor on the
    private cloud, and if it ever matched the admin allowlist it would hand out
    the admin panel with it. Unidentified must stay unidentified; the gate in
    `middleware.py` decides what an unidentified caller may still reach.
    """

    def identify(self, request: Request) -> Optional[str]:
        return _cookie_identity(request)
