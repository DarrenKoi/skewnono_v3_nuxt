"""LLM endpoint/model configuration. Swaps by env only — no code change per phase."""

import json
import os

from back_dev_home._runtime.env import is_cloud

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 60.0
MAX_CONCURRENT_AGENT_RUNS_HARD_LIMIT = 32
DEFAULT_MODELS = [
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "label": "Llama 3.3 70B (free)"},
    {"id": "google/gemini-2.0-flash-exp:free", "label": "Gemini 2.0 Flash (free)"},
]


def is_under_development() -> bool:
    """Whether the SPA should show the chat page as not-yet-in-service.

    Defaults to true on the production cloud and false everywhere else: chat
    is usable at home and at the office while it is being built, but must not
    look like a live service to production users yet.

    ``SKEWNONO_CHAT_UNDER_DEVELOPMENT`` (1/0) overrides in both directions, so
    launching is a config change on the cloud host rather than a code change —
    the same cross-phase rule the rest of this module follows. Read per call,
    not cached, so flipping it takes effect on the next request.

    This gates the PAGE only. ``/api/chat/*`` keeps answering everywhere,
    which is deliberate: it stays exercisable on the cloud host while the
    page is hidden. Do not turn this into an authorization check.
    """
    raw = os.environ.get("SKEWNONO_CHAT_UNDER_DEVELOPMENT")
    if raw is not None and raw.strip():
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return is_cloud()


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


def get_max_concurrent_agent_runs() -> int:
    name = "SKEWNONO_CHAT_MAX_CONCURRENT_AGENT_RUNS"
    raw = os.environ.get(name, "4")
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(
            f"{name} must be an integer between 1 and "
            f"{MAX_CONCURRENT_AGENT_RUNS_HARD_LIMIT}."
        ) from error
    if not 1 <= value <= MAX_CONCURRENT_AGENT_RUNS_HARD_LIMIT:
        raise ValueError(
            f"{name} must be an integer between 1 and "
            f"{MAX_CONCURRENT_AGENT_RUNS_HARD_LIMIT}."
        )
    return value


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


KNOWLEDGE_SOURCES: tuple[str, ...] = ("manual", "meeting", "email", "report")


def get_knowledge_sources() -> tuple[str, ...]:
    """Office-side sources whose retrieval path is ready.

    A source is listed only once its index exists. Unlisted sources are not
    exposed to the model at all — returning an empty result instead would read
    as "there is nothing about this in the meeting notes", which is a claim we
    cannot make about a source we never indexed.
    """
    name = "SKEWNONO_CHAT_KNOWLEDGE_SOURCES"
    raw = os.environ.get(name, "manual")
    requested = {part.strip().lower() for part in raw.split(",") if part.strip()}
    if not requested:
        raise ValueError(f"{name} must name at least one knowledge source.")
    unknown = sorted(requested - set(KNOWLEDGE_SOURCES))
    if unknown:
        allowed = ", ".join(KNOWLEDGE_SOURCES)
        raise ValueError(
            f"{name} must be a comma-separated subset of: {allowed}. "
            f"Unknown: {', '.join(unknown)}."
        )
    return tuple(source for source in KNOWLEDGE_SOURCES if source in requested)
