"""Thin HTTP adapters for chat models, threads, messages, and feedback."""

from uuid import UUID

from flask import Blueprint, g, request

from back_dev_home._auth.errors import error_json
from back_dev_home.chat import config, data, guard, llm
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


def _owned_message(user_id, message_id):
    for summary in data.list_threads(user_id):
        thread = data.get_thread(user_id, summary["id"])
        if thread is None:
            continue
        for message in thread["messages"]:
            if message["id"] == message_id:
                return message
    return None


def _missing_feedback_target(user_id, message_id):
    message = _owned_message(user_id, message_id)
    if message is not None and message["role"] != "assistant":
        return error_json(
            "bad_request", "feedback is only supported for assistant messages", 400
        )
    return error_json("not_found", "message not found", 404)


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
    except RuntimeLimitExceeded as exc:
        return error_json("runtime_limit_exceeded", str(exc), 422)
    except guard.ChatEgressBlocked as exc:
        return error_json("egress_blocked", exc.message, 403)
    except llm.ChatTimeout as exc:
        return error_json("gateway_timeout", exc.message, 504)
    except llm.ChatUpstreamError as exc:
        return error_json("bad_gateway", exc.message, 502)
    return {"data": assistant}


@bp.put("/chat/messages/<message_id>/feedback")
def chat_put_feedback(message_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_json("bad_request", "request body must be an object", 400)
    feedback = _feedback_input(body)
    if feedback is None:
        return error_json("bad_request", "invalid feedback", 400)
    stored = data.put_feedback(_uid(), message_id, feedback)
    if stored is None:
        return _missing_feedback_target(_uid(), message_id)
    return {"data": stored}


@bp.delete("/chat/messages/<message_id>/feedback")
def chat_delete_feedback(message_id):
    if data.delete_feedback(_uid(), message_id):
        return {"data": {"id": message_id, "feedback": None}}
    message = _owned_message(_uid(), message_id)
    if message is None:
        return error_json("not_found", "message not found", 404)
    if message["role"] != "assistant":
        return error_json(
            "bad_request", "feedback is only supported for assistant messages", 400
        )
    return {"data": {"id": message_id, "feedback": None}}
