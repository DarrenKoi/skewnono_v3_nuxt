# TEMPLATE — copy to office.py at the office, then implement the OFFICE-TODO
# seams. office.py is gitignored; this file (office_example.py) is the tracked
# skeleton. Unlike presence-switched features, chat knowledge is selected by
# SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office, so copying this file alone changes
# nothing until that variable is set.
"""Phase 2/3 adapter skeleton for the office chat RAG knowledge source.

The contract half of this adapter is already written and must not change:
``_search()`` clamps limits, short-circuits empty queries, converts every
backend failure into the typed exceptions from ``contracts.py``, and
``_to_evidence()`` strictly validates each raw hit into an ``Evidence`` row.
The office implementation fills exactly three seams:

* ``_config()``       — load office settings (hosts, index aliases, timeouts)
  from environment/.env. Never accept them from user input or model arguments.
* ``_build_request(source_type, query, filters, scope, limit)`` — build the
  backend query. The ``AccessScope`` filter (user_id/groups/fabs) MUST be part
  of this request so filtering happens at query time; post-hoc Python
  filtering of results is a contract violation.
* ``_execute(source_type, request)`` — call the office backend and return raw
  hits as a list of mappings in the NORMALIZED RAW HIT shape below (rank
  order preserved). Map backend-specific errors in ``_translate_error()``.

Normalized raw hit — one mapping per result, keys:

| key             | type          | rule                                  |
| --------------- | ------------- | ------------------------------------- |
| ``source_id``   | str, required | stable across re-indexing; changes only with revision |
| ``title``       | str, required | approved-for-display title only       |
| ``snippet``     | str, required | approved minimal evidence, never full text |
| ``revision``    | str or None   | manual/report revision                |
| ``occurred_at`` | str or None   | normalized ISO-8601 source date       |
| ``section``     | str or None   | section provenance                    |
| ``page``        | int or None   | 1-based page number                   |
| ``region``      | str or None   | approved page region reference        |
| ``locator``     | str or None   | stable approved locator — never a URL or filesystem/MinIO path |
| ``score``       | float or None | ranking diagnostic                    |

``source_type`` is stamped by this adapter from the called function, never
read from the hit. Malformed hits raise ``KnowledgeUnavailable`` (index/schema
mismatch) naming the offending key but never the content. Empty results are
an empty list — no fallback to mock or another source, ever.

Verification: fill the OFFICE-TODO fixtures in
``back_dev_home/chat/tests/test_knowledge_office.py`` (tracked; skips at home)
and follow the ladder in ``back_dev_home/chat/MIGRATION.md``.
"""

from __future__ import annotations

from typing import Any, Mapping

from back_dev_home.chat.knowledge.contracts import (
    AccessScope,
    Evidence,
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)

# Application-side cap; callers already clamp to 5, this is defense in depth.
_RESULT_LIMIT = 5

_SOURCE_TYPES = ("manual", "meeting", "email", "report")

_OPTIONAL_STR_KEYS = ("revision", "occurred_at", "section", "region", "locator")


# ---------------------------------------------------------------------------
# OFFICE-TODO seams — the only code the office implementation writes.
# ---------------------------------------------------------------------------


def _config() -> Mapping[str, Any]:
    """Load office-side settings (hosts, index aliases, timeouts).

    OFFICE-TODO: read from environment/.env only (the self-load pattern in
    ``back_dev_home/_runtime/office_redis.load_env_file`` is available).
    Raise ``KnowledgeUnavailable`` when required settings are missing.
    Never log or return credentials.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: _config() is "
        "not implemented."
    )


def _build_request(
    source_type: str,
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> Mapping[str, Any]:
    """Build the backend search request for one source type.

    OFFICE-TODO: embed the ``scope`` access filter (user_id/groups/fabs) in
    the request itself so unauthorized sources are excluded at query time and
    their existence, title, count, and score are never observable. Restrict
    the field projection to the normalized raw hit keys.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: "
        "_build_request() is not implemented."
    )


def _execute(source_type: str, request: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Run one search against the office backend.

    OFFICE-TODO: call the office index/service and return raw hits in the
    normalized raw hit shape, preserving backend rank order. Let
    backend-specific exceptions escape; ``_search()`` routes them through
    ``_translate_error()``.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: _execute() is "
        "not implemented."
    )


def _translate_error(error: Exception) -> Exception:
    """Map backend-specific exceptions onto the typed contract exceptions.

    OFFICE-TODO: extend the mapping for the office client library —
    authorization failures to ``KnowledgeDenied``, deadline/timeout errors to
    ``KnowledgeTimeout``. Anything unrecognized stays ``KnowledgeUnavailable``
    (configuration/index mismatch/service down); never re-raise raw client
    errors and never include query text or credentials in messages.
    """
    if isinstance(error, TimeoutError):
        return KnowledgeTimeout("The chat knowledge search timed out.")
    if isinstance(error, PermissionError):
        return KnowledgeDenied("The chat knowledge search was denied.")
    return KnowledgeUnavailable("The chat knowledge search is unavailable.")


# ---------------------------------------------------------------------------
# Contract half — already written; the office copy must NOT edit below.
# ---------------------------------------------------------------------------


def _search(
    source_type: str,
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    if source_type not in _SOURCE_TYPES:
        raise KnowledgeUnavailable(f"Unknown chat knowledge source type: {source_type}")
    bounded = min(max(int(limit), 1), _RESULT_LIMIT)
    trimmed = query.strip()
    if not trimmed:
        return []

    request = _build_request(source_type, trimmed, filters, scope, bounded)
    try:
        raw_hits = _execute(source_type, request)
    except (KnowledgeDenied, KnowledgeTimeout, KnowledgeUnavailable):
        raise
    except Exception as error:  # noqa: BLE001 — everything becomes a typed error
        raise _translate_error(error) from error

    return [_to_evidence(source_type, hit) for hit in raw_hits[:bounded]]


def _to_evidence(source_type: str, hit: Mapping[str, Any]) -> Evidence:
    """Validate one normalized raw hit into an Evidence row (strict)."""
    evidence: dict[str, Any] = {"source_type": source_type}

    for key in ("source_id", "title", "snippet"):
        value = hit.get(key)
        if not isinstance(value, str) or not value.strip():
            raise KnowledgeUnavailable(
                f"Office knowledge hit is missing required field '{key}'."
            )
        evidence[key] = value

    for key in _OPTIONAL_STR_KEYS:
        value = hit.get(key)
        if value is not None and not isinstance(value, str):
            raise KnowledgeUnavailable(
                f"Office knowledge hit field '{key}' must be a string or None."
            )
        evidence[key] = value

    page = hit.get("page")
    if page is not None:
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise KnowledgeUnavailable(
                "Office knowledge hit field 'page' must be a 1-based int or None."
            )
    evidence["page"] = page

    score = hit.get("score")
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise KnowledgeUnavailable(
                "Office knowledge hit field 'score' must be a number or None."
            )
        score = float(score)
    evidence["score"] = score

    return evidence  # type: ignore[return-value]


def search_manuals(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("manual", query, filters, scope, limit)


def search_meeting_summaries(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("meeting", query, filters, scope, limit)


def search_emails(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("email", query, filters, scope, limit)


def search_reports(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("report", query, filters, scope, limit)
