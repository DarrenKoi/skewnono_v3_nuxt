"""Thin HTTP adapters for chat models, threads, messages, and feedback."""

import re
from pathlib import Path
from uuid import UUID

from flask import Blueprint, Response, g, request

from back_dev_home._auth.errors import error_json
from back_dev_home.chat import config, data, guard
from back_dev_home.chat.orchestration import (
    ModelDoesNotSupportTools,
    ThreadNotFound,
    orchestrator,
)
from back_dev_home.chat.runtime.contracts import (
    RuntimeDenied,
    RuntimeLimitExceeded,
    RuntimeTimeout,
    RuntimeUnavailable,
    RuntimeUpstreamError,
)
from back_dev_home.chat.scope.contracts import ScopeUnavailable

bp = Blueprint("chat", __name__)

_FEEDBACK_RATINGS = {"up", "down"}
_FEEDBACK_REASONS = {
    "incorrect",
    "insufficient_evidence",
    "wrong_source",
    "outdated",
    "unclear",
    "incorrect_scope_rejection",
    "other",
}


def _uid() -> str:
    return getattr(g, "user_id", None) or "anon"


def _canonical_uuid(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _feedback_input(body):
    rating = body.get("rating")
    reasons = body.get("reasons")
    comment = body.get("comment")
    if not isinstance(rating, str) or rating not in _FEEDBACK_RATINGS:
        return None
    if not isinstance(reasons, list) or any(
        not isinstance(reason, str) or reason not in _FEEDBACK_REASONS
        for reason in reasons
    ):
        return None
    if comment is not None and (not isinstance(comment, str) or len(comment) > 500):
        return None
    if isinstance(comment, str):
        comment = comment.strip() or None
    return {"rating": rating, "reasons": reasons, "comment": comment}


def _feedback_target_error(user_id, message_id):
    message = data.get_owned_message(user_id, message_id)
    if message is None:
        return error_json("not_found", "message not found", 404)
    if message["role"] != "assistant":
        return error_json(
            "bad_request", "feedback is only supported for assistant messages", 400
        )
    return None


@bp.get("/chat/availability")
def chat_availability():
    """Whether the SPA should render the chat page or a not-in-service notice.

    Deployment shape is not knowable to the SPA — one bundle ships to all
    three phases — so the frontend has to be told rather than branch on the
    phase itself. Its own endpoint rather than a field on ``/api/me``: that
    payload is shared by three identity endpoints and this is not identity,
    and the chat page is the only caller, so it costs nothing on app boot.

    Carries no reason string. "Why" is deployment detail and the SPA shows
    the same notice either way.
    """
    return {"data": {"available": not config.is_under_development()}}


@bp.get("/chat/models")
def chat_models():
    return {"data": config.list_models()}


@bp.get("/chat/threads")
def chat_list_threads():
    data.purge_expired(30)
    return {"data": data.list_threads(_uid())}


@bp.post("/chat/threads")
def chat_create_thread():
    body = request.get_json(silent=True) or {}
    model = body.get("model")
    if not model:
        return error_json("bad_request", "model is required", 400)
    thread = data.create_thread(_uid(), model, body.get("system_prompt"))
    thread["messages"] = []
    return {"data": thread}, 201


@bp.get("/chat/threads/<thread_id>")
def chat_get_thread(thread_id):
    thread = data.get_thread(_uid(), thread_id)
    if thread is None:
        return error_json("not_found", "thread not found", 404)
    return {"data": thread}


@bp.patch("/chat/threads/<thread_id>")
def chat_rename_thread(thread_id):
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return error_json("bad_request", "title is required", 400)
    if not data.rename_thread(_uid(), thread_id, title):
        return error_json("not_found", "thread not found", 404)
    return {"data": {"id": thread_id, "title": title}}


@bp.delete("/chat/threads/<thread_id>")
def chat_delete_thread(thread_id):
    if not data.delete_thread(_uid(), thread_id):
        return error_json("not_found", "thread not found", 404)
    return {"data": {"id": thread_id, "deleted": True}}


@bp.post("/chat/threads/<thread_id>/messages")
def chat_send_message(thread_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_json("bad_request", "request body must be an object", 400)
    raw_content = body.get("content")
    if not isinstance(raw_content, str) or not raw_content.strip():
        return error_json("bad_request", "content is required", 400)
    content = raw_content.strip()
    request_id = body.get("request_id")
    if not _canonical_uuid(request_id):
        return error_json("bad_request", "request_id must be a canonical UUID", 400)
    try:
        assistant = orchestrator.send_message(_uid(), thread_id, content, request_id)
    except ThreadNotFound as exc:
        return error_json("not_found", str(exc), 404)
    except ModelDoesNotSupportTools as exc:
        return error_json("bad_request", str(exc), 400)
    except RuntimeDenied as exc:
        return error_json("runtime_denied", str(exc), 403)
    except (RuntimeUnavailable, ScopeUnavailable) as exc:
        return error_json("runtime_unavailable", str(exc), 503)
    except RuntimeTimeout as exc:
        return error_json("gateway_timeout", str(exc), 504)
    except RuntimeUpstreamError as exc:
        return error_json("bad_gateway", str(exc), 502)
    except RuntimeLimitExceeded as exc:
        return error_json("runtime_limit_exceeded", str(exc), 422)
    except guard.ChatEgressBlocked as exc:
        return error_json("egress_blocked", exc.message, 403)
    return {"data": assistant}


@bp.put("/chat/messages/<message_id>/feedback")
def chat_put_feedback(message_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_json("bad_request", "request body must be an object", 400)
    feedback = _feedback_input(body)
    if feedback is None:
        return error_json("bad_request", "invalid feedback", 400)
    target_error = _feedback_target_error(_uid(), message_id)
    if target_error is not None:
        return target_error
    stored = data.put_feedback(_uid(), message_id, feedback)
    if stored is None:
        return error_json("not_found", "message not found", 404)
    return {"data": stored}


@bp.delete("/chat/messages/<message_id>/feedback")
def chat_delete_feedback(message_id):
    target_error = _feedback_target_error(_uid(), message_id)
    if target_error is not None:
        return target_error
    if data.delete_feedback(_uid(), message_id):
        return {"data": {"id": message_id, "feedback": None}}
    return {"data": {"id": message_id, "feedback": None}}


# The office derives a figure id as ``{doc_id}_p{page}_i{idx}``, and real
# doc_ids carry dots — ``CG6300_1.HHTSEM_SYSTEM_p100_i0`` (office 확인
# 2026-08-19). The charset therefore admits ``.``, which the original design
# did not; without it every office figure 404s while every mock fixture keeps
# passing, so the failure would only ever show up at the office.
_FIGURE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _figure_path(figure_id: str) -> Path | None:
    """The stored path for a figure id, or ``None`` if it must not be served.

    Validation happens before any storage call, not after: on the Phase 2
    MinIO path a malformed id would otherwise cost a network round trip to
    learn what the charset already knows.
    """
    figures_dir = config.get_figures_dir()
    if figures_dir is None:
        return None
    if not _FIGURE_ID.match(figure_id) or ".." in figure_id:
        return None
    # Admitting ``.`` means ``..`` is no longer excluded by the charset alone,
    # so it is refused by name above. Routing already refuses anything with a
    # slash, and the containment check below is the backstop for both — it
    # also catches a figure symlinked out of the store.
    root = Path(figures_dir).resolve()
    path = (root / f"{figure_id}.webp").resolve()
    return path if path.parent == root else None


@bp.get("/chat/figures/<figure_id>")
def chat_figure(figure_id):
    """Serve one extracted manual figure.

    Authorization is the identity gate on ``/api/*`` and nothing more. Noted
    risk, carried over from the agreed design: retrieval is filtered by
    ``AccessScope`` but this endpoint is not, so a user who knows a figure_id
    can fetch the figure of a manual outside their group. Revisit if figures
    are found to carry access-restricted content.
    """
    path = _figure_path(figure_id)
    if path is None:
        return error_json("not_found", "figure not found", 404)
    try:
        payload = path.read_bytes()
    except OSError:
        return error_json("not_found", "figure not found", 404)
    return Response(
        payload,
        mimetype="image/webp",
        headers={"Cache-Control": "public, max-age=3600"},
    )
