"""Create Hitachi IDP version rollover indices and their shared ISM policy."""

import argparse
import json
from typing import Any

from ops_store import OSIndex, create_client

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_ALIASES = ("cdsem_idp_ver", "hvsem_idp_ver")
POLICY_ID = "hitachi_idp_ver_retention_policy"

SHARDS = 2
REPLICAS = 1
REFRESH_INTERVAL = "30s"

ROLLOVER_DOC_COUNT = 1000000
RETENTION_AGE = "1095d"
POLICY_PRIORITY = 100


def index_pattern(alias: str) -> str:
    return f"{alias}-*"


def backing_index(alias: str) -> str:
    return f"{alias}-000001"


def index_template_name(alias: str) -> str:
    return f"{alias}_template"


def build_mappings() -> dict[str, Any]:
    """Return mappings: explicit date fields plus *_tm/*_dt safety net.

    OpenSearch's built-in dynamic date detection only matches
    `yyyy/MM/dd[ HH:mm:ss]` and `epoch_millis`, so ISO-8601 timestamp
    strings would otherwise be mapped as `text`. Explicit properties
    pin the two known time fields; the dynamic templates catch any
    other timestamp-shaped columns the dataframe brings in.

    - `modified`    : data-time from the IDP file (may be years old).
    - `os_inserted` : KST timestamp refreshed on every write (bulk
                      index, update, upsert, bulk update). Despite the
                      name it means "last touched in OS" — used for
                      operational cleanup of the live write index by
                      activity, not by ingest cohort.
    Reference-only wide objects (`raw_data`, `parameters`,
    `wafer_para_loc_info`) are mapped
    `enabled: false`: stored verbatim in `_source` and returned on
    fetch, but never parsed or indexed. Their
    (potentially hundreds of) subfields therefore never count against
    `index.mapping.total_fields.limit` (default 1000), which is what was
    blowing up dynamic mapping. Trade-off: their subfields are NOT
    searchable/aggregatable — promote any key you need to query to a
    real top-level field instead.

    - `modified`    : data-time from the IDP file (may be years old).
    - `os_inserted` : KST timestamp refreshed on every write (bulk
                      index, update, upsert, bulk update). Despite the
                      name it means "last touched in OS" — used for
                      operational cleanup of the live write index by
                      activity, not by ingest cohort.
    """

    return {
        "properties": {
            "modified": {"type": "date"},
            "os_inserted": {"type": "date"},
            "raw_data": {"type": "object", "enabled": False},
            "parameters": {"type": "object", "enabled": False},
            "wafer_para_loc_info": {"type": "object", "enabled": False},
        },
        "dynamic_templates": [
            {
                "tm_suffix_as_date": {
                    "match_mapping_type": "string",
                    "match": "*_tm",
                    "mapping": {"type": "date"},
                }
            },
            {
                "dt_suffix_as_date": {
                    "match_mapping_type": "string",
                    "match": "*_dt",
                    "mapping": {"type": "date"},
                }
            },
        ],
    }


def build_index_settings(alias: str) -> dict[str, Any]:
    """Return index settings shared by the template and first backing index."""

    return {
        "number_of_shards": SHARDS,
        "number_of_replicas": REPLICAS,
        "refresh_interval": REFRESH_INTERVAL,
        "plugins.index_state_management.rollover_alias": alias,
    }


def build_ism_policy_body() -> dict[str, Any]:
    """Return one ISM policy shared by both IDP version index families."""

    index_patterns = [index_pattern(alias) for alias in INDEX_ALIASES]
    return {
        "policy": {
            "description": (
                f"Rollover Hitachi IDP version indices after "
                f"{ROLLOVER_DOC_COUNT} docs and delete backing indices "
                f"after {RETENTION_AGE}."
            ),
            "schema_version": 1,
            "default_state": "hot",
            "states": [
                {
                    "name": "hot",
                    "actions": [
                        {
                            "rollover": {
                                "min_doc_count": ROLLOVER_DOC_COUNT,
                            }
                        }
                    ],
                    "transitions": [
                        {
                            "state_name": "delete",
                            "conditions": {
                                "min_index_age": RETENTION_AGE,
                            },
                        }
                    ],
                },
                {
                    "name": "delete",
                    "actions": [{"delete": {}}],
                    "transitions": [],
                },
            ],
            "ism_template": [
                {
                    "index_patterns": index_patterns,
                    "priority": POLICY_PRIORITY,
                }
            ],
        }
    }


def build_index_template_body(alias: str) -> dict[str, Any]:
    """Return the composable index template for one rollover family."""

    return {
        "index_patterns": [index_pattern(alias)],
        "priority": POLICY_PRIORITY,
        "template": {
            "settings": build_index_settings(alias),
            "mappings": build_mappings(),
        },
        "_meta": {
            "description": (
                f"Settings + mappings for the {alias} rollover family."
            )
        },
    }


def build_initial_index_body(alias: str) -> dict[str, Any]:
    """Return the body used to create the first concrete backing index."""

    return {
        "settings": build_index_settings(alias),
        "mappings": build_mappings(),
        "aliases": {
            alias: {"is_write_index": True},
        },
    }


def create_skewnono_client() -> Any:
    """Create a client for the skewnono OpenSearch cluster."""

    if not OPENSEARCH_PASSWORD:
        raise RuntimeError(
            "Set OPENSEARCH_PASSWORD at the top of "
            "ops_index_mgmt/hitachi_idp_ver.py before running this script."
        )
    return create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )


def put_ism_policy(client: Any) -> dict[str, Any]:
    """Create or update the shared ISM policy."""

    return client.transport.perform_request(
        "PUT",
        f"/_plugins/_ism/policies/{POLICY_ID}",
        body=build_ism_policy_body(),
    )


def put_index_template(client: Any, alias: str) -> dict[str, Any]:
    """Create or update one index template used by rollover-created indices."""

    return client.transport.perform_request(
        "PUT",
        f"/_index_template/{index_template_name(alias)}",
        body=build_index_template_body(alias),
    )


def put_index_templates(client: Any) -> dict[str, dict[str, Any]]:
    """Create or update all IDP version index templates."""

    return {
        alias: put_index_template(client, alias)
        for alias in INDEX_ALIASES
    }


def put_live_index_mappings(client: Any) -> dict[str, dict[str, Any]]:
    """Add newly declared mapping fields to the already-created indices.

    Index templates only shape indices created *after* the template is
    updated, so a field added to `build_mappings()` never reaches the
    backing indices that already exist. `PUT mapping` is additive: it
    creates new fields and is a no-op for fields whose definition is
    unchanged. It CANNOT redefine an already-mapped field, so run this
    only before the new field has been ingested — once a document writes
    it, dynamic mapping fixes its type and the `enabled: false` change is
    rejected. Targets the rollover aliases, so the write index of each
    family picks the new field up immediately.
    """

    return {
        alias: client.indices.put_mapping(index=alias, body=build_mappings())
        for alias in INDEX_ALIASES
    }


def ensure_rollover_index(client: Any, alias: str) -> dict[str, Any]:
    """Create the first backing index if the rollover alias does not exist."""

    first_index = backing_index(alias)
    index_service = OSIndex(client=client, index=alias)

    if index_service.exists(alias):
        description = index_service.describe(alias)
        rollover = description["rollover"]
        if not rollover["ready"] or not rollover["uses_numbered_suffix"]:
            raise RuntimeError(
                f"{alias} already exists, but it is not a rollover alias "
                "with a numbered write index. Move or reindex it before "
                "running this setup."
            )
        return {
            "created": False,
            "alias": alias,
            "write_index": rollover["write_index"],
            "description": description,
        }

    if index_service.exists(first_index, include_aliases=False):
        raise RuntimeError(
            f"{first_index} already exists without the {alias} rollover "
            "alias. Add the alias manually or remove the conflicting index."
        )

    response = index_service.create(
        index=first_index,
        mappings=build_mappings(),
        settings=build_index_settings(alias),
        aliases={alias: {"is_write_index": True}},
        shards=SHARDS,
        replicas=REPLICAS,
        refresh_interval=REFRESH_INTERVAL,
    )
    return {
        "created": True,
        "alias": alias,
        "write_index": first_index,
        "response": response,
    }


def ensure_rollover_indices(client: Any) -> dict[str, dict[str, Any]]:
    """Ensure both IDP version rollover aliases have a first backing index."""

    return {
        alias: ensure_rollover_index(client, alias)
        for alias in INDEX_ALIASES
    }


def build_dry_run_plan() -> dict[str, Any]:
    """Return the requests this script will send without connecting."""

    return {
        "cluster": {
            "host": OPENSEARCH_HOST,
            "user": OPENSEARCH_USER,
            "password_set": bool(OPENSEARCH_PASSWORD),
        },
        "policy_request": {
            "method": "PUT",
            "path": f"/_plugins/_ism/policies/{POLICY_ID}",
            "body": build_ism_policy_body(),
        },
        "template_requests": {
            alias: {
                "method": "PUT",
                "path": f"/_index_template/{index_template_name(alias)}",
                "body": build_index_template_body(alias),
            }
            for alias in INDEX_ALIASES
        },
        "initial_index_requests": {
            alias: {
                "method": "PUT",
                "path": f"/{backing_index(alias)}",
                "body": build_initial_index_body(alias),
            }
            for alias in INDEX_ALIASES
        },
    }


def setup_hitachi_idp_ver(client: Any | None = None) -> dict[str, Any]:
    """Create/update policy and templates, then ensure both indices exist."""

    actual_client = client or create_skewnono_client()
    return {
        "policy": put_ism_policy(actual_client),
        "index_templates": put_index_templates(actual_client),
        "indices": ensure_rollover_indices(actual_client),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create cdsem_idp_ver and hvsem_idp_ver rollover indices, "
            "index templates, aliases, and a shared 3-year ISM policy."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the OpenSearch requests without connecting to the cluster.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        result = build_dry_run_plan()
    else:
        result = setup_hitachi_idp_ver()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Reference: ingesting a dataframe into cdsem_idp_ver / hvsem_idp_ver
# ---------------------------------------------------------------------------
# Not executed by this script. Copy/adapt at the office once indices exist.
#
# import pandas as pd
# from ops_store import OSDoc, create_client
#
# client = create_client(
#     host=OPENSEARCH_HOST,
#     user=OPENSEARCH_USER,
#     password=OPENSEARCH_PASSWORD,
# )
# doc_service = OSDoc(client=client)
#
# # 1. The `modified` column must be a real datetime before
# #    bulk_index_dataframe serializes it. Strings left as object dtype
# #    would round-trip as text and break range queries.
# cdsem_df["modified"] = pd.to_datetime(cdsem_df["modified"], errors="coerce")
#
# # 1b. Stamp ingest-time in KST. Must be tz-aware — a naive isoformat
# #     like "2026-05-20T14:30:00" is parsed by OpenSearch as UTC and
# #     bakes in a 9-hour drift. ZoneInfo("Asia/Seoul") makes the
# #     "+09:00" offset explicit so the value round-trips correctly.
# from datetime import datetime
# from zoneinfo import ZoneInfo
# os_inserted_kst = (
#     datetime.now(tz=ZoneInfo("Asia/Seoul"))
#     .replace(microsecond=0)
#     .isoformat()
# )
# cdsem_df["os_inserted"] = os_inserted_kst   # same value for the whole batch
#
# # 2. Drop rows with empty/NaN doc_id, then drop in-batch duplicates.
# #    Nullable "string" dtype keeps NaN as NA (plain astype(str) would
# #    turn NaN into the literal "nan" and slip past the filter).
# before = len(cdsem_df)
# cdsem_df["doc_id"] = cdsem_df["doc_id"].astype("string").str.strip()
# cdsem_df = cdsem_df[cdsem_df["doc_id"].notna() & (cdsem_df["doc_id"] != "")]
# cdsem_df = cdsem_df.drop_duplicates(subset="doc_id", keep="first")
# print(f"filtered {before - len(cdsem_df)} rows (empty or duplicate doc_id)")
#
# # 3. Bulk index. op_type="create" surfaces duplicate doc_id on re-runs;
# #    switch to "index" only if you want upsert-by-doc_id semantics.
# success_count, errors = doc_service.bulk_index_dataframe(
#     cdsem_df,
#     index="cdsem_idp_ver",
#     id_field="doc_id",
#     op_type="create",
# )
# print(f"indexed: {success_count}, errors: {len(errors)}")


# ---------------------------------------------------------------------------
# Reference: looking up documents by id (study examples — not executed)
# ---------------------------------------------------------------------------
# Key idea: the ingest examples above use `id_field="doc_id"`, which tells
# OSDoc to copy the dataframe's `doc_id` column into OpenSearch's primary
# key field `_id`. So "search by id" against these indices is really a
# `_id` lookup, and the cheapest path is OSDoc.get / OSDoc.get_many — they
# hit the GET / MGET endpoints (real-time, no search refresh, no scoring),
# not the _search API.
#
# from ops_store import OSDoc, OSSearch, create_client
#
# client = create_client(
#     host=OPENSEARCH_HOST,
#     user=OPENSEARCH_USER,
#     password=OPENSEARCH_PASSWORD,
# )
# doc_service = OSDoc(client=client)
# search_service = OSSearch(client=client)
#
# # ---- 1. Single id lookup against one alias (cheapest, real-time) -----
# # Raises NotFoundError if the id doesn't exist in that alias.
# envelope = doc_service.get("LOTABC-001", index="cdsem_idp_ver")
# source = envelope["_source"]            # the actual document body
# index_name = envelope["_index"]         # which backing index served it
# print(source["modified"], index_name)
#
# # ---- 2. Batched lookup (one MGET round-trip, dict[id -> source|None]) -
# # Missing ids come back as None instead of raising — convenient when
# # checking a list pulled from somewhere else.
# wanted = ["LOTABC-001", "LOTABC-002", "LOTXYZ-999"]
# results = doc_service.get_many(wanted, index="cdsem_idp_ver")
# for doc_id, source in results.items():
#     if source is None:
#         print(f"{doc_id}: missing")
#     else:
#         print(f"{doc_id}: modified={source.get('modified')}")
#
# # ---- 3. Existence-only check (no _source returned — smaller payload) --
# present = doc_service.exists_many(wanted, index="cdsem_idp_ver")
# # -> {"LOTABC-001": True, "LOTABC-002": True, "LOTXYZ-999": False}
#
# # ---- 4. Don't know which tool the id lives under? Search both ---------
# # GET / MGET need a single index, but _search accepts a CSV of indices.
# # OSSearch.term filters on _id across both rollover families at once.
# hits = search_service.term(
#     field="_id",
#     value="LOTABC-001",
#     index="cdsem_idp_ver,hvsem_idp_ver",
#     size=1,
# )
# matches = hits["hits"]["hits"]          # list of {_index, _id, _source}
# if matches:
#     print(matches[0]["_index"], matches[0]["_source"])
#
# # ---- 5. "id" stored as a regular field, not as _id -------------------
# # If a column holds a logical id but was NOT used as `id_field=` at
# # ingest, OpenSearch generated random _ids and the logical id is just
# # another field. Use OSSearch.term against that field name instead:
# hits = search_service.term(
#     field="idp_ver_id",                 # whatever the actual column is
#     value="V2026.05.01",
#     index="cdsem_idp_ver",
#     size=10,
# )
# for hit in hits["hits"]["hits"]:
#     print(hit["_id"], hit["_source"])
#
# # ---- 6. Many logical-id values at once (terms query, not mget) -------
# hits = search_service.filter_terms(
#     {"idp_ver_id": ["V2026.05.01", "V2026.05.02"]},
#     index="cdsem_idp_ver",
#     size=100,
# )


# ---------------------------------------------------------------------------
# Reference: cleaning up stale docs on the live write index (study)
# ---------------------------------------------------------------------------
# ISM retention here is *index-age based* — it deletes whole backing
# indices 1095 days after they are created and never inspects any
# document field. For doc-level cleanup on the open (write) index —
# e.g. removing test/replay rows or pruning inactive records — drive a
# delete_by_query off `os_inserted`. Per the project convention this
# field is refreshed on every write, so the range filter below means
# "docs not touched since X", NOT "docs ingested before X".
#
# from opensearchpy.helpers import delete_by_query   # if you prefer the helper
#
# # Delete everything in the cdsem write index ingested before a KST date.
# response = client.delete_by_query(
#     index="cdsem_idp_ver",
#     body={
#         "query": {
#             "range": {
#                 "os_inserted": {"lt": "2026-01-01T00:00:00+09:00"}
#             }
#         }
#     },
#     conflicts="proceed",   # don't abort if a concurrent write bumps a doc
#     refresh=True,          # make the deletion visible to subsequent search
# )
# print(response["deleted"], "deleted,", response["version_conflicts"], "conflicts")


# ---------------------------------------------------------------------------
# Reference: updating fields on a doc that already exists by id (study)
# ---------------------------------------------------------------------------
# Three OSDoc methods look similar but mean very different things:
#
#   doc_service.update(id, {...})  -> partial patch; raises NotFoundError
#                                      if the id does not exist
#   doc_service.upsert(id, {...})  -> partial patch; CREATES the doc with
#                                      the given fields if it doesn't exist
#   doc_service.index(doc, id=id)  -> full REPLACE; any field not in the
#                                      payload is dropped from the stored doc
#
# Pick `update` when you want "change these fields on the existing record,
# fail loudly if I'm wrong about which id is there".
#
# from ops_store import OSDoc, create_client
# from datetime import datetime
# from zoneinfo import ZoneInfo
#
# client = create_client(
#     host=OPENSEARCH_HOST,
#     user=OPENSEARCH_USER,
#     password=OPENSEARCH_PASSWORD,
# )
# doc_service = OSDoc(client=client)
#
# # ---- 1. Patch a couple of fields on one doc --------------------------
# # Project convention: every write refreshes `os_inserted` to the
# # current KST timestamp, so it tracks "last touched in OS". The other
# # fields you don't name (e.g. `modified`) are preserved.
# now_kst = (
#     datetime.now(tz=ZoneInfo("Asia/Seoul"))
#     .replace(microsecond=0)
#     .isoformat()
# )
# response = doc_service.update(
#     "LOTABC-001",
#     {
#         "idp_ver_status": "verified",
#         "note_comment": "rechecked 2026-05-20",
#         "os_inserted": now_kst,
#     },
#     index="cdsem_idp_ver",
#     refresh="wait_for",   # block until visible to subsequent search
# )
# print(response["result"])   # -> "updated"  (a fresh os_inserted means
#                             #    OpenSearch will never report "noop")
#
# # ---- 2. Nested-object gotcha: top-level merge, subtree REPLACE -------
# # If the stored doc has   {"recipe": {"step": 2, "tool": "CD1"}}
# # and you send            {"recipe": {"step": 3}}
# # the result is           {"recipe": {"step": 3}}     <- "tool" is GONE.
# # To keep the other keys, read-modify-write or send the full subtree:
# current = doc_service.get("LOTABC-001", index="cdsem_idp_ver")["_source"]
# merged_recipe = {**current.get("recipe", {}), "step": 3}
# doc_service.update(
#     "LOTABC-001",
#     {"recipe": merged_recipe},
#     index="cdsem_idp_ver",
# )
#
# # ---- 3. Update if exists, create if missing (upsert) -----------------
# # Same partial-patch semantics as update, but creates the doc with the
# # given fields if the id is not present. Same convention applies: send
# # a fresh os_inserted so the field tracks "last touched in OS".
# doc_service.upsert(
#     "LOTABC-999",
#     {
#         "idp_ver_status": "pending",
#         "modified": "2026-05-20T09:00:00+09:00",
#         "os_inserted": now_kst,
#     },
#     index="cdsem_idp_ver",
# )
#
# # ---- 4. Update many docs in one round-trip (bulk update actions) -----
# # OSDoc.bulk takes raw bulk-API actions. Each "update" action's "doc"
# # is a partial patch with the same semantics as method 1. Stamp one
# # shared os_inserted for the whole batch so the cohort stays grouped.
# batch_kst = (
#     datetime.now(tz=ZoneInfo("Asia/Seoul"))
#     .replace(microsecond=0)
#     .isoformat()
# )
# patches = [
#     {"id": "LOTABC-001", "fields": {"idp_ver_status": "verified"}},
#     {"id": "LOTABC-002", "fields": {"idp_ver_status": "rejected"}},
# ]
# actions = (
#     {
#         "_op_type": "update",
#         "_index": "cdsem_idp_ver",
#         "_id": p["id"],
#         "doc": {**p["fields"], "os_inserted": batch_kst},
#     }
#     for p in patches
# )
# success_count, errors = doc_service.bulk(actions, refresh=True)
# print(f"updated: {success_count}, errors: {len(errors)}")
