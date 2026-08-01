"""Direct chat runtime backed by the existing OpenAI-compatible client."""

from __future__ import annotations

from back_dev_home.chat import llm
from back_dev_home.chat.runtime.contracts import (
    RuntimeRequest,
    RuntimeResult,
    RuntimeTimeout,
    RuntimeUpstreamError,
)


def invoke(request: RuntimeRequest) -> RuntimeResult:
    """Run direct chat and normalize its reply to the stable runtime contract."""
    messages = list(request["messages"])
    if request["system_prompt"]:
        messages.insert(
            0,
            {
                "role": "system",
                "content": request["system_prompt"],
            },
        )

    try:
        reply = llm.send_chat(request["model"], messages)
    except llm.ChatTimeout as error:
        raise RuntimeTimeout(str(error)) from error
    except llm.ChatUpstreamError as error:
        raise RuntimeUpstreamError(str(error)) from error
    return {
        "content": reply["content"],
        "runtime": "direct",
        "model": request["model"],
        "prompt_tokens": reply["prompt_tokens"],
        "completion_tokens": reply["completion_tokens"],
        "latency_ms": reply["latency_ms"],
        "sources": [],
        "tool_traces": [],
    }
