"""Who the caller is, as an endpoint.

Registered by hand in ``create_app`` rather than by blueprint auto-discovery:
this folder is ``_``-prefixed shared plumbing, which the factory's rglob skips
on purpose.

Mounted in every phase, unlike the SPA and the old SSO login route. The SPA asks
this on boot to greet the user and to decide whether to show admin surfaces, and
a home session that could not answer it would develop against a screen the cloud
never shows.
"""

from flask import Blueprint, g, jsonify

from .admin import is_admin
from .directory import lookup_member

bp = Blueprint("auth", __name__)


@bp.get("/me")
def me():
    """The caller's identity, enriched from the member directory.

    Reached only by an identified caller: this is an ``/api/*`` path, so the
    identity gate answers 401 first for anyone without a LASTUSER cookie. That
    401 is itself the signal the SPA needs — "the page loaded but nobody knows
    who you are" — so no carve-out is added here. A gate with exemptions is how
    auth bugs get in, and this endpoint does not need one to be useful.

    ``member`` always carries an ``empno``; every other field is None when the
    directory has no row for this caller (see `directory.py`).
    """
    user_id = g.user_id
    return jsonify(
        {
            "user_id": user_id,
            "is_admin": is_admin(user_id),
            "member": lookup_member(user_id),
        }
    )
