from flask import Blueprint, request

from back_dev_home._auth.errors import error_json
from back_dev_home.short_links.data import create_short_link, resolve_short_link
from back_dev_home.short_links.targets import MAX_TARGET_LEN, normalize_target

bp = Blueprint("short_links", __name__)


@bp.post("/short-links")
def mint_short_link():
    """Mint (or re-find) the short link for an in-app path.

    This is the ONLY way a target enters the store, which is what lets the
    resolver trust what it reads back. normalize_target is therefore not a
    convenience check here — it is the open-redirect guard, and a refusal must
    leave nothing behind.
    """
    body = request.get_json(silent=True) or {}
    target = normalize_target(body.get("target"))
    if target is None:
        return error_json(
            "invalid_request",
            f"target must be a same-origin path starting with '/' "
            f"(max {MAX_TARGET_LEN} chars)",
            400,
        )
    return create_short_link(target), 201


@bp.get("/short-links/<code>")
def read_short_link(code: str):
    """Resolve a code for the SPA's /s/<code> page.

    A miss is a 404 with a JSON body, not a 500 and not Flask's HTML error
    page: these links live in messengers for months, so opening a stale one is
    routine and the page renders a "not found" state off this response.
    """
    link = resolve_short_link(code)
    if link is None:
        return error_json("not_found", "short link not found", 404)
    return link
