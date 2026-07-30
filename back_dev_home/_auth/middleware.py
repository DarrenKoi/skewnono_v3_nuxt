from flask import Flask, g, redirect, request

from ..access_control.data import is_blocked, record_denied
from ..api_tokens.data import find_by_plaintext, touch_last_used
from .admin import is_admin
from .errors import error_json
from .provider import IdentityProvider


_PUBLIC_PREFIXES = ("/login", "/static/")
_BEARER_PREFIX = "Bearer "


def _is_public(path: str) -> bool:
    return path == "/login" or any(path.startswith(p) for p in _PUBLIC_PREFIXES)


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
    # would cost an HEXISTS per asset (/_nuxt/*.js, favicon, ...), since
    # _is_public only exempts /login and /static/ and everything else reaches
    # the catch-all SPA route.
    if not request.path.startswith("/api/"):
        return None
    # is_blocked before is_admin: non-X ids (nearly everyone) short-circuit on a
    # prefix check without touching the admin allowlist or the exception store.
    if not is_blocked(user_id) or is_admin(user_id):
        return None
    record_denied(user_id)
    return error_json("access_denied", "member id is not allowed to access this service", 403)


def install_identity_middleware(app: Flask, provider: IdentityProvider) -> None:
    @app.before_request
    def _attach_identity():
        if _is_public(request.path):
            return None

        matched, response = _try_api_token()
        if matched:
            return response or _deny_if_blocked()

        user_id = provider.identify(request)
        if user_id:
            g.user_id = user_id
            return _deny_if_blocked()

        if request.path.startswith("/api/"):
            return error_json("unauthenticated", "SSO session required", 401)

        target = provider.login_redirect_url(request, request.path)
        if target:
            return redirect(target)
        return error_json("unauthenticated", "SSO session required", 401)
