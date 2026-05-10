from flask import Flask, g, redirect, request

from .errors import error_json
from .provider import IdentityProvider


_PUBLIC_PREFIXES = ("/login", "/static/")


def _is_public(path: str) -> bool:
    return path == "/login" or any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def install_identity_middleware(app: Flask, provider: IdentityProvider) -> None:
    @app.before_request
    def _attach_identity():
        if _is_public(request.path):
            return None

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
