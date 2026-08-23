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

Data layout (see ``docs/datatables/hitachi/meas_hist.txt`` for the full mapping):

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
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any

from back_dev_home._runtime.office_redis import (
    read_dataframe,
    redis_client,
)
# Generic OpenSearch mechanics live in _office_search.py. Re-exported here so
# the adapters that predate the split (recipe_tat, fail_issue, meas_hist) keep
# importing them from this module unchanged.
from back_dev_home.ebeam._office_search import (  # noqa: F401
    CACHE_TTL_SECONDS,
    KST,
    MAX_INNER_RESULT_WINDOW,
    aggregate,
    client,
    fetch_hits,
    parse_dt,
    query,
    search,
    text,
    top_hits,
    ttl_cache,
)
from back_dev_home.ebeam.recipe_tat.contracts import ToolType


_LOG = logging.getLogger(__name__)


# tool_type -> OpenSearch alias.
INDEX: dict[ToolType, str] = {
    "cd-sem": "meas_hist_cdsem",
    "hv-sem": "meas_hist_hvsem",
}
# Both aliases together — used only to anchor on the global latest timestamp.
ALL_INDICES = ",".join(INDEX.values())

# Time / metric fields (both are proper numeric/date types — no .keyword).
TIME_FIELD = "timestamp"   # date: drives the range filter, histogram, anchor
# long (seconds). NOT present on every document: meastime exists only where
# msr_check == "Yes" (user-confirmed 2026-08-10). This comment used to claim
# "every doc has one", which made value_count(meastime) look interchangeable
# with a document count — it is not, and the two disagreed on live data while
# agreeing on every mock row. See DOC_COUNT_AGG below.
MEAS_FIELD = "meastime"

# "How many documents are in scope", as an aggregation.
#
# `aggregate()` returns only the `aggregations` object, so `hits.total` is not
# available to callers. Counting TIME_FIELD is exact rather than approximate:
# `filter_clauses` always includes a `range` on it, and a range query only
# matches documents that HAVE the field, so every document in scope carries a
# timestamp by construction.
#
# Use this — never value_count(MEAS_FIELD) — wherever the number means
# "executions". An execution whose MSR file never landed still ran.
DOC_COUNT_AGG: dict[str, Any] = {"value_count": {"field": TIME_FIELD}}

# Exact-match / aggregation fields go through their .keyword sub-fields.
FULL_NAME_KW = "full_name.keyword"   # class_name/recipe_name composite group key
FAB_NAME_KW = "fab_name.keyword"     # fab selection filter
EQP_ID_KW = "eqp_id.keyword"         # sample_eqp_ids
LOT_ID_KW = "lot_id.keyword"         # device roll-ups + lot_cd drill-down
# 장비별 뷰의 모델 열. OFFICE-VERIFY: docs/datatables/hitachi/meas_hist.txt 는
# eqp_model_cd 를 text 로만 적고 있어 .keyword 서브필드 존재가 미확인입니다.
# **없어도 예외가 나지 않습니다** — 매핑에 없는 필드를 composite 소스로 쓰면
# 매칭되는 문서가 없어 버킷이 0개가 되고, /equipments 는 200 에 빈 표를
# 돌려줍니다("이 기간에 데이터 없음"과 구분되지 않습니다). 크래시를 기다리지
# 말고 recipe_tat/MIGRATION.md 의 실행 수 대조를 돌리십시오. 대처는 이 소스를
# 빼고 모델을 다른 경로로 되찾는 것 — 버킷당 top_hits(size 1) 또는 sem_list 의
# 장비 카탈로그. 분석되는 raw text 필드로 그냥 바꾸면 안 됩니다: 토큰화되어
# "VERITYSEM_5" 가 "veritysem"/"5" 로 쪼개진 채 모델명 행세를 합니다
# (이쪽도 에러 없이 조용히 틀립니다).
EQP_MODEL_CD_KW = "eqp_model_cd.keyword"

# ── the measurement id (msr) ────────────────────────────────────────────────
# ``_id`` and the ``msr`` field are SUPPOSED to hold the same value
# (user-confirmed 2026-08-20), and the ``msr`` field is what this app has read
# all along. The helpers below exist because that invariant is currently
# broken on the write side: recently ingested documents carry no ``msr`` field
# at all -- 21,474 of 2,250,652 as of 2026-08-20, believed to be a scheduler /
# loader defect rather than a schema change. The newest documents are the
# affected ones, which is the segment a default 스큐보아 search returns, so
# reading only ``_source["msr"]`` hands the frontend an empty identity for
# exactly the rows a user is most likely to click -- the row goes dead while
# its ``minio_msr``/``minio_pkl`` sit populated in the same document.
#
# So this is a safety net over an upstream bug, NOT a blessing of documents
# without ``msr``: the loader still needs fixing and the affected documents
# still want a backfill. What the net buys is that neither one has to happen
# before the screens work, and that a future recurrence cannot black them out
# again.
#
# Every office adapter that needs a measurement id must go through the two
# helpers below rather than touching ``_source["msr"]``. The field stays the
# preferred source where it exists -- it is the same value, and behaviour is
# then identical to before for every document that has it.
MSR_KW = "msr.keyword"


def msr_of(hit: Mapping[str, Any]) -> str:
    """The measurement id of a search hit. Never empty for a real document."""
    return text(hit.get("_source", {}).get("msr")) or text(hit.get("_id"))


def msr_clause(values: Sequence[str]) -> dict[str, Any] | None:
    """Match documents whose msr is any of ``values``.

    Two clauses OR'd, because the same id lives in two places depending on the
    document: a ``terms`` on the field for those that have it, and an ``ids``
    query for those where only ``_id`` carries it. A lookup that queried only
    ``MSR_KW`` would 404 on every document ingested without the field.
    """
    wanted = [v for v in values if v]
    if not wanted:
        return None
    return {
        "bool": {
            "should": [
                {"terms": {MSR_KW: wanted}},
                {"ids": {"values": wanted}},
            ],
            "minimum_should_match": 1,
        }
    }


def iso_date_or_none(value: str | None) -> str | None:
    """``value`` when it is a real ``yyyy-MM-dd`` date, else ``None``.

    The mocks route every bound through ``_analytics.parse_iso_date``, which
    returns None on garbage and so simply drops the filter. The office side had
    no equivalent, and both ways it consumes a bound failed loudly on
    ``?start_date=2026-13-01``: ``date.fromisoformat`` below raises ValueError
    in-process, and a raw bound in ``gte`` / ``extended_bounds`` makes
    OpenSearch answer with a parse error. Either way one malformed query
    parameter 500s an endpoint that answers fine at home.

    Dropping an unparseable bound rather than rejecting it is the parity
    choice: it is what the mocks already do. Validating at the route and
    answering 400 would be better API behavior, but that is a contract change
    for both providers, not a home/office divergence fix.

    Round-tripping through ``isoformat()`` rather than just parsing is
    deliberate: since 3.11 ``date.fromisoformat`` also accepts basic forms like
    ``20260101``, which would sail through a bare try/except and then be
    rejected by OpenSearch anyway, because every bound below is sent under
    ``"format": "yyyy-MM-dd"``. Only the canonical spelling is safe to forward.
    """
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return value if parsed.isoformat() == value else None


def histogram_bounds(start_date: str | None, end_date: str | None) -> dict[str, str] | None:
    """``extended_bounds`` for a day histogram, or None when unusable.

    Mirrors the mocks' backfill guard, which needs both ends to parse and to be
    the right way round before it will zero-fill.
    """
    start = iso_date_or_none(start_date)
    end = iso_date_or_none(end_date)
    if start is None or end is None or start > end:
        return None
    return {"min": start, "max": end}


def _range_clause(start_date: str | None, end_date: str | None) -> dict[str, Any]:
    """Inclusive-day range on ``timestamp``.

    Bounds are dates (``yyyy-MM-dd``, UTC). We use ``gte start`` and
    ``lt end+1day`` so the whole of ``end_date`` is included — matching the
    mocks, which compare the ``YYYY-MM-DD`` slice with ``<=``.
    """
    start = iso_date_or_none(start_date)
    end = iso_date_or_none(end_date)
    bounds: dict[str, Any] = {"format": "yyyy-MM-dd"}
    if start:
        bounds["gte"] = start
    if end:
        end_excl = date.fromisoformat(end) + timedelta(days=1)
        bounds["lt"] = end_excl.isoformat()
    return {"range": {TIME_FIELD: bounds}}


def filter_clauses(
    fab_names: Sequence[str] | None,
    start_date: str | None,
    end_date: str | None,
    lot_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = [_range_clause(start_date, end_date)]
    # fab_name is stored uppercase (M16A, R3, ...); the mocks compare
    # case-insensitively, so uppercase the terms for parity. One fab keeps the
    # exact single-`term` shape existing office queries produce.
    wanted = [fab.strip().upper() for fab in (fab_names or []) if fab.strip()]
    if len(wanted) == 1:
        clauses.append({"term": {FAB_NAME_KW: wanted[0]}})
    elif wanted:
        clauses.append({"terms": {FAB_NAME_KW: wanted}})
    if lot_ids is not None:
        clauses.append({"terms": {LOT_ID_KW: lot_ids}})
    return clauses


_COMPOSITE_PAGE_SIZE = 1000


def _composite_sources(field: str | Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
    """composite 의 sources 절을 만듭니다.

    문자열 하나면 예전과 똑같이 ``group`` 이라는 이름의 소스 하나입니다 —
    기존 호출자(사무실의 갱신되지 않은 office.py 포함)가 그대로 동작해야
    합니다. (이름, 필드) 목록을 주면 그 순서대로 다중 소스가 됩니다.
    """
    if isinstance(field, str):
        return [{"group": {"terms": {"field": field}}}]
    return [{name: {"terms": {"field": path}}} for name, path in field]


def _validate_composite_key(
    key: Mapping[str, Any],
    names: tuple[str, ...],
    *,
    location: str,
    label: str,
) -> None:
    """Check a composite ``key``/``after_key`` against the declared sources.

    Shared by the bucket and ``after_key`` checks. The one-source wording is
    kept verbatim — a message an office operator has already seen once should
    not change spelling just because the helper learned to take more sources.

    NOTE: this rejects a ``null`` key value, so ``missing_bucket: true`` on any
    composite source is NOT a drop-in change — that option's whole point is a
    bucket whose key value is ``null`` for the missing field. Anyone turning it
    on to stop `missing_bucket: false` from dropping documents (see
    recipe_tat/MIGRATION.md) has to relax this check for that source first.
    """
    if set(key) != set(names):
        expected = (
            f"exactly one key named {names[0]!r}"
            if len(names) == 1
            else f"exactly the keys {list(names)!r}"
        )
        raise RuntimeError(
            f"{location} {label!r} must contain {expected}; "
            f"got keys {list(key)!r}."
        )
    for name in names:
        value = key[name]
        if value is None or not isinstance(value, (str, int, float, bool)):
            raise RuntimeError(
                f"{location} '{label}.{name}' must be a non-null JSON scalar "
                f"(string, number, or boolean); got {type(value).__name__}."
            )


def _validated_composite_bucket(
    bucket: Any,
    names: tuple[str, ...],
    *,
    index: str,
    page_number: int,
    bucket_position: int,
) -> dict[str, Any]:
    location = (
        f"OpenSearch composite bucket {bucket_position} on page {page_number} "
        f"for {index!r}"
    )
    if not isinstance(bucket, Mapping):
        raise RuntimeError(f"{location} must be a mapping.")
    key = bucket.get("key")
    if not isinstance(key, Mapping):
        raise RuntimeError(f"{location} 'key' must be a mapping.")
    _validate_composite_key(key, names, location=location, label="key")
    return dict(bucket)


def composite_buckets(
    index: str,
    field: str | Sequence[tuple[str, str]],
    sub_aggs: dict[str, Any],
    query_body: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Every bucket for a terms/composite grouping via a paginated composite aggregation.

    A plain ``terms`` agg has two problems here: it truncates at ``size`` (the
    fleet has far more recipes/lots than any fixed cap over a wide date range),
    and when ordered by a sub-agg sum it is *approximate* — each shard sends
    its local top-N, so bucket totals can be wrong. ``composite`` walks every
    bucket exactly, one page of ``after_key`` at a time; sums per bucket are
    exact. Callers sort the complete list themselves.

    Each page bucket carries ``key.group`` (the term), ``doc_count``, and the
    requested ``sub_aggs`` results. ``sub_aggs`` may be empty (bucket walk
    only — e.g. a distinct count that needs post-mapping in Python).

    ``field`` 가 문자열이면 버킷 키는 ``key.group`` 입니다(기존 동작).
    (이름, 필드) 목록을 주면 ``key.<이름>`` 으로 각각 접근합니다.
    """
    sources = _composite_sources(field)
    names = tuple(next(iter(source)) for source in sources)
    buckets: list[dict[str, Any]] = []
    after: dict[str, Any] | None = None
    seen_after_keys: list[dict[str, Any]] = []
    page_number = 1
    while True:
        composite: dict[str, Any] = {
            "size": _COMPOSITE_PAGE_SIZE,
            "sources": sources,
        }
        if after is not None:
            composite["after"] = after
        body: dict[str, Any] = {"comp": {"composite": composite}}
        if sub_aggs:
            body["comp"]["aggs"] = sub_aggs
        result = aggregate(index, body, query_body)
        if not isinstance(result, Mapping):
            raise RuntimeError(
                f"OpenSearch composite page {page_number} for {index!r} "
                "must be a mapping."
            )
        if "comp" not in result:
            raise RuntimeError(
                f"OpenSearch composite page {page_number} for {index!r} "
                "is missing the 'comp' aggregation."
            )
        page = result["comp"]
        if not isinstance(page, Mapping):
            raise RuntimeError(
                f"OpenSearch composite page {page_number} for {index!r} "
                "'comp' must be a mapping."
            )
        if "buckets" not in page:
            raise RuntimeError(
                f"OpenSearch composite page {page_number} for {index!r} "
                "is missing 'buckets'."
            )
        page_buckets = page["buckets"]
        if not isinstance(page_buckets, list):
            raise RuntimeError(
                f"OpenSearch composite page {page_number} for {index!r} "
                "'buckets' must be a list."
            )
        for bucket_position, bucket in enumerate(page_buckets, start=1):
            buckets.append(
                _validated_composite_bucket(
                    bucket,
                    names,
                    index=index,
                    page_number=page_number,
                    bucket_position=bucket_position,
                )
            )
        if "after_key" not in page:
            break
        next_after = page["after_key"]
        if not isinstance(next_after, Mapping):
            raise RuntimeError(
                f"OpenSearch composite page {page_number} for {index!r} "
                "'after_key' must be a mapping when present."
            )
        _validate_composite_key(
            next_after,
            names,
            location=f"OpenSearch composite page {page_number} for {index!r}",
            label="after_key",
        )
        after_key = dict(next_after)
        if any(after_key == seen for seen in seen_after_keys):
            raise RuntimeError(
                f"OpenSearch composite page {page_number} for {index!r} "
                "returned a repeated 'after_key'."
            )
        seen_after_keys.append(after_key)
        if len(page_buckets) < _COMPOSITE_PAGE_SIZE:
            break
        after = after_key
        page_number += 1
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


# NOTE: ``text()`` (imported above) is what normalizes the office catalogs'
# several spellings of "missing" — real None/NaN/pd.NA, and the literal string
# "None" written by the upstream loader — to "" so they fall out of lot_cd keys
# and metadata instead of surfacing as "None" text.


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
        for lot_id, lot_cd in zip(df["lot_id"].tolist(), df["lot_cd"].tolist(), strict=True):
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
