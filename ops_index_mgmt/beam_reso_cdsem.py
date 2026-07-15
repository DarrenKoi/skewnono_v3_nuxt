"""Create beam_shape_cdsem + reso_center_cdsem indices and a shared ISM policy.

Both CD-SEM measurement indices share one rollover/retention policy (same
lifecycle: 500000-doc rollover safety net, 3-year retention). Only the
mappings differ — `reso_center_cdsem` carries three wide reference objects
mapped `enabled: false`; `beam_shape_cdsem` has no special fields.
"""

import argparse
import json
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from ops_store import OSIndex, create_client

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_ALIASES = ("beam_shape_cdsem", "reso_center_cdsem")
POLICY_ID = "beam_reso_cdsem_retention_policy"

SHARDS = 2
REPLICAS = 1
REFRESH_INTERVAL = "30s"

# Low-volume indices — rollover is a safety net, not an expected event. Each
# family stays a single backing index until it ever reaches 500000 docs.
ROLLOVER_DOC_COUNT = 500000
RETENTION_AGE = "1095d"  # 3 years
POLICY_PRIORITY = 100

# Dict-valued reference fields (sub-keys hold lists) kept in _source but never
# parsed/indexed — fetched whole to plot, not queried. Mapped enabled:false so
# their sub-keys cost nothing against the field limit. Keyed by alias.
STORE_ONLY_OBJECT_FIELDS = {
    "reso_center_cdsem": (
        "Resolution_Range",
        "Resolution_Range_Raw",
        "Resolution_Range_Smooth",
    ),
}

# Fields whose combined value identifies one measurement; joined to form _id.
ID_FIELDS = ("eqp_ip", "timestamp", "beam_condition")


def index_pattern(alias: str) -> str:
    return f"{alias}-*"


def backing_index(alias: str) -> str:
    return f"{alias}-000001"


def index_template_name(alias: str) -> str:
    return f"{alias}_template"


def make_doc_id(doc: Mapping[str, Any]) -> str:
    """Return the composite `_id` for one measurement document.

    Joins `eqp_ip`, `timestamp`, and `beam_condition` (in that order) with
    `_`. These three fields together identify a measurement, so deriving
    `_id` from them makes re-ingest idempotent: the same measurement always
    lands on the same `_id`. With `op_type="create"` a re-run then surfaces
    as a duplicate; with `op_type="index"` it overwrites in place. Values
    are `str()`-coerced so a non-string `timestamp` still joins cleanly.

    Raises `KeyError` if any of the three fields is missing — a document
    without them cannot get a stable id and should not be silently indexed
    under a malformed key. Filter with `has_id_fields` first if the batch
    may contain incomplete documents (`iter_bulk_actions` does this).
    """

    return "_".join(str(doc[field]) for field in ID_FIELDS)


def has_id_fields(doc: Mapping[str, Any]) -> bool:
    """Return True if `doc` has a usable value for every field in ID_FIELDS.

    A field counts as present only if the key exists, the value is not
    `None`, and — for strings — it is not blank/whitespace-only. Other
    falsy values are kept: `timestamp` or `beam_condition` of `0` is valid
    and `str()`-coerces to `"0"`, so it must not be treated as missing.
    Documents that fail this check cannot get a stable composite `_id` and
    are skipped at ingest rather than indexed under a malformed key.
    """

    for field in ID_FIELDS:
        if field not in doc:
            return False
        value = doc[field]
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
    return True


def iter_bulk_actions(
    docs: Iterable[Mapping[str, Any]],
    *,
    index: str,
    os_inserted: str,
    op_type: str = "create",
) -> Iterator[dict[str, Any]]:
    """Yield raw bulk actions for `docs`, skipping any missing an id field.

    Each yielded action carries the composite `_id` from `make_doc_id` and
    the shared `os_inserted` stamp (KST, tz-aware — the caller computes one
    value for the whole batch) added to `_source`. Documents that fail
    `has_id_fields` are silently skipped. `op_type="create"` surfaces
    duplicate ids on re-runs (dedup); `"index"` overwrites by id (upsert).

    Feed the result straight to `OSDoc.bulk`; a composite `_id` rules out
    `OSDoc.bulk_index`, which only copies a single field into `_id`.
    """

    for doc in docs:
        if not has_id_fields(doc):
            continue
        yield {
            "_op_type": op_type,
            "_index": index,
            "_id": make_doc_id(doc),
            "_source": {**doc, "os_inserted": os_inserted},
        }


def build_mappings(alias: str) -> dict[str, Any]:
    """Return the mapping for one alias: shared base + per-alias store-only objects.

    OpenSearch's built-in dynamic date detection only matches
    `yyyy/MM/dd[ HH:mm:ss]` and `epoch_millis`, so ISO-8601 timestamp
    strings would otherwise land as `text`. The dynamic templates pin any
    `*_tm` / `*_dt` column to `date`; everything else falls through to
    default dynamic mapping.

    - `os_inserted` : KST timestamp refreshed on every write (bulk index,
                      update, upsert, bulk update). Despite the name it
                      means "last touched in OS" — used for operational
                      cleanup of the live write index by activity, not by
                      ingest cohort. It does not end in `_tm`/`_dt`, so it
                      is mapped explicitly here rather than via the dynamic
                      templates.
    - store-only objects (reso_center_cdsem only):
                      `Resolution_Range`, `Resolution_Range_Raw`,
                      `Resolution_Range_Smooth` are dicts whose sub-keys
                      hold lists of floats — fetched whole to plot, never
                      filtered/aggregated. Mapped `object` with
                      `enabled: false`, so the entire dict (lists and all)
                      is stored verbatim in `_source` and returned on fetch
                      but never parsed: its sub-keys are never mapped, so
                      they cost nothing against
                      `index.mapping.total_fields.limit` (default 1000) no
                      matter how many or which keys appear. To query one
                      sub-key later, promote it to a real top-level field
                      and reindex.
    """

    properties: dict[str, Any] = {
        "os_inserted": {"type": "date"},
    }
    for field in STORE_ONLY_OBJECT_FIELDS.get(alias, ()):
        properties[field] = {"type": "object", "enabled": False}

    return {
        "properties": properties,
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
    """Return one ISM policy shared by both CD-SEM measurement index families."""

    index_patterns = [index_pattern(alias) for alias in INDEX_ALIASES]
    return {
        "policy": {
            "description": (
                f"Rollover beam_shape_cdsem / reso_center_cdsem after "
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
            "mappings": build_mappings(alias),
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
        "mappings": build_mappings(alias),
        "aliases": {
            alias: {"is_write_index": True},
        },
    }


def create_skewnono_client() -> Any:
    """Create a client for the skewnono OpenSearch cluster."""

    if not OPENSEARCH_PASSWORD:
        raise RuntimeError(
            "Set OPENSEARCH_PASSWORD at the top of "
            "ops_index_mgmt/beam_reso_cdsem.py before running this script."
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
    """Create or update both CD-SEM measurement index templates."""

    return {
        alias: put_index_template(client, alias)
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
        mappings=build_mappings(alias),
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
    """Ensure both CD-SEM measurement aliases have a first backing index."""

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


def setup_beam_reso_cdsem(client: Any | None = None) -> dict[str, Any]:
    """Create/update shared policy and templates, then ensure both indices."""

    actual_client = client or create_skewnono_client()
    return {
        "policy": put_ism_policy(actual_client),
        "index_templates": put_index_templates(actual_client),
        "indices": ensure_rollover_indices(actual_client),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create beam_shape_cdsem and reso_center_cdsem rollover indices, "
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
        result = setup_beam_reso_cdsem()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Reference: bulk-indexing a list of dicts with a composite _id
# ---------------------------------------------------------------------------
# Not executed by this script. Copy/adapt at the office once the indices
# exist. `iter_bulk_actions` (defined above) builds the composite _id from
# eqp_ip + timestamp + beam_condition, stamps os_inserted, and skips any doc
# missing an id field. A composite id is why this uses OSDoc.bulk (raw
# actions) rather than OSDoc.bulk_index — the latter copies a single field.
#
# from datetime import datetime
# from zoneinfo import ZoneInfo
#
# from ops_store import OSDoc, create_client
#
# client = create_client(
#     host=OPENSEARCH_HOST,
#     user=OPENSEARCH_USER,
#     password=OPENSEARCH_PASSWORD,
# )
# doc_service = OSDoc(client=client)
#
# # docs: list[dict] — each should carry eqp_ip, timestamp, beam_condition.
# # Any doc missing one is skipped (see has_id_fields / iter_bulk_actions).
# # For reso_center_cdsem, Resolution_Range / _Raw / _Smooth ride along in
# # _source untouched (mapped enabled:false), so no pre-processing needed.
# docs = [...]
#
# # Report how many were skipped — iter_bulk_actions skips silently.
# skipped = sum(1 for doc in docs if not has_id_fields(doc))
# if skipped:
#     print(f"skipping {skipped} docs missing an id field")
#
# # Stamp ingest time once for the whole batch. Must be tz-aware — a naive
# # isoformat is read by OpenSearch as UTC and bakes in a 9-hour drift.
# os_inserted_kst = (
#     datetime.now(tz=ZoneInfo("Asia/Seoul"))
#     .replace(microsecond=0)
#     .isoformat()
# )
#
# # op_type="create" surfaces duplicate _ids on re-runs (dedup); switch to
# # "index" for overwrite-by-id (upsert) semantics.
# actions = iter_bulk_actions(
#     docs,
#     index="beam_shape_cdsem",   # or "reso_center_cdsem"
#     os_inserted=os_inserted_kst,
#     op_type="create",
# )
# success_count, errors = doc_service.bulk(actions, refresh=False)
# print(f"indexed: {success_count}, errors: {len(errors)}")
# for err in errors[:5]:
#     print(err)
