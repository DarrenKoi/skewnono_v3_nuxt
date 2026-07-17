"""LLM endpoint/model configuration. Swaps by env only — no code change per phase."""

import json
import os

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MODELS = [
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "label": "Llama 3.3 70B (free)"},
    {"id": "google/gemini-2.0-flash-exp:free", "label": "Gemini 2.0 Flash (free)"},
]


def get_base_url() -> str:
    return os.environ.get("CHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_api_key() -> str | None:
    return os.environ.get("CHAT_API_KEY")


def get_timeout() -> float:
    raw = os.environ.get("CHAT_TIMEOUT")
    return float(raw) if raw else DEFAULT_TIMEOUT


def list_models() -> list[dict]:
    raw = os.environ.get("CHAT_MODELS")
    if not raw:
        return [dict(m) for m in DEFAULT_MODELS]
    return json.loads(raw)
