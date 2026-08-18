"""Generic office-side OpenSearch plumbing for Hitachi features.

Connection handling, TTL caching, value coercion, and the two query entry
points (``aggregate`` for roll-ups, ``fetch_hits`` for document listings).
Nothing here knows about a specific index — index names, field names, and
query shapes live in the feature adapters that import this.

Split out of ``_office_meas_hist.py`` when ``lateral_recipe`` became the
first consumer backed by a NON-meas_hist index (``{cdsem,hvsem}_idp_ver``):
that module still owns the meas_hist indices, the lot/device catalogs, and
the KST-as-UTC timezone contract, and re-exports these helpers so its
existing consumers (recipe_tat, fail_issue, meas_hist) are unaffected.

This module is TRACKED (not an ``office_example.py`` template): it holds no
사내 schema details, only access mechanics.

Connection settings come from ``OPENSEARCH_HOST`` / ``OPENSEARCH_PORT`` /
``OPENSEARCH_USER`` / ``OPENSEARCH_PASSWORD`` in ``back_dev_home/.env``
(self-loaded so standalone runs work, same as ``office_redis.py``).
"""

import logging
import os
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from functools import lru_cache, wraps
from typing import Any

import pandas as pd
from opensearchpy.exceptions import NotFoundError

from ops_store import OSSearch, create_client

from back_dev_home._runtime.office_redis import load_env_file


__all__ = [
    "CACHE_TTL_SECONDS",
    "KST",
    "MAX_INNER_RESULT_WINDOW",
    "aggregate",
    "client",
    "fetch_hits",
    "parse_dt",
    "query",
    "search",
    "text",
    "top_hits",
    "ttl_cache",
]


_LOG = logging.getLogger(__name__)

# Korea has no DST — a fixed +09:00 offset is exact (mirrors the mocks' KST).
KST = timezone(timedelta(hours=9), "KST")

CACHE_TTL_SECONDS = 900  # backing catalogs refresh at most every 15 minutes

# OpenSearch caps a top_hits sub-aggregation at `index.max_inner_result_window`,
# which defaults to 100 — a DIFFERENT and much smaller limit than the 10,000
# `index.max_result_window` that bounds a top-level search. Exceeding it is a
# 400 `search_phase_execution_exception` at query time, not a truncation, so the
# whole page fails rather than showing less. Nothing about a `size: 200` looks
# wrong when you write it, which is why `top_hits` below refuses it here
# instead of letting the cluster refuse it in production.
MAX_INNER_RESULT_WINDOW = 100


def ttl_cache(func):
    """``lru_cache(maxsize=1)`` with expiry, serving stale on refresh failure.

    A long-lived office Flask process must eventually see new lots, devices,
    and data days without a restart — a plain ``lru_cache`` freezes them until
    redeploy. When a refresh attempt fails but a previous value exists, the
    stale value is served and the error logged: an upstream hiccup shouldn't
    blank pages that worked a minute ago. The first-ever load still raises.
    """
    state: dict[str, Any] = {}

    @wraps(func)
    def wrapper():
        now = time.monotonic()
        if "value" in state and now - state["at"] < CACHE_TTL_SECONDS:
            return state["value"]
        try:
            value = func()
        except Exception:
            if "value" in state:
                _LOG.exception(
                    "refresh of %s failed; serving stale value", func.__name__
                )
                state["at"] = now  # back off a full TTL before retrying
                return state["value"]
            raise
        state["value"] = value
        state["at"] = now
        return value

    wrapper.cache_clear = state.clear  # parity with lru_cache, for tests
    return wrapper


@lru_cache(maxsize=1)
def client() -> Any:
    """Create the OpenSearch client once and reuse its connection pool.

    ``create_client()`` reads OPENSEARCH_* from the environment via
    ``ops_store.load_config`` (host, port default 443, use_ssl, verify_certs,
    basic auth). We self-load .env first so a standalone run works.
    """
    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")
    if not os.environ.get("OPENSEARCH_HOST"):
        raise RuntimeError(
            "OPENSEARCH_HOST is not set. Run from the repo root so "
            "back_dev_home/.env is found, or set OPENSEARCH_HOST/"
            "OPENSEARCH_PORT/OPENSEARCH_USER/OPENSEARCH_PASSWORD in the "
            "environment before calling this adapter."
        )
    return create_client()


def search(index: str) -> OSSearch:
    return OSSearch(client=client(), index=index)


def parse_dt(value: str) -> datetime:
    """Parse an OpenSearch date string (``...Z`` / ``+00:00``) to aware UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def query(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    return {"bool": {"filter": clauses}}


def _missing_index_error(index: str, exc: Exception) -> LookupError:
    return LookupError(
        f"OpenSearch index/alias {index!r} not found — check the alias "
        "name and that ingestion has populated it."
    )


def aggregate(
    index: str, aggs: dict[str, Any], query_body: dict[str, Any] | None
) -> dict[str, Any]:
    try:
        result = search(index).aggregate(aggs, query=query_body)
    except NotFoundError as exc:
        raise _missing_index_error(index, exc) from exc
    if not isinstance(result, Mapping):
        raise RuntimeError(
            f"OpenSearch aggregate response for {index!r} must be a mapping; "
            f"got {type(result).__name__}."
        )
    timed_out = result.get("timed_out")
    if timed_out is not False:
        raise RuntimeError(
            f"OpenSearch aggregate response for {index!r} has invalid "
            f"'timed_out' metadata: expected exactly false, got {timed_out!r}."
        )
    shards = result.get("_shards")
    if not isinstance(shards, Mapping):
        raise RuntimeError(
            f"OpenSearch aggregate response for {index!r} '_shards' metadata "
            f"must be a mapping; got {type(shards).__name__}."
        )
    failed = shards.get("failed")
    if isinstance(failed, bool) or not isinstance(failed, int):
        raise RuntimeError(
            f"OpenSearch aggregate response for {index!r} '_shards.failed' "
            "must be a non-negative integer (boolean is not valid); "
            f"got {failed!r}."
        )
    if failed < 0:
        raise RuntimeError(
            f"OpenSearch aggregate response for {index!r} '_shards.failed' "
            f"must be non-negative; got {failed}."
        )
    if failed != 0:
        raise RuntimeError(
            f"OpenSearch aggregate response for {index!r} reports "
            f"_shards.failed={failed}; refusing partial aggregation results."
        )
    aggregations = result.get("aggregations")
    if not isinstance(aggregations, Mapping):
        raise RuntimeError(
            f"OpenSearch aggregate response for {index!r} 'aggregations' "
            f"must be a mapping; got {type(aggregations).__name__}."
        )
    return dict(aggregations)


def top_hits(
    size: int,
    *,
    sort: list[dict[str, Any]],
    source: list[str] | None = None,
) -> dict[str, Any]:
    """A ``top_hits`` sub-aggregation, refusing a size the cluster will reject.

    Raising here rather than at query time is the point: the cap is per-INNER
    result window (100 by default), not the familiar 10,000, and an adapter
    author reaching for "the last 200 docs per tool" has no reason to suspect a
    different ceiling applies. The error names the fix.

    A caller that legitimately needs more than the cap has to change shape, not
    the number — a composite walk, a date_histogram, or a narrower window —
    because raising ``index.max_inner_result_window`` is a cluster-wide setting
    paid for by every query, not just this one.
    """
    if size > MAX_INNER_RESULT_WINDOW:
        raise ValueError(
            f"top_hits size={size} exceeds index.max_inner_result_window "
            f"({MAX_INNER_RESULT_WINDOW}). OpenSearch answers 400 "
            "search_phase_execution_exception rather than truncating, so the "
            "page fails outright. Narrow the window, aggregate instead of "
            "listing, or split the query — do not raise the cluster setting "
            "for one screen."
        )
    body: dict[str, Any] = {"size": size, "sort": sort}
    if source is not None:
        body["_source"] = source
    return {"top_hits": body}


def fetch_hits(
    index: str,
    query_body: dict[str, Any] | None,
    size: int,
    sort: list[dict[str, Any]] | None = None,
    source: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Document ``_source`` dicts for ``query_body``, in ``sort`` order.

    Ordering comes entirely from the caller's ``sort``; with none passed, hits
    arrive in OpenSearch's own score/index order and no ordering is promised.

    A single non-paginated request capped at ``size``. Callers that can
    legitimately exceed the cap must detect truncation themselves (compare
    ``len(result)`` against ``size``) rather than silently showing a partial
    answer — there is no scroll here on purpose, since every current consumer
    reads a bounded per-recipe document set.

    ``source`` trims the fetched fields; leave it None to fetch everything.
    Passing it matters for indices carrying large ``object`` blobs that the
    caller does not need.
    """
    body: dict[str, Any] = {"size": size}
    if query_body is not None:
        body["query"] = query_body
    if sort:
        body["sort"] = sort
    if source is not None:
        body["_source"] = source
    try:
        result = search(index).search_raw(body)
    except NotFoundError as exc:
        raise _missing_index_error(index, exc) from exc
    return [hit.get("_source", {}) for hit in result.get("hits", {}).get("hits", [])]


# Values that mean "absent" once stringified. Kept so NaN/None/NaT fall out of
# keys and metadata instead of surfacing as literal "None" text.
_MISSING_TEXT = {"none", "nan", "null", "<na>"}


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode("utf-8")
    elif not isinstance(value, str):
        try:
            if pd.isna(value):  # float NaN, pd.NA, NaT
                return ""
        except (TypeError, ValueError):
            pass  # non-scalar (list, ...) — fall through to str()
    result = str(value).strip()
    if result.lower() in _MISSING_TEXT:
        return ""
    return result
