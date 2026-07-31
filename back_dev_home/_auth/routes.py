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

import logging

from flask import Blueprint, g, jsonify, request

from .admin import is_admin_request
from .directory import lookup_member, probe_member
from .middleware import resolve_identity
from .provider import SOURCE_DECLARED
from .self_id import clear_declared, read_declared, write_declared
from .verify import decide

logger = logging.getLogger(__name__)

bp = Blueprint("auth", __name__)


def _identity_payload():
    """The one shape every identity endpoint answers with.

    ``/api/me``, an accepted declaration and a cleared one all return this, so
    the SPA has a single parser rather than an endpoint-specific branch each
    time it needs to know who it is talking to.
    """
    user_id = g.user_id
    declared = read_declared()
    member = lookup_member(user_id)
    # The stored declared name exists for exactly this payload: an `absent`
    # directory row leaves the member nameless, and the name the caller typed
    # is then the only attribution there is — without this, the header greets
    # a self-identified caller by raw empno. The directory spelling wins when
    # present (a verified declaration stored it anyway). Guarded on the
    # SOURCE, not just the session: a stale declared session must not rename
    # a caller whose identity came from a cookie.
    if (
        getattr(g, "identity_source", None) == SOURCE_DECLARED
        and declared
        and not (member.get("emp_nm") or "").strip()
    ):
        member = {**member, "emp_nm": declared["emp_nm"]}
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
        "member": member,
    }


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
    # The name is required HERE, not only in the SPA's form: the /identify
    # gate is client-side, and an `absent`/`unavailable` probe accepts without
    # a directory name to fall back on — a curl caller skipping `emp_nm` would
    # otherwise store the accepted-with-no-name state Decision rules out.
    if not entered_name:
        return jsonify({"error": "invalid_input", "message": "이름을 입력해 주세요"}), 422

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

    # An accepted-but-unverified declaration is the only record that this
    # employee number could not be confirmed, and the two reasons want
    # different attention: `absent` is an expected outcome whose RATE is the
    # open office question (spec §13 — how many people have no `members` row),
    # while `unavailable` means the directory itself is not answering.
    if decision.reason == "absent":
        logger.info(
            "declared identity %s has no members row; accepted unverified", empno
        )
    elif decision.reason == "unavailable":
        logger.warning(
            "could not verify declared identity %s: directory unavailable", empno
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
    # Re-run the chain rather than assuming `anonymous`. The declaration is
    # already gone, so its step falls through on its own, and a caller who
    # also holds a LASTUSER cookie is correctly told they are still that
    # person — which is what their next request will compute anyway.
    g.user_id, g.identity_source = resolve_identity()
    return jsonify(_identity_payload())
