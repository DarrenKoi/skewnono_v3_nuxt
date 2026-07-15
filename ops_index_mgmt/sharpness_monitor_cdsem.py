"""Create the sharpness_monitor_cdsem rollover index, template, alias, and ISM policy.

Single CD-SEM sharpness-monitoring index. One document per equipment IP per
collection event (`_id = ip_timestamp`). The ingest payload is IP-keyed:
`{ip: {beam_condition, reso_detector, noise, reso_eb, summ_beam}}`; each inner
value may be a one-or-more-row pandas DataFrame or a single row dict. `Date` is
lifted out of each row into the top-level `timestamp` field and removed from
the nested measurement blocks. Of the five per-IP measurement blocks, four —
`beam_condition`, `reso_detector`, `noise`, `reso_eb` — are wide reference
objects mapped `enabled: false` (stored whole in `_source`, never
parsed/indexed); `summ_beam` is left a normal object so its summary metrics
stay queryable/aggregatable. Lifecycle copies the network_fdc_cdsem rule:
1000000-doc rollover safety net, 1-year retention.
"""

import argparse
import json
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ops_store import OSDoc, OSIndex, create_client, normalize_document

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_ALIAS = "sharpness_monitor_cdsem"
POLICY_ID = "sharpness_monitor_cdsem_retention_policy"
TEMPLATE_NAME = "sharpness_monitor_cdsem_template"

SHARDS = 2
REPLICAS = 1
REFRESH_INTERVAL = "30s"

# Same lifecycle as network_fdc_cdsem_retention_policy.
ROLLOVER_DOC_COUNT = 1000000
RETENTION_AGE = "365d"  # 1 year
POLICY_PRIORITY = 100

# Dict-valued reference fields kept in _source but never parsed/indexed —
# fetched whole, not queried. Mapped enabled:false so their sub-keys cost
# nothing against index.mapping.total_fields.limit, no matter that the keys
# are numeric-looking degree labels ("0.0", "112.5") and the values are
# stringified floats ("0.003434") — enabled:false stores the dict verbatim
# and never type-checks any of it. `summ_beam` is deliberately NOT here: it
# stays a normal object so its summary metrics remain queryable/aggregatable.
# `beam_condition` is treated as display-only; promote it out of this tuple if
# you ever need to filter/aggregate on a beam characteristic.
STORE_ONLY_OBJECT_FIELDS = ("beam_condition", "reso_detector", "noise", "reso_eb")
MEASUREMENT_BLOCK_FIELDS = (*STORE_ONLY_OBJECT_FIELDS, "summ_beam")
DATE_FIELD = "Date"

# Fields whose combined value identifies one collection event; joined to form
# _id. One document per equipment IP per timestamp.
ID_FIELDS = ("ip", "timestamp")


def make_doc_id(doc: Mapping[str, Any]) -> str:
    """Return the composite `_id` for one sharpness-monitor document.

    Joins `ip` and `timestamp` (in that order) with `_`. These two fields
    together identify one collection event, so deriving `_id` from them makes
    re-ingest idempotent: the same event always lands on the same `_id`. With
    `op_type="create"` a re-run then surfaces as a duplicate; with
    `op_type="index"` it overwrites in place. Values are `str()`-coerced so a
    non-string `timestamp` (epoch int, datetime) still joins cleanly.

    Raises `KeyError` if either field is missing — a document without them
    cannot get a stable id and should not be silently indexed under a
    malformed key. Filter with `has_id_fields` first if the batch may contain
    incomplete documents (`iter_bulk_actions` does this).
    """

    return "_".join(str(doc[field]) for field in ID_FIELDS)


def has_id_fields(doc: Mapping[str, Any]) -> bool:
    """Return True if `doc` has a usable value for every field in ID_FIELDS.

    A field counts as present only if the key exists, the value is not
    `None`, and — for strings — it is not blank/whitespace-only. Other falsy
    values are kept: a `timestamp` of `0` is valid and `str()`-coerces to
    `"0"`, so it must not be treated as missing. Documents that fail this
    check cannot get a stable composite `_id` and are skipped at ingest
    rather than indexed under a malformed key.
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
    value for the whole batch) added to `_source`. The `_source` is normalized
    before `_id` generation so pandas/numpy scalars, datetimes, NaT, and
    nested mapping keys are JSON-safe even though this uses raw bulk actions.
    Documents that fail `has_id_fields` after normalization are silently
    skipped. `op_type="create"` surfaces duplicate ids on re-runs (dedup);
    `"index"` overwrites by id (upsert).

    Feed the result straight to `OSDoc.bulk`; a composite `_id` rules out
    `OSDoc.bulk_index`, which only copies a single field into `_id`.
    """

    for doc in docs:
        source = normalize_document({**doc, "os_inserted": os_inserted})
        if not has_id_fields(source):
            continue
        yield {
            "_op_type": op_type,
            "_index": index,
            "_id": make_doc_id(source),
            "_source": source,
        }


def ordered_degree_pairs(block: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    """Return `(degrees, values)` as parallel float lists sorted by degree.

    A degree block (`reso_detector`, `noise`, `reso_eb`) is a dict with
    degree-labelled measurements (`"0.0"`, `"112.5"`, ...), each value a
    stringified float. Older caller-shaped blocks may still include `Date`.
    The block is stored `enabled: false`, so its `_source` key order is
    whatever was sent — and JSON objects are
    unordered anyway, so it must not be trusted. This rebuilds a deterministic
    ascending-by-degree view ready to plot: degrees are sorted numerically
    (`float(key)`, not lexically — else `"112.5"` would sort before `"22.5"`),
    and `values` stays index-aligned with `degrees`.

    Any key that does not parse as a float (e.g. `Date`) is skipped, so the
    whole block can be passed in as-is. Values are `float()`-coerced; a blank
    or non-numeric value raises `ValueError` rather than silently dropping a
    measurement point.
    """

    pairs: list[tuple[float, float]] = []
    for key, value in block.items():
        try:
            degree = float(key)
        except (TypeError, ValueError):
            continue
        pairs.append((degree, float(value)))
    pairs.sort(key=lambda pair: pair[0])
    return [degree for degree, _ in pairs], [value for _, value in pairs]


def _iter_block_records(block: Any) -> Iterator[Mapping[str, Any]]:
    """Yield row dicts from one measurement block.

    Office payloads carry each block as a pandas DataFrame. The older examples
    used a single mapping. Duck typing keeps pandas optional at import time and
    lets both forms feed the same fan-out path.
    """

    if isinstance(block, Mapping):
        yield block
        return

    for record in block.to_dict(orient="records"):
        yield record


def _records_by_date(block: Any) -> dict[Any, dict[str, Any]]:
    """Return one block's rows keyed by normalized `Date`, with `Date` removed."""

    records: dict[Any, dict[str, Any]] = {}
    for record in _iter_block_records(block):
        timestamp = normalize_document({DATE_FIELD: record[DATE_FIELD]})[DATE_FIELD]
        records[timestamp] = {
            key: value for key, value in record.items() if key != DATE_FIELD
        }
    return records


def fan_out(payload: Mapping[str, Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
    """Turn the IP-keyed payload into one flat document per IP and `Date`.

    `payload` is `{ip: {beam_condition, reso_detector, noise, reso_eb,
    summ_beam}}`, where every inner value is either a pandas DataFrame or a
    single row dict carrying a `Date` column/key. Each row in `summ_beam`
    defines one collection event. Its `Date` is lifted to the top-level
    `timestamp` field so it can serve as part of the composite `_id` and a real
    OpenSearch `date` field; `Date` is removed from every nested measurement
    block before storing.

    Raises `KeyError` if an IP is missing one of the five blocks, a row is
    missing `Date`, or one block lacks a `Date` present in `summ_beam` — an
    incomplete sweep should surface here, not land as a half-written document.
    """

    for ip, blocks in payload.items():
        rows_by_block = {
            block_name: _records_by_date(blocks[block_name])
            for block_name in MEASUREMENT_BLOCK_FIELDS
        }
        for timestamp in rows_by_block["summ_beam"]:
            yield {
                "ip": ip,
                "timestamp": timestamp,
                "beam_condition": rows_by_block["beam_condition"][timestamp],
                "reso_detector": rows_by_block["reso_detector"][timestamp],
                "noise": rows_by_block["noise"][timestamp],
                "reso_eb": rows_by_block["reso_eb"][timestamp],
                "summ_beam": rows_by_block["summ_beam"][timestamp],
            }


def store_payload(
    payload: Mapping[str, Mapping[str, Any]],
    client: Any | None = None,
    *,
    op_type: str = "create",
) -> tuple[int, list[Any]]:
    """Fan one IP-keyed sharpness payload out and bulk-store it.

    Builds a client from the module connection variables if none is passed,
    fans `payload` into one document per IP (`fan_out`), and bulk-indexes them
    with a single `os_inserted` stamp for the whole batch (KST, tz-aware —
    "last touched in OS"). Returns `OSDoc.bulk`'s `(indexed, errors)`.

    `op_type="create"` makes re-ingest idempotent: duplicate composite ids
    come back as 409 entries in `errors` (not exceptions — `bulk` defaults to
    `raise_on_error=False`), so `errors` is the already-present set, not a
    failure. `op_type="index"` overwrites by id instead, re-stamping
    `os_inserted`. `refresh` is left off so the index's `refresh_interval`
    governs visibility rather than forcing a refresh per batch.
    """

    actual_client = client or create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )
    doc_service = OSDoc(client=actual_client, index=INDEX_ALIAS)
    os_inserted = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()

    return doc_service.bulk(
        iter_bulk_actions(
            fan_out(payload),
            index=INDEX_ALIAS,
            os_inserted=os_inserted,
            op_type=op_type,
        ),
    )


def index_pattern() -> str:
    return f"{INDEX_ALIAS}-*"


def backing_index() -> str:
    return f"{INDEX_ALIAS}-000001"


def build_mappings() -> dict[str, Any]:
    """Return mappings: explicit os_inserted, store-only objects, auto-typed dates.

    OpenSearch's built-in dynamic date detection only matches
    `yyyy/MM/dd[ HH:mm:ss]` and `epoch_millis`, so ISO-8601 strings would
    otherwise be mapped as `text`. The dynamic templates pin any `*_tm` /
    `*_dt` column to `date`; everything else falls through to default
    dynamic mapping.

    - `os_inserted` : KST timestamp refreshed on every write (bulk index,
                      update, upsert, bulk update). Despite the name it
                      means "last touched in OS", used for operational
                      cleanup of the live write index by activity. It does
                      not end in `_tm`/`_dt`, so it is mapped explicitly
                      here rather than via the dynamic templates.
    - store-only objects:
                      `beam_condition`, `reso_detector`, `noise`, `reso_eb`
                      are dicts fetched whole to plot, never
                      filtered/aggregated. Mapped `object` with
                      `enabled: false`, so the entire dict is stored verbatim
                      in `_source` and returned on fetch but never parsed: its
                      sub-keys are never mapped, so they cost nothing against
                      `index.mapping.total_fields.limit` (default 1000) no
                      matter how many or which keys appear — and it does not
                      matter that the keys are numeric-looking degree labels
                      ("0.0", "112.5") or that the values are stringified
                      floats ("0.003434"), since nothing in a disabled object
                      is type-checked. To query one sub-key later, promote it
                      to a real top-level field and reindex.
    - `summ_beam`   : deliberately left to default dynamic mapping (a normal
                      object) so its bounded set of summary metrics stays
                      queryable/aggregatable. Cast its numerics on ingest so
                      they map as numbers, not `keyword`.
    """

    properties: dict[str, Any] = {
        "ip": {"type": "keyword"},
        "timestamp": {"type": "date"},
        "os_inserted": {"type": "date"},
    }
    for field in STORE_ONLY_OBJECT_FIELDS:
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


def build_index_settings() -> dict[str, Any]:
    """Return the index settings shared by template and first backing index."""

    return {
        "number_of_shards": SHARDS,
        "number_of_replicas": REPLICAS,
        "refresh_interval": REFRESH_INTERVAL,
        "plugins.index_state_management.rollover_alias": INDEX_ALIAS,
    }


def build_ism_policy_body() -> dict[str, Any]:
    """Return the ISM policy that rolls over by doc count and deletes by age."""

    return {
        "policy": {
            "description": (
                f"Rollover {INDEX_ALIAS} after {ROLLOVER_DOC_COUNT} docs and "
                f"delete backing indices after {RETENTION_AGE}."
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
                    "index_patterns": [index_pattern()],
                    "priority": POLICY_PRIORITY,
                }
            ],
        }
    }


def build_index_template_body() -> dict[str, Any]:
    """Return the composable index template for the rollover family."""

    return {
        "index_patterns": [index_pattern()],
        "priority": POLICY_PRIORITY,
        "template": {
            "settings": build_index_settings(),
            "mappings": build_mappings(),
        },
        "_meta": {
            "description": (
                f"Settings + mappings for the {INDEX_ALIAS} rollover family."
            )
        },
    }


def build_initial_index_body() -> dict[str, Any]:
    """Return the body used to create the first concrete backing index."""

    return {
        "settings": build_index_settings(),
        "mappings": build_mappings(),
        "aliases": {
            INDEX_ALIAS: {"is_write_index": True},
        },
    }


def create_skewnono_client() -> Any:
    """Create a client for the skewnono OpenSearch cluster."""

    if not OPENSEARCH_PASSWORD:
        raise RuntimeError(
            "Set OPENSEARCH_PASSWORD at the top of "
            "ops_index_mgmt/sharpness_monitor_cdsem.py before running this script."
        )
    return create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )


def put_ism_policy(client: Any) -> dict[str, Any]:
    """Create or update the ISM policy."""

    return client.transport.perform_request(
        "PUT",
        f"/_plugins/_ism/policies/{POLICY_ID}",
        body=build_ism_policy_body(),
    )


def put_index_template(client: Any) -> dict[str, Any]:
    """Create or update the index template used by rollover-created indices."""

    return client.transport.perform_request(
        "PUT",
        f"/_index_template/{TEMPLATE_NAME}",
        body=build_index_template_body(),
    )


def ensure_rollover_index(client: Any) -> dict[str, Any]:
    """Create the first backing index if the rollover alias does not exist."""

    first_index = backing_index()
    index_service = OSIndex(client=client, index=INDEX_ALIAS)

    if index_service.exists(INDEX_ALIAS):
        description = index_service.describe(INDEX_ALIAS)
        rollover = description["rollover"]
        if not rollover["ready"] or not rollover["uses_numbered_suffix"]:
            raise RuntimeError(
                f"{INDEX_ALIAS} already exists, but it is not a rollover "
                "alias with a numbered write index. Move or reindex it "
                "before running this setup."
            )
        return {
            "created": False,
            "alias": INDEX_ALIAS,
            "write_index": rollover["write_index"],
            "description": description,
        }

    if index_service.exists(first_index, include_aliases=False):
        raise RuntimeError(
            f"{first_index} already exists without the {INDEX_ALIAS} "
            "rollover alias. Add the alias manually or remove the "
            "conflicting index."
        )

    response = index_service.create(
        index=first_index,
        mappings=build_mappings(),
        settings=build_index_settings(),
        aliases={INDEX_ALIAS: {"is_write_index": True}},
        shards=SHARDS,
        replicas=REPLICAS,
        refresh_interval=REFRESH_INTERVAL,
    )
    return {
        "created": True,
        "alias": INDEX_ALIAS,
        "write_index": first_index,
        "response": response,
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
        "template_request": {
            "method": "PUT",
            "path": f"/_index_template/{TEMPLATE_NAME}",
            "body": build_index_template_body(),
        },
        "initial_index_request": {
            "method": "PUT",
            "path": f"/{backing_index()}",
            "body": build_initial_index_body(),
        },
    }


def setup_sharpness_monitor_cdsem(client: Any | None = None) -> dict[str, Any]:
    """Create/update policy and template, then ensure the index exists."""

    actual_client = client or create_skewnono_client()
    return {
        "policy": put_ism_policy(actual_client),
        "index_template": put_index_template(actual_client),
        "index": ensure_rollover_index(actual_client),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            f"Create the {INDEX_ALIAS} rollover index, template, alias, and "
            "1-year ISM policy."
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
        result = setup_sharpness_monitor_cdsem()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Reference: ingesting one IP-keyed sweep
# ---------------------------------------------------------------------------
# Not executed by this script. Copy/adapt at the office once the index exists.
#
# # `payload` is the nested dict: {ip: {beam_condition, reso_detector, noise,
# # reso_eb, summ_beam}}, where each inner value is a DataFrame with a `Date`
# # column (or a single row dict). store_payload fans it out one doc per
# # IP/Date, lifts `Date` to top-level `timestamp`, removes `Date` from nested
# # blocks, stamps a single os_inserted for the batch, and bulk-indexes. Pass a
# # client to reuse one; omit it to build from the module connection variables.
# indexed, errors = store_payload(payload)  # op_type="index" to upsert instead
# print(f"indexed: {indexed}, errors: {len(errors)}")
# for err in errors[:5]:   # with op_type="create", 409s here = already present
#     print(err)
#
#
# ---------------------------------------------------------------------------
# Reference: reading back one IP's latest sweep into plottable curves
# ---------------------------------------------------------------------------
# from ops_store import OSSearch
#
# search = OSSearch(client=create_skewnono_client(), default_index=INDEX_ALIAS)
#
# # Most recent document for one equipment IP. `latest` sorts by the date
# # field desc; the query narrows to a single host (ip is a keyword field).
# result = search.latest(
#     "timestamp",
#     query={"term": {"ip": "10.1.2.3"}},
# )
# hit = result["hits"]["hits"][0]
# source = hit["_source"]
#
# # The four disabled objects come back whole. Rebuild a deterministic
# # ascending-by-degree view per curve — never trust the stored key order.
# for block_name in ("reso_detector", "noise", "reso_eb"):
#     degrees, values = ordered_degree_pairs(source[block_name])
#     print(block_name, degrees, values)
#     # e.g. feed straight to a plot: ax.plot(degrees, values, label=block_name)
#
# # summ_beam stays a normal object, so its metrics are queryable/aggregatable
# # directly (range_search, aggregate, ...) — no ordered_degree_pairs needed.
