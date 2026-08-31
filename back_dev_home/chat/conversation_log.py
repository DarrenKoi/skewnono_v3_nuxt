"""Ship completed chat turns to the dedicated conversation index.

Conversation content is deliberately barred from the activity logging index
(``skewnono_logging``), so completed turns get their own alias family
(``skewnono_chat_logging`` / ``_local``, provisioned by
``ops_index_mgmt/skewnono_chat_logging.py``) with separate retention. The
transport reuses the buffered, retrying :class:`OpenSearchBulkHandler`
pipeline; only the document schema differs. The logger never propagates, so
a turn document can never leak into the activity index through root.
"""

import logging
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Mapping

from back_dev_home._logging.opensearch_handler import (
    _logging_disabled,
    OpenSearchBulkHandler,
    _startup_preflight,
)
from back_dev_home._logging.target import (
    LoggingConfigurationError,
    LoggingTarget,
    resolve_chat_conversation_target,
)
from back_dev_home._runtime.data_provider import get_mode

CONVERSATION_LOGGER_NAME = "skewnono.chat.conversation"

# Bounds mirror the handler's own bounded-document principle: a runaway
# content blob must not be able to reject a whole bulk batch.
CONTENT_LIMIT = 8_000

logger = logging.getLogger(CONVERSATION_LOGGER_NAME)
# Without this, every turn record would also reach root — at the office that
# is the activity index handler, which would store a junk row per turn.
logger.propagate = False


class ChatConversationHandler(OpenSearchBulkHandler):
    """Bulk-index conversation documents built by :func:`build_turn_document`."""

    def _record_to_doc(self, record: logging.LogRecord) -> dict[str, Any]:
        conversation = getattr(record, "conversation", None)
        if not isinstance(conversation, Mapping):
            raise TypeError("chat conversation record has no payload")
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        doc: dict[str, Any] = {
            "event_id": str(self._uuid_factory()),
            "@timestamp": ts,
            "service": "skewnono",
            "deployment": self._deployment,
            "host": self._host,
        }
        doc.update({key: value for key, value in conversation.items() if value is not None})
        return doc


def build_turn_document(
    *,
    user_id: str,
    user_content: str,
    assistant: Mapping[str, Any],
    decision: Mapping[str, Any],
    tool_call_count: int,
) -> dict[str, Any]:
    """One flat document per completed turn, keys ⊆ the index mapping."""
    sources = assistant.get("sources") or []
    return {
        "user_id": user_id,
        "thread_id": assistant.get("thread_id"),
        "request_id": assistant.get("request_id"),
        "message_id": assistant.get("id"),
        "model": assistant.get("model"),
        "runtime": assistant.get("runtime"),
        "scope_status": assistant.get("scope_status") or decision.get("status"),
        "scope_reason_code": decision.get("reason_code"),
        "user_content": user_content[:CONTENT_LIMIT],
        "assistant_content": str(assistant.get("content") or "")[:CONTENT_LIMIT],
        "prompt_tokens": assistant.get("prompt_tokens"),
        "completion_tokens": assistant.get("completion_tokens"),
        "latency_ms": assistant.get("latency_ms"),
        "source_count": len(sources),
        "source_ids": [
            source["source_id"]
            for source in sources
            if isinstance(source, Mapping) and source.get("source_id")
        ],
        "tool_call_count": tool_call_count,
    }


def record_turn(
    *,
    user_id: str,
    user_content: str,
    assistant: Mapping[str, Any],
    decision: Mapping[str, Any],
    tool_call_count: int,
) -> None:
    """Emit one conversation document. Delivery is asynchronous and lossy-safe."""
    document = build_turn_document(
        user_id=user_id,
        user_content=user_content,
        assistant=assistant,
        decision=decision,
        tool_call_count=tool_call_count,
    )
    logger.info("chat turn", extra={"conversation": document})


def installed_conversation_handler() -> ChatConversationHandler | None:
    """The conversation shipper attached by install(), if any."""
    return next(
        (
            handler
            for handler in logger.handlers
            if isinstance(handler, ChatConversationHandler)
        ),
        None,
    )


def install_chat_conversation_logging(
    *,
    target: LoggingTarget | None = None,
    level: int = logging.INFO,
) -> ChatConversationHandler | None:
    """Attach the conversation shipper, gated exactly like activity logging."""

    if _logging_disabled(os.environ):
        return None
    if target is None and get_mode() != "office":
        # Same reasoning as install_opensearch_logging: only deployments that
        # really ship logs resolve an ambient target; a home .env carrying
        # office OPENSEARCH_* lines must not start a worker that retries an
        # unreachable host forever. Explicit `target=` bypasses on purpose.
        return None
    if not os.environ.get("OPENSEARCH_PASSWORD"):
        sys.stderr.write(
            "[opensearch-log] OPENSEARCH_PASSWORD not set; "
            "skipping chat conversation handler\n"
        )
        return None

    actual_target = target or resolve_chat_conversation_target()
    existing = installed_conversation_handler()
    if existing is not None:
        if (
            existing.index != actual_target.alias
            or existing.deployment != actual_target.deployment
        ):
            raise LoggingConfigurationError(
                "existing chat conversation logging target does not match "
                f"{actual_target.environment}"
            )
        return existing

    from ops_store import create_client

    handler = ChatConversationHandler(
        client_factory=create_client,
        index=actual_target.alias,
        deployment=actual_target.deployment,
        level=level,
    )
    logger.addHandler(handler)
    if logger.level == logging.NOTSET or logger.level > level:
        logger.setLevel(level)
    threading.Thread(
        target=_startup_preflight,
        args=(handler,),
        name="skewnono-chat-log-preflight",
        daemon=True,
    ).start()
    return handler
