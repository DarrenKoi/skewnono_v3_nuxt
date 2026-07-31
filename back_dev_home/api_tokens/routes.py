from functools import wraps

from flask import Blueprint, g, request

from back_dev_home._auth.errors import error_json
from back_dev_home.api_tokens.data import (
    create_token,
    list_tokens,
    revoke_token,
)

bp = Blueprint("api_tokens", __name__)


def _reject_token_auth(view):
    """Refuse callers that authenticated WITH an API token.

    A token-authenticated caller minting more tokens would defeat revocation,
    and a leaked token must not be able to revoke its siblings — so token
    management stays human-session-only (cookie/declared identity).
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        if getattr(g, "api_token_id", None):
            return error_json("forbidden", "API tokens cannot manage tokens", 403)
        return view(*args, **kwargs)

    return wrapper


@bp.get("/account/api-tokens")
def list_api_tokens():
    return {"tokens": list_tokens(g.user_id)}


@bp.post("/account/api-tokens")
@_reject_token_auth
def create_api_token():
    body = request.get_json(silent=True) or {}
    label = (body.get("label") or "").strip()
    if not label:
        return error_json("invalid_request", "label is required", 400)
    if len(label) > 80:
        return error_json("invalid_request", "label too long (max 80)", 400)
    view, plaintext = create_token(g.user_id, label)
    return {"token": view, "plaintext": plaintext}, 201


@bp.delete("/account/api-tokens/<token_id>")
@_reject_token_auth
def revoke_api_token(token_id: str):
    if not revoke_token(g.user_id, token_id):
        return error_json("not_found", "token not found", 404)
    return {"revoked": token_id}
