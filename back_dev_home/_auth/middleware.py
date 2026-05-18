from flask import Flask, g, redirect, request

from ..api_tokens.data import find_by_plaintext, touch_last_used
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


def install_identity_middleware(app: Flask, provider: IdentityProvider) -> None:
    @app.before_request
    def _attach_identity():
        if _is_public(request.path):
            return None

        matched, response = _try_api_token()
        if matched:
            return response

        user_id = provider.identify(request)
        if user_id:
            g.user_id = user_id
            return None

        if request.path.startswith("/api/"):
            return error_json("unauthenticated", "SSO session required", 401)

        target = provider.login_redirect_url(request, request.path)
        if target:
            return redirect(target)
        return error_json("unauthenticated", "SSO session required", 401)
