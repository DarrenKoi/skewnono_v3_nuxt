from flask import Blueprint, abort, redirect, request

from .provider import CloudIdentityProvider

bp = Blueprint("auth", __name__)

_provider = None


def _get_provider() -> CloudIdentityProvider:
    global _provider
    if _provider is None:
        _provider = CloudIdentityProvider()
    return _provider


@bp.route("/login", defaults={"sub_path": ""})
@bp.route("/login/<path:sub_path>")
def login(sub_path: str):
    next_path = ("/" + sub_path) if sub_path else (request.args.get("next") or "/")
    target = _get_provider().login_redirect_url(request, next_path)
    if not target:
        abort(503, description="SSO unavailable")
    return redirect(target)
