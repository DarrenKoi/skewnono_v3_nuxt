"""Shared office-side plumbing for the Hitachi meas_hist OpenSearch indices.

``_analytics.py`` is the shared helper module for the MOCK providers (row
filters over the in-memory universe); this module is its Phase 2/3 sibling:
OpenSearch connection plumbing, exact composite aggregation, and the
lot/device catalogs that every meas_hist-backed office adapter needs
(recipe_tat, fail_issue, ...).

Extracted from ``recipe_tat/providers/office_example.py`` when fail_issue
became the second consumer — per-adapter copies of the Redis helpers drifted
three ways before the same extraction landed in ``_runtime/office_redis.py``,
so the OpenSearch plumbing is shared from day one instead.

This module is TRACKED (it is not an ``office_example.py`` template): it
holds no 사내 schema secrets, only the access mechanics. Feature-specific
query shapes stay in each feature's gitignored ``providers/office.py``.

Data layout (see ``docs/datatables/meas_hist.txt`` for the full mapping):

* ``meas_hist_cdsem`` / ``meas_hist_hvsem`` — one document per measurement
  execution, alias per tool family. Text fields aggregate/filter through
  their ``.keyword`` sub-fields.
* ``ebeam_tas_lot_hist`` — the fab-system lot history. meas_hist documents
  carry ``lot_id`` but NOT ``lot_cd``; this index carries both, so its
  last-60-day slice is the ``lot_id <-> lot_cd`` bridge and, implicitly,
  the "currently active" device set.
* Redis ``device_desc`` / ``r3_device_grp`` — per-lot_cd display metadata
  (M-fab ``tech_nm`` vs. R3/R&D ``prod_catg_cd``).

Timezone: the office indices store KST wall-clock timestamps without an
offset, so OpenSearch treats them as UTC throughout — range filters, daily
histograms (no ``time_zone`` param), and the max-timestamp anchor all
operate on the same KST-as-UTC values. Consistent as long as no component
adds an offset; wall-clock fallbacks therefore use KST, not UTC, to match.

Connection settings come from ``OPENSEARCH_HOST`` / ``OPENSEARCH_PORT`` /
``OPENSEARCH_USER`` / ``OPENSEARCH_PASSWORD`` in ``back_dev_home/.env``
(self-loaded so standalone runs work, same as ``office_redis.py``).
"""

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache, wraps
from typing import Any

import pandas as pd
from opensearchpy.exceptions import NotFoundError

from ops_store import OSSearch, create_client

from back_dev_home._runtime.office_redis import (
    load_env_file,
    read_dataframe,
    redis_client,
)
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import ToolType


_LOG = logging.getLogger(__name__)

# Korea has no DST — a fixed +09:00 offset is exact (mirrors the mocks' KST).
KST = timezone(timedelta(hours=9), "KST")

CACHE_TTL_SECONDS = 900  # backing catalogs refresh at most every 15 minutes


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


# tool_type -> OpenSearch alias.
INDEX: dict[ToolType, str] = {
    "cd-sem": "meas_hist_cdsem",
    "hv-sem": "meas_hist_hvsem",
}
# Both aliases together — used only to anchor on the global latest timestamp.
ALL_INDICES = ",".join(INDEX.values())

# Time / metric fields (both are proper numeric/date types — no .keyword).
TIME_FIELD = "timestamp"   # date: drives the range filter, histogram, anchor
MEAS_FIELD = "meastime"    # long (seconds): recipe-TAT metric; every doc has one

# Exact-match / aggregation fields go through their .keyword sub-fields.
FULL_NAME_KW = "full_name.keyword"   # class_name/recipe_name composite group key
FAB_NAME_KW = "fab_name.keyword"     # fab selection filter
EQP_ID_KW = "eqp_id.keyword"         # sample_eqp_ids
LOT_ID_KW = "lot_id.keyword"         # device roll-ups + lot_cd drill-down


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


def _range_clause(start_date: str | None, end_date: str | None) -> dict[str, Any]:
    """Inclusive-day range on ``timestamp``.

    Bounds are dates (``yyyy-MM-dd``, UTC). We use ``gte start`` and
    ``lt end+1day`` so the whole of ``end_date`` is included — matching the
    mocks, which compare the ``YYYY-MM-DD`` slice with ``<=``.
    """
    bounds: dict[str, Any] = {"format": "yyyy-MM-dd"}
    if start_date:
        bounds["gte"] = start_date
    if end_date:
        end_excl = date.fromisoformat(end_date) + timedelta(days=1)
        bounds["lt"] = end_excl.isoformat()
    return {"range": {TIME_FIELD: bounds}}


def filter_clauses(
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = [_range_clause(start_date, end_date)]
    if fab_name:
        # fab_name is stored uppercase (M16A, R3, ...); the mocks compare
        # case-insensitively, so uppercase the term for parity.
        clauses.append({"term": {FAB_NAME_KW: fab_name.strip().upper()}})
    if lot_ids is not None:
        clauses.append({"terms": {LOT_ID_KW: lot_ids}})
    return clauses


def query(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    return {"bool": {"filter": clauses}}


def aggregate(
    index: str, aggs: dict[str, Any], query_body: dict[str, Any] | None
) -> dict[str, Any]:
    try:
        result = search(index).aggregate(aggs, query=query_body)
    except NotFoundError as exc:
        raise LookupError(
            f"OpenSearch index/alias {index!r} not found — check the alias "
            "name and that ingestion has populated it."
        ) from exc
    return result.get("aggregations", {})


_COMPOSITE_PAGE_SIZE = 1000


def composite_buckets(
    index: str,
    field: str,
    sub_aggs: dict[str, Any],
    query_body: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Every bucket for ``terms(field)`` via a paginated composite aggregation.

    A plain ``terms`` agg has two problems here: it truncates at ``size`` (the
    fleet has far more recipes/lots than any fixed cap over a wide date range),
    and when ordered by a sub-agg sum it is *approximate* — each shard sends
    its local top-N, so bucket totals can be wrong. ``composite`` walks every
    bucket exactly, one page of ``after_key`` at a time; sums per bucket are
    exact. Callers sort the complete list themselves.

    Each page bucket carries ``key.group`` (the term), ``doc_count``, and the
    requested ``sub_aggs`` results. ``sub_aggs`` may be empty (bucket walk
    only — e.g. a distinct count that needs post-mapping in Python).
    """
    buckets: list[dict[str, Any]] = []
    after: dict[str, Any] | None = None
    while True:
        composite: dict[str, Any] = {
            "size": _COMPOSITE_PAGE_SIZE,
            "sources": [{"group": {"terms": {"field": field}}}],
        }
        if after is not None:
            composite["after"] = after
        body: dict[str, Any] = {"comp": {"composite": composite}}
        if sub_aggs:
            body["comp"]["aggs"] = sub_aggs
        result = aggregate(index, body, query_body)
        page = result.get("comp", {})
        page_buckets = page.get("buckets", [])
        buckets.extend(page_buckets)
        after = page.get("after_key")
        if not after or len(page_buckets) < _COMPOSITE_PAGE_SIZE:
            break
    return buckets


# ─────────────────── device catalog + lot_id<->lot_cd bridge ────────────────
# lot_cd is NOT a field on the meas_hist_* documents (and lot_id does not encode
# lot_cd). The fab-system lot-history index (ebeam_tas_lot_hist) carries both,
# so it is the bridge: it maps each meas_hist lot_id to a lot_cd AND, over the
# last 60 days, defines the currently-active device set. device_desc (Redis)
# supplies the per-lot_cd display metadata.

_DEVICE_DESC_KEY = "device_desc"          # Redis parquet DataFrame (M-fab catalog)
_R3_DEVICE_GRP_KEY = "r3_device_grp"      # Redis parquet DataFrame (R3/R&D catalog)
_LOT_HIST_INDEX = "ebeam_tas_lot_hist"    # OpenSearch: fab-system measurement history
_LOT_HIST_TIME_F = "event_tm"             # date field on the lot-history index
CURRENT_WINDOW_DAYS = 60                  # a lot_cd active within this window = current


# The office catalogs (device_desc, r3_device_grp) carry missing cells in
# several spellings: real None/NaN/pd.NA, and sometimes the literal string
# "None" written by the upstream loader. All must normalize to "" so they
# fall out of lot_cd keys and metadata instead of surfacing as "None" text.
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


@ttl_cache
def device_desc() -> dict[str, dict[str, str]]:
    """lot_cd -> device metadata, from the Redis ``device_desc`` DataFrame.

    Columns: fac_id, lot_cd, stn_desc, chg_tm, tech_nm, rnd_connector.
    Includes retired lot_cds — callers intersect with the current set.
    """
    raw = redis_client().get(_DEVICE_DESC_KEY)
    if raw is None:
        raise LookupError(
            f"Redis key {_DEVICE_DESC_KEY!r} not found — check REDIS_* in "
            "back_dev_home/.env and that the device catalog is populated."
        )
    df = read_dataframe(raw, _DEVICE_DESC_KEY)
    out: dict[str, dict[str, str]] = {}
    for rec in df.to_dict(orient="records"):
        lot_cd = text(rec.get("lot_cd"))
        if not lot_cd:
            continue
        out[lot_cd] = {
            "fac_id": text(rec.get("fac_id")),
            "tech_nm": text(rec.get("tech_nm")),
            "rnd_connector": text(rec.get("rnd_connector")),
            "stn_desc": text(rec.get("stn_desc")),
        }
    return out


@ttl_cache
def r3_device_grp() -> dict[str, str]:
    """lot_cd -> prod_catg_cd, from the Redis ``r3_device_grp`` DataFrame.

    The R3/R&D catalog (fac_id is always "R3"). Only the product category is
    needed for device rows; other columns (tech_cd, den_type, prod_grp_typ,
    ...) are ignored here. Empty prod_catg_cd values are skipped.
    """
    raw = redis_client().get(_R3_DEVICE_GRP_KEY)
    if raw is None:
        raise LookupError(
            f"Redis key {_R3_DEVICE_GRP_KEY!r} not found — check REDIS_* in "
            "back_dev_home/.env and that the R3 device catalog is populated."
        )
    df = read_dataframe(raw, _R3_DEVICE_GRP_KEY)
    out: dict[str, str] = {}
    for rec in df.to_dict(orient="records"):
        lot_cd = text(rec.get("lot_cd"))
        prod_catg_cd = text(rec.get("prod_catg_cd"))
        if lot_cd and prod_catg_cd:
            out[lot_cd] = prod_catg_cd
    return out


@ttl_cache
def _lot_bridge() -> tuple[dict[str, str], dict[str, list[str]]]:
    """(lot_id->lot_cd, lot_cd->[lot_id, ...]) from ebeam_tas_lot_hist.

    meas_hist_* documents carry ``lot_id``, not ``lot_cd``, and the two are not
    derivable from each other. The fab-system lot history carries BOTH, so it
    is the join table (last-60-day slice via
    ``range_dataframe_all(time_field="event_tm", days=60)``). Because only
    lot_ids seen in this window get a lot_cd, the bridge also bounds the device
    catalog to recently-active lots (older lot_ids resolve to no device and
    drop out). Both directions are built from the same frame in one refresh so
    they can never disagree with each other.
    """
    df = search(_LOT_HIST_INDEX).range_dataframe_all(
        time_field=_LOT_HIST_TIME_F, days=CURRENT_WINDOW_DAYS
    )
    forward: dict[str, str] = {}
    if not df.empty and "lot_id" in df.columns and "lot_cd" in df.columns:
        for lot_id, lot_cd in zip(df["lot_id"].tolist(), df["lot_cd"].tolist()):
            lid, lcd = text(lot_id), text(lot_cd)
            if lid and lcd:
                forward[lid] = lcd
    reverse: dict[str, list[str]] = {}
    for lot_id, lot_cd in forward.items():
        reverse.setdefault(lot_cd, []).append(lot_id)
    return forward, reverse


def lot_id_to_lot_cd() -> dict[str, str]:
    """lot_id -> lot_cd, from the lot-history bridge."""
    return _lot_bridge()[0]


def lot_cd_to_lot_ids() -> dict[str, list[str]]:
    """lot_cd -> [lot_id, ...] (reverse of the bridge)."""
    return _lot_bridge()[1]


def try_bridge() -> dict[str, str]:
    """lot_id->lot_cd map, or {} if the lot-history index is unreachable.

    Used where the map is a nice-to-have (e.g. ranking ``sample_lot_cds``, a
    summary KPI) so a lot-history hiccup never breaks the core aggregation.
    Essential paths (/devices, lot_cd drill-down) call the raising helpers
    directly.
    """
    try:
        return lot_id_to_lot_cd()
    except Exception:  # noqa: BLE001 — degrade the nice-to-have, keep the page alive
        _LOG.exception("lot-history bridge unavailable; lot_cd mapping degraded")
        return {}


def lot_ids_for_lot_cd(lot_cd: str) -> list[str]:
    """The ``lot_id`` values to filter meas_hist_* by, for a selected device.

    Resolved through the lot-history bridge. An unknown lot_cd yields ``[]`` so
    the caller's ``terms(lot_id.keyword, [])`` matches nothing (an empty scope)
    rather than silently matching every measurement.
    """
    return lot_cd_to_lot_ids().get(lot_cd, [])


@ttl_cache
def get_anchor_time() -> datetime:
    """Latest ``timestamp`` across both aliases (the date-picker ceiling).

    TTL-cached AND shared by every meas_hist-backed office adapter: the
    recipe-status page renders recipe_tat and fail_issue as sibling tabs, so
    one cached anchor keeps their 데이터 기준 dates identical within a burst
    of requests (like the mocks' fixed ANCHOR_TIME) while still following new
    ingestion days in a long-lived process. Falls back to wall-clock KST now
    only when neither alias has any rows (see module docstring on KST-as-UTC).
    """
    aggs = {"max_ts": {"max": {"field": TIME_FIELD}}}
    result = aggregate(ALL_INDICES, aggs, query_body=None)
    value = result.get("max_ts", {}).get("value_as_string")
    if value:
        return parse_dt(value)
    return datetime.now(KST).replace(microsecond=0)
