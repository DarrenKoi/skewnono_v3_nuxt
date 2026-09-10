"""Chat configuration. Swaps by env only — no code change per phase.

There is no model or gateway setting here: the RAG owns the LLM (its keys are
embedded in ``skewnono_rag/config.py``), so chat never makes an outbound model
call of its own. What is left are budgets and the office figure store.
"""

import os


def is_under_development() -> bool:
    """Whether the SPA should show the chat page as not-yet-in-service.

    Defaults to FALSE everywhere since 2026-09-01: chat is in service on the
    production cloud too. Before that the default was ``is_cloud()`` — shown
    at home and at the office, hidden in production while it was being built.

    ``SKEWNONO_CHAT_UNDER_DEVELOPMENT=1`` puts the notice back without a
    deploy, which is why the flag outlives the launch: if the RAG goes down
    on the cloud, hiding the page is a ``.env`` line and a restart. Read per
    call, not cached, so flipping it takes effect on the next request.

    This gates the PAGE only. ``/api/chat/*`` keeps answering everywhere,
    which is deliberate: it stays exercisable on the cloud host while the
    page is hidden. Do not turn this into an authorization check.
    """
    raw = os.environ.get("SKEWNONO_CHAT_UNDER_DEVELOPMENT")
    if raw is not None and raw.strip():
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def get_answer_timeout() -> float:
    """Seconds one whole RAG turn may take, sent to the RAG as its budget.

    Nothing on this side enforces it any more. The thread guard that used to
    (``_call_with_deadline``) went away with the turn-as-resource change on
    2026-09-01: it protected a request that is now over before the RAG is
    asked, and it could never stop the call anyway — only abandon it. The RAG
    raises ``TimeoutError`` on its own budget, and that is the ceiling.

    240 default: one turn is not one model call. Query rewrite, hybrid
    retrieval, rerank and follow-up generation each take their own slice, and
    turns were still being cut off mid-progress at 60, 120 and 180.

    **300 cap, because that is the RAG's own hard ceiling** (RAG 측 확인
    2026-09-01: they cap a turn at 300s outright, on the grounds that an
    answer arriving later than that is a problem rather than a slow success).
    Asking for more than 300 would have chat waiting on time the RAG will
    never give. It is no longer a deployment invariant: the answer does not
    run on a request thread, so this number no longer has to sit under
    uWSGI's harakiri.
    """
    return min(max(float(os.environ.get("SKEWNONO_CHAT_ANSWER_TIMEOUT", "240")), 1), 300)


def get_answer_history_limit() -> int:
    """Prior turns sent to the RAG's agent_query, capped before the call.

    Default 5 = the RAG's own chat/app.py MAX_HISTORY (RAG 측 확인
    2026-08-31); sending more is wasted payload the RAG truncates anyway.
    """
    return min(max(int(os.environ.get("SKEWNONO_CHAT_ANSWER_MAX_HISTORY", "5")), 1), 100)


def get_figures_dir() -> str | None:
    """Absolute path of the directory holding extracted manual figures.

    The disk store, used wherever there is no RAG checkout. Unset means the
    deployment has no figure store, which is a 404 rather than an error: a
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


