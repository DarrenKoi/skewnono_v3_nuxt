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


def get_knowledge_timeout() -> float:
    """Seconds one office RAG call may take (search, rewrite, or follow-ups).

    Passed as ``timeout=`` to every RAG function. It is a per-call bound, not
    the loop's remaining budget: the agent wall-clock (``get_agent_timeout``)
    cuts the answer, but a RAG call already running in its thread would keep
    going without this. Kept under the agent timeout so a single hung search
    cannot consume the whole turn.
    """
    raw = float(os.environ.get("SKEWNONO_CHAT_KNOWLEDGE_TIMEOUT", "20"))
    return min(max(raw, 1), get_agent_timeout())


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


def get_figures_dir() -> str | None:
    """Absolute path of the directory holding extracted manual figures.

    The disk store, used while the knowledge provider is ``mock``. Unset means
    the deployment has no figure store, which is a 404 rather than an error: a
    manual indexed without figures is a normal state, not a misconfiguration.
    """
    value = os.environ.get("SKEWNONO_CHAT_FIGURES_DIR", "").strip()
    return value or None


def get_figure_bucket() -> str | None:
    """MinIO bucket of the office figure store; unset keeps the client default.

    At the office that default is the ``user`` bucket (``minio_handler``'s
    ``BUCKET``), which is where the figures live (office 확인 2026-08-27), so
    this is normally left unset.
    """
    value = os.environ.get("SKEWNONO_CHAT_FIGURE_BUCKET", "").strip()
    return value or None


# The office ingestion writes manual figures here, BELOW the MinIO client's
# own namespace prefix (RAG 측 확인 2026-08-31; supersedes the 2026-08-27
# ``hitachi_sem/manual_figures/`` layout):
#   {client prefix}/skewnono_rag/hitachi_manuals/figures/{figure_id}.webp
# ``skewnono_rag`` is the RAG's own namespace segment, not a bucket — see
# chat/figures.py.
DEFAULT_FIGURE_PREFIX = "skewnono_rag/hitachi_manuals/figures/"


def get_figure_prefix() -> str:
    """Key prefix of office figures, relative to the client's namespace prefix.

    Normalized to ``segment/.../`` — no leading slash, exactly one trailing —
    so ``figure_key()`` can concatenate. Do NOT put the user namespace
    (``2067928/``) here; the MinIO client already carries it and the key
    would double up.
    """
    raw = os.environ.get("SKEWNONO_CHAT_FIGURE_PREFIX", "").strip()
    value = (raw or DEFAULT_FIGURE_PREFIX).strip("/")
    return f"{value}/" if value else ""


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


def get_knowledge_candidate_pool() -> int:
    """How many candidates the office retrieval fetches before reranking.

    A cross-encoder reranker costs linearly in candidates, so this stays small.
    The application owns it — the adapter must not widen its own input.
    """
    raw = os.environ.get("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", "24")
    return min(max(int(raw), 5), 50)
