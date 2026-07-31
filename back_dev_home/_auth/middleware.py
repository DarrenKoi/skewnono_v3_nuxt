from typing import Optional

from flask import Flask, current_app, g, request

from ..access_control.data import is_blocked, record_denied
from ..api_tokens.data import find_by_plaintext, touch_last_used
from .admin import is_admin_request
from .errors import error_json
from .provider import (
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    SOURCE_TOKEN,
    IdentityProvider,
    read_identity_cookie,
)
from .self_id import read_declared


_BEARER_PREFIX = "Bearer "


def _try_api_token():
    """Authenticate via Authorization: Bearer skn_... on /api/* requests.

    Returns (matched, response):
      matched=False           → no Authorization header, fall through to SSO
      matched=True, response=None → token accepted, request proceeds
      matched=True, response=<401> → token present but invalid; do not redirect
    """
    if not request.path.startswith("/api/"):
        return False, None
    auth = request.headers.get("Authorization", "")
    if not auth.startswith(_BEARER_PREFIX):
        return False, None
    plaintext = auth[len(_BEARER_PREFIX):].strip()
    row = find_by_plaintext(plaintext)
    if row is None:
        return True, error_json("invalid_token", "API token invalid or revoked", 401)
    g.user_id = row.owner_user_id
    g.identity_source = SOURCE_TOKEN
    g.api_token_id = row.id
    touch_last_used(row.id)
    return True, None


def _deny_if_blocked():
    """X-prefixed member ids are blocked unless granted an exception.

    Only /api/* is denied — the SPA HTML must still load so the frontend
    can render the friendly access-denied screen. Admins always pass.
    """
    user_id = getattr(g, "user_id", None)
    if not user_id:
        return None
    # Path check FIRST, because only /api/* can be denied — every other path
    # returns None regardless of the verdict, so computing one is pure waste.
    # This matters now that the office access_control provider makes is_blocked
    # a Redis round trip: without this, one cold SPA page load by an X-member
    # would cost an HEXISTS per asset (/_nuxt/*.js, favicon, ...), since every
    # non-API path reaches the catch-all SPA route.
    if not request.path.startswith("/api/"):
        return None
    # is_blocked first: non-X ids (nearly everyone) short-circuit on a prefix
    # check without touching the admin allowlist or the exception store.
    #
    # is_admin_request, not is_admin: the admin exemption below must not be
    # reachable by declaring an X-prefixed admin's employee number, which an
    # id-only check would have granted.
    if not is_blocked(user_id) or is_admin_request():
        return None
    record_denied(user_id)
    return error_json("access_denied", "member id is not allowed to access this service", 403)


# Where the installed provider is parked so routes can ask what THIS phase
# substitutes for an unidentified caller. `DELETE /api/identify` needs it to
# describe the identity its own response leaves the caller with, and deciding
# that from is_cloud() a second time would be a second place to get the
# phase split wrong.
IDENTITY_PROVIDER_KEY = "skewnono_identity_provider"


def resolve_identity() -> tuple[Optional[str], Optional[str]]:
    """Steps 2-4 of the chain: cookie, declared session, per-phase fallback.

    The API token step is deliberately outside — it can answer with a 401,
    which is a response rather than an identity, and folding it in would give
    this function two return kinds.

    Public because ``DELETE /api/identify`` needs the same answer this hook
    computes. Having it call this rather than re-deriving the steps is what
    keeps "who is the caller once the declaration is gone" from becoming a
    second, drifting copy of the precedence rules: clearing the session makes
    the declared step fall through here on its own.
    """
    cookie = read_identity_cookie(request)
    if cookie:
        return cookie, SOURCE_COOKIE

    # The identity the user typed in for themselves. Below the cookie on
    # purpose: infrastructure identity outranks a declared one, so someone who
    # is later given a real cookie stops being their own declaration without
    # having to clear anything.
    declared = read_declared()
    if declared:
        return declared["empno"], SOURCE_DECLARED

    # Nobody was identified, so the phase decides what that means: a stand-in
    # developer at home, `anonymous` on the cloud.
    provider = current_app.extensions.get(IDENTITY_PROVIDER_KEY)
    if provider is None:
        return None, None
    return provider.fallback_identity()


def install_identity_middleware(app: Flask, provider: IdentityProvider) -> None:
    app.extensions[IDENTITY_PROVIDER_KEY] = provider

    @app.before_request
    def _attach_identity():
        matched, response = _try_api_token()
        if matched:
            return response or _deny_if_blocked()

        user_id, source = resolve_identity()
        if user_id:
            g.user_id = user_id
            g.identity_source = source
            return _deny_if_blocked()

        # Nobody identified. Data is refused, but the page is not: this hook is
        # the app's first before_request, so returning a response here answers
        # index.html and every bundle with it, and the visitor gets a blank
        # window instead of a UI that could explain itself. Phase 3 shipped a
        # redirect on this line once and the browser looped between the app and
        # SSO until it gave up. Falling through hands the request to the SPA
        # mount; /api/* stays 401 and the frontend renders that.
        if request.path.startswith("/api/"):
            return error_json(
                "unauthenticated", "member identity cookie missing", 401
            )
        return None
