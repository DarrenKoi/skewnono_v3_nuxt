"""Thin HTTP adapters for chat threads, messages, feedback, and figures."""

from uuid import UUID

from flask import Blueprint, Response, g, request

from back_dev_home._auth.errors import error_json
from back_dev_home.chat import config, data, figures
from back_dev_home.chat.knowledge.contracts import (
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)
from back_dev_home.chat.orchestration import ThreadNotFound, orchestrator
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


@bp.get("/chat/threads")
def chat_list_threads():
    data.purge_expired(30)
    return {"data": data.list_threads(_uid())}


@bp.post("/chat/threads")
def chat_create_thread():
    """Open an empty thread. No body: the RAG owns the model and the prompt."""
    thread = data.create_thread(_uid())
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
    # The answer seam is the only thing that can fail out here, and it speaks
    # the knowledge error family: denied by access scope, no usable RAG on
    # this machine, or over the turn budget.
    except KnowledgeDenied as exc:
        return error_json("runtime_denied", str(exc), 403)
    except (ScopeUnavailable, KnowledgeUnavailable) as exc:
        return error_json("runtime_unavailable", str(exc), 503)
    except KnowledgeTimeout as exc:
        return error_json("gateway_timeout", str(exc), 504)
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
    data.delete_feedback(_uid(), message_id)
    return {"data": {"id": message_id, "feedback": None}}


@bp.get("/chat/figures/<figure_id>")
def chat_figure(figure_id):
    """Serve one extracted manual figure.

    Authorization is the identity gate on ``/api/*`` and nothing more. Noted
    risk, carried over from the agreed design: retrieval is filtered by
    ``AccessScope`` but this endpoint is not, so a user who knows a figure_id
    can fetch the figure of a manual outside their group. Revisit if figures
    are found to carry access-restricted content.
    """
    payload = figures.read_figure(figure_id)
    if payload is None:
        return error_json("not_found", "figure not found", 404)
    return Response(
        payload,
        mimetype="image/webp",
        headers={"Cache-Control": "public, max-age=3600"},
    )
