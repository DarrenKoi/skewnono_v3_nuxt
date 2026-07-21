# TEMPLATE — copy to office.py at the office, then implement/verify the body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 Recipe-TAT adapter backed by the office OpenSearch cluster.

Measurement history lives in OpenSearch under two aliases, one per tool
family:

* ``meas_hist_cdsem`` — CD-SEM measurement executions (tool_type ``cd-sem``).
* ``meas_hist_hvsem`` — HV-SEM measurement executions (tool_type ``hv-sem``).

Each document is one measurement execution. The TAT dashboard never needs
the raw rows — every endpoint is a server-side aggregation over ``meastime``
(the per-execution turnaround, in seconds) sliced by ``timestamp`` (the date
range) and optionally ``fab_name`` / ``lot_cd``:

* ranking      — ``terms`` agg on ``full_name.keyword`` (the class/recipe
                 composite), ``sum(meastime)`` + ``top_hits`` per bucket.
* summary      — ``sum(meastime)`` + ``cardinality(full_name.keyword)`` +
                 ``value_count(meastime)`` over the same filter.
* daily-trend  — ``date_histogram`` (calendar day) with ``extended_bounds``
                 so empty days are zero-filled, matching the mock.
* anchor       — ``max(timestamp)`` across both aliases: the date-picker
                 ceiling (the real latest data date, NOT wall-clock).

Text fields are aggregated/filtered through their ``.keyword`` sub-fields
(OpenSearch tokenizes ``text``; exact match / aggregation needs ``.keyword``
— see ``ops_store/docs/llm_tool_calling_usage.md``).

Connection settings come from ``OPENSEARCH_HOST`` / ``OPENSEARCH_PORT`` /
``OPENSEARCH_USER`` / ``OPENSEARCH_PASSWORD`` in ``back_dev_home/.env`` (the
same vars ``ops_store`` reads). At the office: fill in .env,
``cp office_example.py office.py``, set ``SKEWNONO_RECIPE_TAT_PROVIDER=office``,
then run the Verify command in MIGRATION.md.

DEVICE / lot_cd JOIN: ``lot_cd`` is not on the meas_hist_* documents, and
``lot_id`` does not encode it. The fab-system lot-history index
(``ebeam_tas_lot_hist``) carries both ``lot_id`` and ``lot_cd`` (its ``lot_id``
matches meas_hist's), so it is the bridge — last-60-day slice, cached. It
powers: ``get_devices`` (aggregate meas_hist by ``lot_id`` in scope → map to
``lot_cd`` → roll up), the ``lot_cd`` drill-down on ranking/summary/daily-trend
(``lot_cd`` → its ``lot_id`` set → ``terms(lot_id.keyword)`` filter), and
``sample_lot_cds`` on ranking rows.

Device metadata (exactly one per device): M-fab devices carry ``tech_nm`` from
the Redis ``device_desc`` catalog; R3/R&D devices carry ``prod_catg_cd`` from
the Redis ``r3_device_grp`` catalog.
"""

import logging
import os
import pickle
import sys
import time
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache, wraps
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import redis
from opensearchpy.exceptions import NotFoundError
from redis.backoff import NoBackoff
from redis.retry import Retry

from ops_store import OSSearch, create_client

from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
    RankingRow,
    SummaryPayload,
    ToolType,
)


_LOG = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 900  # backing catalogs refresh at most every 15 minutes


def _ttl_cache(func):
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
        if "value" in state and now - state["at"] < _CACHE_TTL_SECONDS:
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
_INDEX: dict[ToolType, str] = {
    "cd-sem": "meas_hist_cdsem",
    "hv-sem": "meas_hist_hvsem",
}
# Both aliases together — used only to anchor on the global latest timestamp.
_ALL_INDICES = ",".join(_INDEX.values())

# Time / metric fields (both are proper numeric/date types — no .keyword).
_TIME_F = "timestamp"      # date: drives the range filter, histogram, anchor
_MEAS_F = "meastime"       # long (seconds): the TAT metric we sum

# Exact-match / aggregation fields go through their .keyword sub-fields.
_FULL_KW = "full_name.keyword"      # class_name/recipe_name composite group key
_FAB_KW = "fab_name.keyword"        # fab selection filter
_EQP_KW = "eqp_id.keyword"          # ranking sample_eqp_ids


def _load_env_file() -> None:
    """Load back_dev_home/.env for standalone / bare-import runs.

    The Flask app factory and conftest.py already load it; this is the fallback
    when the module is imported directly (script, ``python -m``, notebook).
    Try the repo-root-relative path first (honors "run from the repo root"),
    then the .env sitting next to the ``back_dev_home`` package — the latter
    works no matter the current working directory. ``override=False`` (the
    default) keeps any value already set by Flask/pytest.
    """
    from dotenv import load_dotenv

    load_dotenv("back_dev_home/.env")
    if os.environ.get("OPENSEARCH_HOST"):
        return
    pkg = sys.modules.get("back_dev_home")  # already imported by this module
    pkg_file = getattr(pkg, "__file__", None)
    if pkg_file:
        load_dotenv(Path(pkg_file).with_name(".env"))


@lru_cache(maxsize=1)
def _client() -> Any:
    """Create the OpenSearch client once and reuse its connection pool.

    ``create_client()`` reads OPENSEARCH_* from the environment via
    ``ops_store.load_config`` (host, port default 443, use_ssl, verify_certs,
    basic auth). We self-load .env first so a standalone run works.
    """
    if not os.environ.get("OPENSEARCH_HOST"):
        _load_env_file()
    if not os.environ.get("OPENSEARCH_HOST"):
        raise RuntimeError(
            "OPENSEARCH_HOST is not set. Run from the repo root so "
            "back_dev_home/.env is found, or set OPENSEARCH_HOST/"
            "OPENSEARCH_PORT/OPENSEARCH_USER/OPENSEARCH_PASSWORD in the "
            "environment before calling this adapter."
        )
    return create_client()


def _search(index: str) -> OSSearch:
    return OSSearch(client=_client(), index=index)


def _parse_dt(value: str) -> datetime:
    """Parse an OpenSearch date string (``...Z`` / ``+00:00``) to aware UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _range_clause(start_date: str | None, end_date: str | None) -> dict[str, Any]:
    """Inclusive-day range on ``timestamp``.

    Bounds are dates (``yyyy-MM-dd``, UTC). We use ``gte start`` and
    ``lt end+1day`` so the whole of ``end_date`` is included — matching the
    mock, which compares the ``YYYY-MM-DD`` slice with ``<=``.
    """
    bounds: dict[str, Any] = {"format": "yyyy-MM-dd"}
    if start_date:
        bounds["gte"] = start_date
    if end_date:
        end_excl = date.fromisoformat(end_date) + timedelta(days=1)
        bounds["lt"] = end_excl.isoformat()
    return {"range": {_TIME_F: bounds}}


def _filter_clauses(
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = [_range_clause(start_date, end_date)]
    if fab_name:
        # fab_name is stored uppercase (M16A, R3, ...); the mock compares
        # case-insensitively, so uppercase the term for parity.
        clauses.append({"term": {_FAB_KW: fab_name.strip().upper()}})
    if lot_ids is not None:
        clauses.append({"terms": {"lot_id.keyword": lot_ids}})
    return clauses


def _query(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    return {"bool": {"filter": clauses}}


def _aggregate(index: str, aggs: dict[str, Any], query: dict[str, Any] | None) -> dict[str, Any]:
    try:
        result = _search(index).aggregate(aggs, query=query)
    except NotFoundError as exc:
        raise LookupError(
            f"OpenSearch index/alias {index!r} not found — check the alias "
            "name and that ingestion has populated it."
        ) from exc
    return result.get("aggregations", {})


_COMPOSITE_PAGE_SIZE = 1000


def _composite_buckets(
    index: str,
    field: str,
    sub_aggs: dict[str, Any],
    query: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Every bucket for ``terms(field)`` via a paginated composite aggregation.

    A plain ``terms`` agg has two problems here: it truncates at ``size`` (the
    fleet has far more recipes/lots than any fixed cap over a wide date range),
    and when ordered by a sub-agg sum it is *approximate* — each shard sends
    its local top-N, so bucket totals can be wrong. ``composite`` walks every
    bucket exactly, one page of ``after_key`` at a time; sums per bucket are
    exact. Callers sort the complete list themselves.

    Each page bucket carries ``key.group`` (the term), ``doc_count``, and the
    requested ``sub_aggs`` results.
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
        result = _aggregate(
            index, {"comp": {"composite": composite, "aggs": sub_aggs}}, query
        )
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
_CURRENT_WINDOW_DAYS = 60                 # a lot_cd active within this window = current


@lru_cache(maxsize=1)
def _redis_client() -> redis.Redis:
    # Cached: one client (and its connection pool) per process instead of a
    # fresh TCP connect per request. redis-py re-establishes dropped pool
    # connections per command, so reuse is safe across backend restarts.
    host = os.environ.get("REDIS_HOST")
    if not host:
        _load_env_file()
        host = os.environ.get("REDIS_HOST")
    if not host:
        raise RuntimeError(
            "REDIS_HOST is not set (needed for the device_desc catalog). Run "
            "from the repo root so back_dev_home/.env is found, or set "
            "REDIS_HOST/REDIS_PORT/REDIS_PASSWORD in the environment."
        )
    return redis.Redis(
        host=host,
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD"),
        decode_responses=False,   # the value is a serialized DataFrame (binary)
        socket_connect_timeout=5,
        socket_timeout=10,
        retry=Retry(NoBackoff(), retries=1),
    )


def _read_dataframe(raw: bytes, key: str) -> pd.DataFrame:
    """Deserialize a DataFrame stored in Redis (parquet, else pickle)."""
    try:
        if raw[:4] == b"PAR1":
            return pd.read_parquet(BytesIO(raw), engine="pyarrow")
        obj = pickle.loads(raw)
    except Exception as exc:
        # LookupError (bare) = upstream data problem — the app-level handler
        # turns it into a JSON 502 instead of an opaque traceback.
        raise LookupError(
            f"Redis key {key!r} holds bytes that deserialize as neither "
            f"parquet nor pickle: {exc}"
        ) from exc
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, dict):
        return pd.DataFrame(obj)
    raise LookupError(
        f"Redis key {key!r} is a {type(obj).__name__}, expected DataFrame"
    )


# The office catalogs (device_desc, r3_device_grp) carry missing cells in
# several spellings: real None/NaN/pd.NA, and sometimes the literal string
# "None" written by the upstream loader. All must normalize to "" so they
# fall out of lot_cd keys and metadata instead of surfacing as "None" text.
_MISSING_TEXT = {"none", "nan", "null", "<na>"}


def _text(value: Any) -> str:
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
    text = str(value).strip()
    if text.lower() in _MISSING_TEXT:
        return ""
    return text


@_ttl_cache
def _device_desc() -> dict[str, dict[str, str]]:
    """lot_cd -> device metadata, from the Redis ``device_desc`` DataFrame.

    Columns: fac_id, lot_cd, stn_desc, chg_tm, tech_nm, rnd_connector.
    Includes retired lot_cds — callers intersect with the current set.
    """
    raw = _redis_client().get(_DEVICE_DESC_KEY)
    if raw is None:
        raise LookupError(
            f"Redis key {_DEVICE_DESC_KEY!r} not found — check REDIS_* in "
            "back_dev_home/.env and that the device catalog is populated."
        )
    df = _read_dataframe(raw, _DEVICE_DESC_KEY)
    out: dict[str, dict[str, str]] = {}
    for rec in df.to_dict(orient="records"):
        lot_cd = _text(rec.get("lot_cd"))
        if not lot_cd:
            continue
        out[lot_cd] = {
            "fac_id": _text(rec.get("fac_id")),
            "tech_nm": _text(rec.get("tech_nm")),
            "rnd_connector": _text(rec.get("rnd_connector")),
            "stn_desc": _text(rec.get("stn_desc")),
        }
    return out


@_ttl_cache
def _r3_device_grp() -> dict[str, str]:
    """lot_cd -> prod_catg_cd, from the Redis ``r3_device_grp`` DataFrame.

    The R3/R&D catalog (fac_id is always "R3"). Only the product category is
    needed for DeviceRow; other columns (tech_cd, den_type, prod_grp_typ, ...)
    are ignored here. Empty prod_catg_cd values are skipped.
    """
    raw = _redis_client().get(_R3_DEVICE_GRP_KEY)
    if raw is None:
        raise LookupError(
            f"Redis key {_R3_DEVICE_GRP_KEY!r} not found — check REDIS_* in "
            "back_dev_home/.env and that the R3 device catalog is populated."
        )
    df = _read_dataframe(raw, _R3_DEVICE_GRP_KEY)
    out: dict[str, str] = {}
    for rec in df.to_dict(orient="records"):
        lot_cd = _text(rec.get("lot_cd"))
        prod_catg_cd = _text(rec.get("prod_catg_cd"))
        if lot_cd and prod_catg_cd:
            out[lot_cd] = prod_catg_cd
    return out


@_ttl_cache
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
    df = _search(_LOT_HIST_INDEX).range_dataframe_all(
        time_field=_LOT_HIST_TIME_F, days=_CURRENT_WINDOW_DAYS
    )
    forward: dict[str, str] = {}
    if not df.empty and "lot_id" in df.columns and "lot_cd" in df.columns:
        for lot_id, lot_cd in zip(df["lot_id"].tolist(), df["lot_cd"].tolist()):
            lid, lcd = _text(lot_id), _text(lot_cd)
            if lid and lcd:
                forward[lid] = lcd
    reverse: dict[str, list[str]] = {}
    for lot_id, lot_cd in forward.items():
        reverse.setdefault(lot_cd, []).append(lot_id)
    return forward, reverse


def _lot_id_to_lot_cd() -> dict[str, str]:
    """lot_id -> lot_cd, from the lot-history bridge."""
    return _lot_bridge()[0]


def _lot_cd_to_lot_ids() -> dict[str, list[str]]:
    """lot_cd -> [lot_id, ...] (reverse of the bridge)."""
    return _lot_bridge()[1]


def _try_bridge() -> dict[str, str]:
    """lot_id->lot_cd map, or {} if the lot-history index is unreachable.

    Used where the map is a nice-to-have (ranking ``sample_lot_cds``) so a
    lot-history hiccup never breaks the core aggregation. The essential paths
    (/devices, lot_cd drill-down) call the raising helpers directly.
    """
    try:
        return _lot_id_to_lot_cd()
    except Exception:  # noqa: BLE001 — degrade sample_lot_cds, keep ranking alive
        _LOG.exception("lot-history bridge unavailable; sample_lot_cds degraded to []")
        return {}


def _lot_ids_for_lot_cd(lot_cd: str) -> list[str]:
    """The ``lot_id`` values to filter meas_hist_* by, for a selected device.

    Resolved through the lot-history bridge. An unknown lot_cd yields ``[]`` so
    the caller's ``terms(lot_id.keyword, [])`` matches nothing (an empty scope)
    rather than silently matching every measurement.
    """
    return _lot_cd_to_lot_ids().get(lot_cd, [])


# ─────────────────────────────── endpoints ──────────────────────────────────

@_ttl_cache
def get_anchor_time() -> datetime:
    """Latest ``timestamp`` across both aliases (the date-picker ceiling).

    TTL-cached: stable within a burst of requests (like the mock's fixed
    ANCHOR_TIME) but follows new ingestion days in a long-lived process.
    Falls back to wall-clock now only when neither alias has any rows.
    """
    aggs = {"max_ts": {"max": {"field": _TIME_F}}}
    result = _aggregate(_ALL_INDICES, aggs, query=None)
    value = result.get("max_ts", {}).get("value_as_string")
    if value:
        return _parse_dt(value)
    return datetime.now(timezone.utc).replace(microsecond=0)


def get_meas_hist(*args: Any, **kwargs: Any) -> Any:
    # Not used by the TAT routes (they only call the aggregation endpoints)
    # and not part of the contract gate. Raw-row export would also need the
    # lot_cd source; use the aggregation endpoints instead.
    raise NotImplementedError(
        "get_meas_hist (raw rows) is intentionally not connected for office "
        "mode — the Recipe-TAT routes use the aggregation endpoints below."
    )


def get_ranking(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None,
) -> list[RankingRow]:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_name, start_date, end_date, lot_ids)

    # Composite (not terms) so the ranking covers EVERY recipe in the range:
    # a terms agg both truncates at its size cap and, when ordered by the sum
    # sub-agg, returns approximate totals. All buckets are fetched page by
    # page, then ranked here; limit>0 trims only the final, complete ranking.
    sub_aggs = {
        "tat": {"sum": {"field": _MEAS_F}},
        "eqps": {"terms": {"field": _EQP_KW, "size": 5}},
        # A handful of lot_ids per recipe, mapped to lot_cds below.
        "lots": {"terms": {"field": "lot_id.keyword", "size": 25}},
        "top": {
            "top_hits": {
                "size": 1,
                "_source": ["class_name", "recipe_name", "full_name"],
            }
        },
    }
    buckets = _composite_buckets(_INDEX[tool_type], _FULL_KW, sub_aggs, _query(clauses))
    buckets.sort(key=lambda b: int(b.get("tat", {}).get("value") or 0), reverse=True)
    if limit > 0:
        buckets = buckets[:limit]
    # Nice-to-have: never let a lot-history hiccup break the ranking table.
    bridge = _try_bridge()

    rows: list[RankingRow] = []
    for index, bucket in enumerate(buckets):
        meas_counts = int(bucket["doc_count"])
        total = int(bucket.get("tat", {}).get("value") or 0)
        avg = round(total / meas_counts, 2) if meas_counts else 0.0
        source = (bucket.get("top", {}).get("hits", {}).get("hits") or [{}])[0].get(
            "_source", {}
        )
        eqp_buckets = bucket.get("eqps", {}).get("buckets", [])
        sample_eqps = sorted(str(b["key"]) for b in eqp_buckets)[:5]
        # Map the recipe's sample lot_ids to their lot_cds (drop unmapped).
        lot_buckets = bucket.get("lots", {}).get("buckets", [])
        sample_lot_cds = sorted(
            {bridge.get(_text(b["key"]), "") for b in lot_buckets} - {""}
        )[:5]

        rows.append(
            RankingRow(
                rank=index + 1,
                class_name=str(source.get("class_name", "")),
                recipe_name=str(source.get("recipe_name", "")),
                full_name=str(source.get("full_name") or bucket["key"].get("group", "")),
                meas_counts=meas_counts,
                total_meastime=total,
                avg_meastime=avg,
                sample_lot_cds=sample_lot_cds,
                sample_eqp_ids=sample_eqps,
            )
        )
    return rows


def get_summary(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> SummaryPayload:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_name, start_date, end_date, lot_ids)

    aggs = {
        "tat": {"sum": {"field": _MEAS_F}},
        "execs": {"value_count": {"field": _MEAS_F}},
        "recipes": {"cardinality": {"field": _FULL_KW}},
    }
    result = _aggregate(_INDEX[tool_type], aggs, _query(clauses))

    total_tat = int(result.get("tat", {}).get("value") or 0)
    total_executions = int(result.get("execs", {}).get("value") or 0)
    total_recipes = int(result.get("recipes", {}).get("value") or 0)
    avg = round(total_tat / total_executions, 2) if total_executions else 0.0

    return SummaryPayload(
        tool_type=tool_type,
        fab_name=fab_name,
        start_date=start_date,
        end_date=end_date,
        anchor_date=get_anchor_time().date().isoformat(),
        total_tat_seconds=total_tat,
        total_recipes=total_recipes,
        total_executions=total_executions,
        avg_meastime=avg,
    )


def get_daily_trend(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> list[DailyTrendPoint]:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_name, start_date, end_date, lot_ids)

    histogram: dict[str, Any] = {
        "field": _TIME_F,
        "calendar_interval": "day",
        "format": "yyyy-MM-dd",
        "min_doc_count": 0,
    }
    # Zero-fill the whole requested range so the trend chart has a continuous
    # x-axis (mirrors the mock's backfill). extended_bounds needs both ends.
    if start_date and end_date:
        histogram["extended_bounds"] = {"min": start_date, "max": end_date}

    aggs = {
        "by_day": {
            "date_histogram": histogram,
            "aggs": {"tat": {"sum": {"field": _MEAS_F}}},
        }
    }
    result = _aggregate(_INDEX[tool_type], aggs, _query(clauses))
    buckets = result.get("by_day", {}).get("buckets", [])

    return [
        DailyTrendPoint(
            date=str(bucket["key_as_string"]),
            total_meastime=int(bucket.get("tat", {}).get("value") or 0),
            exec_count=int(bucket["doc_count"]),
        )
        for bucket in buckets
    ]


def get_devices(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[DeviceRow]:
    """Devices (lot_cds) with measurements in scope, ranked by total TAT.

    meas_hist_* is aggregated by ``lot_id`` within the tool/fab/date scope, each
    ``lot_id`` is mapped to its ``lot_cd`` through the lot-history bridge, and
    the per-lot sums are rolled up per device. Because the bridge only knows
    recently-active lot_ids, an in-scope ``lot_id`` with no mapping is dropped
    (keeps retired/unknown lots out).

    ``exec_count``/``total_meastime`` are the real in-scope execution count and
    summed ``meastime`` per device. Metadata follows the mock's exactly-one
    rule: R3/R&D devices carry ``prod_catg_cd`` (from ``r3_device_grp``),
    M-fab devices carry ``tech_nm`` (from ``device_desc``).
    """
    clauses = _filter_clauses(fab_name, start_date, end_date)
    # Composite pagination (see _composite_buckets): every in-scope lot_id,
    # not a top-N — a capped terms agg would drop lots (and thus understate
    # or lose whole devices) on fleet-wide date ranges.
    lot_buckets = _composite_buckets(
        _INDEX[tool_type],
        "lot_id.keyword",
        {"tat": {"sum": {"field": _MEAS_F}}},
        _query(clauses),
    )

    bridge = _lot_id_to_lot_cd()
    catalog = _device_desc()
    r3 = _r3_device_grp()

    rolled: dict[str, dict[str, int]] = {}
    for bucket in lot_buckets:
        lot_cd = bridge.get(_text(bucket["key"]["group"]))
        if not lot_cd:              # lot_id not in the recent bridge -> drop
            continue
        agg = rolled.setdefault(lot_cd, {"exec": 0, "tat": 0})
        agg["exec"] += int(bucket["doc_count"])
        agg["tat"] += int(bucket.get("tat", {}).get("value") or 0)

    rows: list[DeviceRow] = []
    for lot_cd, agg in rolled.items():
        # Exactly one of the pair: R3/R&D -> prod_catg_cd, M-fab -> tech_nm.
        prod_catg_cd = r3.get(lot_cd)
        tech_nm = None if prod_catg_cd else (catalog.get(lot_cd, {}).get("tech_nm") or None)
        rows.append(
            DeviceRow(
                lot_cd=lot_cd,
                exec_count=agg["exec"],
                total_meastime=agg["tat"],
                prod_catg_cd=prod_catg_cd,
                tech_nm=tech_nm,
            )
        )
    rows.sort(key=lambda r: (r["total_meastime"], r["exec_count"]), reverse=True)
    return rows


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.hitachi.recipe_tat.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    # _client() loads back_dev_home/.env itself if the env isn't set.
    anchor = get_anchor_time()
    end = anchor.date().isoformat()
    start = (anchor.date() - timedelta(days=30)).isoformat()
    print(f"anchor (latest data date): {anchor.isoformat()}")

    for tool in ("cd-sem", "hv-sem"):
        summary = get_summary(tool, None, start, end)  # type: ignore[arg-type]
        ranking = get_ranking(tool, None, start, end, limit=5)  # type: ignore[arg-type]
        trend = get_daily_trend(tool, None, start, end)  # type: ignore[arg-type]
        print(
            f"\n[{tool}] {start}..{end}  "
            f"execs={summary['total_executions']}  "
            f"recipes={summary['total_recipes']}  "
            f"total_tat={summary['total_tat_seconds']}s  "
            f"avg={summary['avg_meastime']}s"
        )
        for row in ranking:
            print(
                f"  #{row['rank']:>2} {row['full_name']:<28} "
                f"counts={row['meas_counts']:>5} total={row['total_meastime']:>8}s"
            )
        if trend:
            print(f"  daily-trend points: {len(trend)} ({trend[0]['date']}..{trend[-1]['date']})")

    # /devices needs BOTH Redis (device_desc) and ebeam_tas_lot_hist. Guard it
    # so the OpenSearch results above still print if Redis isn't configured.
    try:
        devices = get_devices("cd-sem", None, start, end)  # type: ignore[arg-type]
        print(f"\ndevices (current, last {_CURRENT_WINDOW_DAYS}d ∩ device_desc): {len(devices)}")
        for dev in devices[:5]:
            print(f"  {dev['lot_cd']:<14} exec={dev['exec_count']:>5} tech_nm={dev['tech_nm']}")
    except Exception as exc:  # noqa: BLE001 — smoke test, surface & continue
        print(f"\ndevices: skipped ({type(exc).__name__}: {exc})")
