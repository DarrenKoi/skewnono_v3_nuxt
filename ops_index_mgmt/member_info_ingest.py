"""Roster ingest, prune, and scheduled refresh for the member_info index.

The index itself (mappings, settings, create) lives in `member_info.py`; this
module only *handles data*. It imports INDEX_NAME / ID_FIELD from there so the
index definition stays the single source of truth.

The roster arrives from an HTTP source as a DataFrame, turned into a list of
dicts (`df.to_dict("records")`) for ingest. The scheduled job's single entry
point is `refresh_member_directory`, which upserts everyone present and prunes
those who have been gone past a grace window -- built so a dropped/partial HTTP
fetch is harmless (see its docstring).

To run the ingest standalone, `create_member_doc_service()` builds the OSDoc
itself (its client comes from `create_skewnono_client` in `member_info.py`,
which wraps ops_store's `create_client`), so no separate wiring is needed:

    refresh_member_directory(create_member_doc_service(), df.to_dict("records"))
"""

from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ops_store import OSDoc, normalize_document

from ops_index_mgmt.member_info import (
    ID_FIELD,
    INDEX_NAME,
    create_skewnono_client,
)


def create_member_doc_service(client: Any | None = None) -> OSDoc:
    """Return an OSDoc bound to the member_info index, ready to ingest.

    This is what lets the module run on its own: with no `client`, it builds one
    via `create_skewnono_client` (defined in `member_info.py`, which wraps
    ops_store's `create_client` with the skewnono cluster credentials), so a
    scheduled job or a standalone script can do the whole refresh in one line --

        refresh_member_directory(create_member_doc_service(), df.to_dict("records"))

    without wiring up the OpenSearch client itself. Pass an existing `client` to
    reuse a connection (e.g. when sharing one across indices, or in tests).
    """

    actual_client = client or create_skewnono_client()
    return OSDoc(client=actual_client, index=INDEX_NAME)


def has_emp_no(member: Mapping[str, Any]) -> bool:
    """Return True if `member` carries a usable EMP_NO to key the document on.

    Rows without one cannot get a stable `_id`, so they are skipped at ingest
    (`iter_member_actions` filters with this) rather than landing as random-id
    duplicates that a roster refresh could never overwrite.
    """

    value = member.get(ID_FIELD)
    return value is not None and str(value).strip() != ""


def iter_member_actions(
    members: Iterable[Mapping[str, Any]],
    *,
    os_inserted: str,
    op_type: str = "index",
    normalize: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield raw bulk actions for roster rows, keyed on EMP_NO.

    Each row becomes one document whose `_id` is its EMP_NO, so re-ingesting the
    roster overwrites the same person instead of appending a duplicate. Rows
    failing `has_emp_no` are silently skipped. The shared `os_inserted` stamp
    (KST, tz-aware — the caller computes one value for the whole batch) is added
    to `_source`.

    `normalize` defaults to True because the roster arrives as DataFrame rows
    (`df.to_dict("records")`): it runs `normalize_document` to coerce `NaN`/`NaT`
    to None, numpy scalars to native types, and Timestamps to ISO strings — all
    of which are otherwise invalid JSON that breaks the bulk insert. It runs
    *before* the EMP_NO check, so a missing EMP_NO that came in as `NaN`
    (whose `str()` is the non-blank "nan") is correctly skipped. Pass
    `normalize=False` only when the rows are already JSON-clean.

    `op_type` defaults to `"index"` (upsert: overwrite by EMP_NO — the
    roster-refresh semantics); pass `"create"` to instead surface already-present
    EMP_NOs as 409s. Feed the result straight to `OSDoc.bulk`.
    """

    for member in members:
        source = normalize_document(member) if normalize else dict(member)
        if not has_emp_no(source):
            continue
        yield {
            "_op_type": op_type,
            "_index": INDEX_NAME,
            "_id": str(source[ID_FIELD]),
            "_source": {**source, "os_inserted": os_inserted},
        }


def current_kst_stamp() -> str:
    """Return the current KST timestamp as an ISO string (the os_inserted value).

    One run computes a single stamp and shares it between `ingest_members` and
    `prune_stale_members` so the prune boundary lines up exactly with the upsert
    stamp.
    """

    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat()


def ingest_members(
    doc_service: OSDoc,
    members: Iterable[Mapping[str, Any]],
    *,
    refresh: bool = False,
    normalize: bool = True,
    os_inserted: str | None = None,
) -> tuple[int, list[Any]]:
    """Bulk-upsert roster rows into member_info, keyed on EMP_NO.

    Stamps one KST `os_inserted` for the whole batch, builds upsert actions via
    `iter_member_actions`, and bulk-indexes them. Returns `OSDoc.bulk`'s
    `(indexed, errors)`. `refresh` is left off by default so the index's own
    refresh cadence applies; pass `refresh=True` for a small one-off load you
    want searchable immediately.

    `normalize` defaults to True for the DataFrame source (`df.to_dict("records")`):
    it makes `NaN`/`NaT`/numpy/Timestamp cells JSON-safe before they reach the
    bulk API. The whole scheduled extract→update step is therefore one call:

        doc = OSDoc(client=client, index="member_info")
        indexed, errors = ingest_members(doc, df.to_dict("records"))

    Pass `os_inserted` to reuse a stamp from `current_kst_stamp` when a later
    `prune_stale_members` needs the same boundary (or just call
    `refresh_member_directory`, which wires both together).
    """

    stamp = os_inserted or current_kst_stamp()
    return doc_service.bulk(
        iter_member_actions(members, os_inserted=stamp, normalize=normalize),
        refresh=refresh,
    )


def prune_stale_members(
    client: Any,
    *,
    before: str,
    refresh: bool = False,
) -> dict[str, Any]:
    """Delete member docs not refreshed at/after `before` (people who left).

    `ingest_members` re-stamps every still-present person with the run's KST
    `os_inserted`. Anyone carrying a strictly older `os_inserted` was absent from
    this run's roster -- i.e. they left -- so a `delete_by_query` on
    `os_inserted < before` removes exactly them. Pass the SAME stamp the ingest
    used as `before`: just-upserted docs carry `os_inserted == before`, which the
    strict `lt` range excludes, so they survive.

    Make the upserts visible before calling this (ingest with `refresh=True`, or
    use `refresh_member_directory`); otherwise the query can still match a
    re-stamped person's pre-refresh `os_inserted` and delete someone still on the
    roster. Returns the raw `delete_by_query` response (`deleted`, `total`, ...).
    """

    body = {"query": {"range": {"os_inserted": {"lt": before}}}}
    return client.delete_by_query(index=INDEX_NAME, body=body, refresh=refresh)


def refresh_member_directory(
    doc_service: OSDoc,
    members: Iterable[Mapping[str, Any]],
    *,
    stale_after: timedelta | None = None,
    min_rows: int = 1,
    normalize: bool = True,
) -> dict[str, Any]:
    """Run one roster refresh, resilient to a flaky HTTP source.

    The scheduled job's single entry point, built so a dropped/partial HTTP
    response is harmless:

    - Upsert is self-healing. A member missing from one fetch keeps their
      previous `os_inserted` and stays searchable; the next successful run
      re-stamps them. No member is lost by being missed once.

    - Pruning uses a grace window, not a single run. `stale_after` (a timedelta)
      deletes only members whose `os_inserted` is older than `now - stale_after`,
      so a transient miss never deletes anyone -- they are re-stamped well within
      the window. Leave `stale_after=None` (default) to skip pruning entirely;
      pass e.g. `timedelta(days=14)` once you trust the source over that span.

    - `min_rows` guards against a truncated fetch: if fewer than `min_rows` rows
      arrive, the whole run is skipped (no upsert, no prune) so one bad HTTP
      response cannot blank or decimate the directory. Set it near your real
      roster size (e.g. 90% of it).

    The upsert runs with `refresh=True` so the re-stamped docs are searchable
    before the prune query reads `os_inserted`. Returns
    `{"stamp", "indexed", "errors", "pruned", "skipped"}`; on a guarded skip,
    `stamp` is None and `skipped` explains why.
    """

    rows = list(members)
    if len(rows) < min_rows:
        return {
            "stamp": None,
            "indexed": 0,
            "errors": [],
            "pruned": None,
            "skipped": f"fetched {len(rows)} rows, below min_rows={min_rows}",
        }

    stamp = current_kst_stamp()
    indexed, errors = ingest_members(
        doc_service, rows, os_inserted=stamp, normalize=normalize, refresh=True
    )

    pruned = None
    if stale_after is not None:
        cutoff = (datetime.now(ZoneInfo("Asia/Seoul")) - stale_after).isoformat()
        pruned = prune_stale_members(doc_service.client, before=cutoff, refresh=True)

    return {
        "stamp": stamp,
        "indexed": indexed,
        "errors": errors,
        "pruned": pruned,
        "skipped": None,
    }
