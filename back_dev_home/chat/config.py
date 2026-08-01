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
    models = DEFAULT_MODELS if not raw else json.loads(raw)
    normalized = []
    for row in models:
        model = dict(row)
        model.setdefault("supports_tools", False)
        model.setdefault("supports_vision", False)
        normalized.append(model)
    return normalized


def find_model(model_id: str) -> dict | None:
    return next((model for model in list_models() if model["id"] == model_id), None)


def _choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.environ.get(name, default).strip().lower()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}")
    return value


def get_runtime_name() -> str:
    return _choice("SKEWNONO_CHAT_RUNTIME", "direct", {"direct", "agent"})


def get_knowledge_provider_name() -> str:
    return _choice(
        "SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock", {"mock", "office"}
    )


def get_scope_provider_name() -> str:
    return _choice("SKEWNONO_CHAT_SCOPE_PROVIDER", "mock", {"mock", "office"})


def get_max_tool_calls() -> int:
    return min(max(int(os.environ.get("SKEWNONO_CHAT_MAX_TOOL_CALLS", "6")), 1), 12)


def get_agent_timeout() -> float:
    return min(max(float(os.environ.get("SKEWNONO_CHAT_AGENT_TIMEOUT", "60")), 1), 120)


def get_max_snippet_chars() -> int:
    return min(
        max(int(os.environ.get("SKEWNONO_CHAT_MAX_SNIPPET_CHARS", "1200")), 1),
        4000,
    )


def get_max_evidence_chars() -> int:
    return min(
        max(int(os.environ.get("SKEWNONO_CHAT_MAX_EVIDENCE_CHARS", "12000")), 1),
        40000,
    )


def get_rag_source_root() -> str | None:
    value = os.environ.get("SKEWNONO_RAG_SOURCE_ROOT", "").strip()
    return value or None
