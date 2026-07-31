"""Who the caller is, as an endpoint.

Registered by hand in ``create_app`` rather than by blueprint auto-discovery:
this folder is ``_``-prefixed shared plumbing, which the factory's rglob skips
on purpose.

Mounted in every phase, unlike the SPA and the old SSO login route. The SPA asks
this on boot to greet the user and to decide whether to show admin surfaces, and
a home session that could not answer it would develop against a screen the cloud
never shows.

``/identify`` gets **no carve-out** in the identity gate, and needs none: every
phase substitutes an identity for a caller no cookie named, so an unidentified
visitor arrives here as an ordinary identified request. A gate with exemptions
is how this repository's last auth bug got in.
"""

from flask import Blueprint, current_app, g, jsonify, request

from .admin import is_admin_request
from .directory import lookup_member, probe_member
from .middleware import IDENTITY_PROVIDER_KEY
from .provider import (
    ANONYMOUS,
    SOURCE_ANONYMOUS,
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    read_identity_cookie,
)
from .self_id import clear_declared, read_declared, write_declared
from .verify import decide

bp = Blueprint("auth", __name__)


def _identity_payload():
    """The one shape every identity endpoint answers with.

    ``/api/me``, an accepted declaration and a cleared one all return this, so
    the SPA has a single parser rather than an endpoint-specific branch each
    time it needs to know who it is talking to.
    """
    user_id = g.user_id
    declared = read_declared()
    return {
        "user_id": user_id,
        "identity_source": getattr(g, "identity_source", None),
        # is_admin_request, NOT is_admin: the latter answers "is this id an
        # admin", which is true for a declared identity that typed an admin's
        # employee number. The server refuses those calls either way, but
        # rendering the admin surfaces at all invites the bug report.
        "is_admin": is_admin_request(),
        # Only meaningful for a declared identity. A cookie identity is not
        # "verified" — it is authoritative, which is a stronger thing.
        "verified": bool(declared and declared["verified"]),
        "member": lookup_member(user_id),
    }


def _identity_without_a_declaration():
    """Who the caller is once their declaration is gone.

    Re-runs the two chain steps that can still apply — a cookie, then this
    phase's fallback — so the DELETE response describes the identity the next
    request will actually compute rather than assuming `anonymous`.
    """
    cookie = read_identity_cookie(request)
    if cookie:
        return cookie, SOURCE_COOKIE

    provider = current_app.extensions.get(IDENTITY_PROVIDER_KEY)
    if provider is None:
        # The blueprint mounted without the gate. Not a configuration this app
        # ships, but answering with the safest identity beats raising.
        return ANONYMOUS, SOURCE_ANONYMOUS
    return provider.fallback_identity()


@bp.get("/me")
def me():
    """The caller's identity, enriched from the member directory.

    Always reachable: every phase substitutes an identity for an unidentified
    caller, so there is nobody for this endpoint to refuse. ``member`` always
    carries an ``empno``; every other field is None when the directory has no
    row for this caller (see `directory.py`).
    """
    return jsonify(_identity_payload())


@bp.post("/identify")
def identify():
    """Accept an employee number and name the caller typed for themselves."""
    body = request.get_json(silent=True) or {}
    empno = str(body.get("empno") or "").strip()
    entered_name = str(body.get("emp_nm") or "").strip()

    if not empno:
        return jsonify({"error": "invalid_input", "message": "사번을 입력해 주세요"}), 422

    decision = decide(probe_member(empno), entered_name)
    if not decision.accept:
        # One message whatever the reason, so the response cannot be used to
        # ask which employee numbers the directory holds.
        return (
            jsonify(
                {
                    "error": "not_verified",
                    "message": "사번 또는 이름이 확인되지 않습니다",
                }
            ),
            422,
        )

    write_declared(
        empno=empno,
        emp_nm=decision.emp_nm,
        verified=decision.verified,
        declared_from=request.remote_addr,
    )
    # Re-point this request's own identity, so the payload below describes the
    # caller they just became rather than the anonymous one they arrived as.
    g.user_id = empno
    g.identity_source = SOURCE_DECLARED
    return jsonify(_identity_payload())


@bp.delete("/identify")
def unidentify():
    """"본인이 아닙니다" — drop the declaration.

    Safe when there is none: this is reachable from a page whose session may
    already have expired, and an error on a button meaning "undo" is worse than
    a no-op.
    """
    clear_declared()
    g.user_id, g.identity_source = _identity_without_a_declaration()
    return jsonify(_identity_payload())
