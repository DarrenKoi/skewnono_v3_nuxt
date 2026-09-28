"""Create network_fdc_cdsem rollover index, template, alias, and ISM policy."""

import argparse
import json
import math
from typing import Any, Iterable, Iterator, Mapping

from ops_store import OSIndex, create_client

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_ALIAS = "network_fdc_cdsem"
POLICY_ID = "network_fdc_cdsem_retention_policy"
TEMPLATE_NAME = "network_fdc_cdsem_template"

SHARDS = 2
REPLICAS = 1
REFRESH_INTERVAL = "30s"

ROLLOVER_DOC_COUNT = 1000000
RETENTION_AGE = "365d"  # 1 year
POLICY_PRIORITY = 100

# Fields whose combined value identifies one FDC record; joined to form _id.
ID_FIELDS = ("fab_name", "eqp_id", "fdc_key", "timestamp")

# Typed side-fields derived from `values` at write time (see side_fields).
# `values` is a positional string list, which OpenSearch cannot aggregate by
# position; these typed copies make fleet views native aggregations. The
# names are the office writer's (office 확인 2026-09-28) and the index stays
# dynamically mapped: numbers land as long/float, strings as text + .keyword.
# The real writer is the FDC task in the office scheduler repo; this copy is
# the home mirror the mock runs, so its names and rules must match that one.
_INT_SIDE_FIELDS = {"temp_pos", "pin_no", "pin_counter"}


def index_pattern() -> str:
    return f"{INDEX_ALIAS}-*"


def backing_index() -> str:
    return f"{INDEX_ALIAS}-000001"


def make_doc_id(doc: Mapping[str, Any]) -> str:
    """Return the composite `_id` for one FDC record.

    Joins `fab_name`, `eqp_id`, `fdc_key`, and `timestamp` (in that order)
    with `_`. These four fields together identify one record, so deriving
    `_id` from them makes re-ingest idempotent: the same record always
    lands on the same `_id`. With `op_type="create"` a re-run then surfaces
    as a duplicate (HTTP 409); with `op_type="index"` it overwrites in
    place. Values are `str()`-coerced so a non-string `timestamp` (epoch
    int, datetime) still joins cleanly.

    Raises `KeyError` if any of the four fields is missing — a record
    without them cannot get a stable id and should not be silently indexed
    under a malformed key. Filter with `has_id_fields` first if the batch
    may contain incomplete records (`iter_bulk_actions` does this).
    """

    return "_".join(str(doc[field]) for field in ID_FIELDS)


def has_id_fields(doc: Mapping[str, Any]) -> bool:
    """Return True if `doc` has a usable value for every field in ID_FIELDS.

    A field counts as present only if the key exists, the value is not
    `None`, and — for strings — it is not blank/whitespace-only. Other
    falsy values are kept: a `timestamp` of `0` is valid and `str()`-coerces
    to `"0"`, so it must not be treated as missing. Records that fail this
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


def _number(value: Any) -> float | None:
    """Parse one `values` cell; a comma decimal (`'25,0'`) reads as 25.0."""

    text = str(value).strip()
    if "," in text and "." not in text:
        text = text.replace(",", ".", 1)
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def side_fields(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Return the typed side-fields for one record, derived from `values`.

    Layouts (values[0] repeats fdc_key, values[1] is always '0'):

    - TemperatureEChuck        [key, '0', pos, temp]        -> temp_pos, temp_c
    - LaserPower               [key, '0', x1, y1, x2, y2]   -> laser_x1, laser_y1
    - SPMVoltages              [key, '0', ch, n, n, n, fit model, 107 nums]
                                                            -> spm_channel, spm_judgment
                               CG5000 omits the fit model   -> spm_channel only
    - ContactpinConductionInfo [key, '0', ch, pin, judgment,
                                n1, n2, n3, n4, counter]    -> pin_channel, pin_no,
                                                               pin_judgment, pin_spread,
                                                               pin_counter

    SPM gets strings only: its profile's unit scale differs up to 100x
    between tools, so no SPM number is fleet-comparable. A cell that does
    not parse leaves its field out, so a bad cell never becomes a wrong
    number; `values` itself stays the record of truth.
    """

    values = doc.get("values")
    if not isinstance(values, list):
        return {}
    nums = [_number(v) for v in values]
    key = doc.get("fdc_key")
    fields: dict[str, float | None] = {}
    out: dict[str, Any] = {}
    if key == "TemperatureEChuck" and len(nums) == 4:
        fields = {"temp_pos": nums[2], "temp_c": nums[3]}
    elif key == "LaserPower" and len(nums) == 6:
        fields = {"laser_x1": nums[2], "laser_y1": nums[3]}
    elif key == "SPMVoltages" and len(values) > 7:
        out = {"spm_channel": str(values[2])}
        # CG5000 writes no fit-model token, so values[6] is already the first
        # profile number and spm_judgment stays absent (office 확인 2026-09-29).
        if nums[6] is None:
            out["spm_judgment"] = str(values[6])
    elif key == "ContactpinConductionInfo" and len(nums) == 10:
        first4 = nums[5:9]
        spread = None if None in first4 else max(first4) - min(first4)
        out = {"pin_channel": str(values[2]), "pin_judgment": str(values[4])}
        fields = {"pin_no": nums[3], "pin_spread": spread, "pin_counter": nums[9]}
    for name, number in fields.items():
        if number is None:
            continue
        if name in _INT_SIDE_FIELDS:
            if not number.is_integer():
                continue
            out[name] = int(number)
        else:
            out[name] = number
    return out


def iter_bulk_actions(
    docs: Iterable[Mapping[str, Any]],
    *,
    index: str,
    op_type: str = "create",
) -> Iterator[dict[str, Any]]:
    """Yield raw bulk actions for `docs`, skipping any missing an id field.

    Each yielded action carries the composite `_id` from `make_doc_id`, and
    the record is stored in `_source` with its `values` untouched plus the
    typed `side_fields` derived from them — no `os_inserted` is added.
    Records that fail `has_id_fields` are silently skipped.
    `op_type="create"` surfaces duplicate ids on re-runs (dedup); `"index"`
    overwrites by id (upsert).

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
            "_source": {**doc, **side_fields(doc)},
        }


def build_mappings() -> dict[str, Any]:
    """Return mappings: explicit os_inserted + auto-typed *_tm / *_dt dates.

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
    """

    return {
        "properties": {
            "os_inserted": {"type": "date"},
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
            "ops_index_mgmt/network_fdc_cdsem.py before running this script."
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


def setup_network_fdc_cdsem(client: Any | None = None) -> dict[str, Any]:
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
        result = setup_network_fdc_cdsem()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Reference: ingesting a list of record dicts into network_fdc_cdsem
# ---------------------------------------------------------------------------
# Not executed by this script. Copy/adapt at the office once the index exists.
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
# # `records` is your list[dict] — each dict carries fab_name, eqp_id,
# # fdc_key, timestamp (the composite _id) plus the rest of the payload.
# # iter_bulk_actions builds _id = fab_name_eqp_id_fdc_key_timestamp, skips
# # any record missing one of those four, and stores _source with the typed
# # side_fields added (values untouched; no os_inserted is added). op_type="create" surfaces duplicate ids on
# # re-runs (dedup); switch to "index" for upsert-by-id semantics.
# success_count, errors = doc_service.bulk(
#     iter_bulk_actions(records, index=INDEX_ALIAS, op_type="create"),
# )
# print(f"indexed: {success_count}, errors: {len(errors)}")
# for err in errors[:5]:
#     print(err)
