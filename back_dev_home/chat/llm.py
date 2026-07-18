"""Stateless OpenAI-compatible chat client. Identical code across phases."""

import time

import httpx

from back_dev_home.chat import config, guard


class ChatError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ChatTimeout(ChatError):
    pass


class ChatUpstreamError(ChatError):
    pass


def send_chat(model: str, messages: list[dict]) -> dict:
    base_url = config.get_base_url()
    guard.enforce_egress_policy(base_url)
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    api_key = config.get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.perf_counter()
    try:
        resp = httpx.post(
            url,
            json={"model": model, "messages": messages},
            headers=headers,
            timeout=config.get_timeout(),
        )
    except httpx.TimeoutException as exc:
        raise ChatTimeout("The model did not respond in time.") from exc
    except httpx.HTTPError as exc:
        raise ChatUpstreamError(f"Could not reach the model gateway: {exc}") from exc

    latency_ms = int((time.perf_counter() - start) * 1000)

    if resp.status_code >= 400:
        raise ChatUpstreamError(
            f"Model gateway returned {resp.status_code}: {resp.text[:200]}"
        )

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content", "")
    usage = data.get("usage") or {}
    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "latency_ms": latency_ms,
    }
