"""Chat blueprint: models, threads CRUD, and the send-message orchestration."""

from flask import Blueprint, g, request

from back_dev_home._auth.errors import error_json
from back_dev_home.chat import config, data, llm

bp = Blueprint("chat", __name__)


def _uid() -> str:
    return getattr(g, "user_id", None) or "anon"


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
    body = request.get_json(silent=True) or {}
    content = (body.get("content") or "").strip()
    if not content:
        return error_json("bad_request", "content is required", 400)

    thread = data.get_thread(_uid(), thread_id)
    if thread is None:
        return error_json("not_found", "thread not found", 404)

    # Persist the user message BEFORE the LLM call so a failure never loses it.
    data.append_message(thread_id, "user", content)

    payload = []
    if thread.get("system_prompt"):
        payload.append({"role": "system", "content": thread["system_prompt"]})
    for m in thread["messages"]:
        payload.append({"role": m["role"], "content": m["content"]})
    payload.append({"role": "user", "content": content})

    try:
        reply = llm.send_chat(thread["model"], payload)
    except llm.ChatTimeout as exc:
        return error_json("gateway_timeout", exc.message, 504)
    except llm.ChatUpstreamError as exc:
        return error_json("bad_gateway", exc.message, 502)

    assistant = data.append_message(
        thread_id, "assistant", reply["content"],
        meta={
            "model": thread["model"],
            "prompt_tokens": reply["prompt_tokens"],
            "completion_tokens": reply["completion_tokens"],
            "latency_ms": reply["latency_ms"],
        },
    )
    return {"data": assistant}
