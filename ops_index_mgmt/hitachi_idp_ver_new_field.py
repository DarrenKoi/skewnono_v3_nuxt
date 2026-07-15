"""Add the `wafer_para_loc_info` field to the existing Hitachi IDP version indices.

The base setup script `hitachi_idp_ver.py` already ran long ago, so the
ISM policy, index templates, and backing indices all exist. This script
only propagates a newly declared mapping field to them — it never touches
the policy (re-PUTting it would 409 without if_seq_no/if_primary_term).

Two writes, both sourced from `hitachi_idp_ver.build_mappings()`:

  1. PUT index templates  -> indices created by *future* rollovers carry
                             the new field.
  2. PUT mapping on the    -> the already-created write indices get the
     live aliases             field *now*, while it is still unmapped.

`PUT mapping` is additive: it creates new fields and is a no-op for
fields whose definition is unchanged, but it CANNOT redefine a field that
is already mapped. So run this BEFORE the first document carrying
`wafer_para_loc_info` is ingested — once a value lands, dynamic mapping
fixes the field as a parsed object and the `enabled: false` definition is
rejected (only a reindex could change it then).
"""

import argparse
import json
from typing import Any

from ops_index_mgmt.hitachi_idp_ver import (
    INDEX_ALIASES,
    build_index_template_body,
    build_mappings,
    create_skewnono_client,
    index_template_name,
    put_index_templates,
    put_live_index_mappings,
)

NEW_FIELD = "wafer_para_loc_info"


def build_dry_run_plan() -> dict[str, Any]:
    """Return the requests this script will send without connecting."""

    mappings = build_mappings()
    return {
        "new_field": {NEW_FIELD: mappings["properties"].get(NEW_FIELD)},
        "template_requests": {
            alias: {
                "method": "PUT",
                "path": f"/_index_template/{index_template_name(alias)}",
                "body": build_index_template_body(alias),
            }
            for alias in INDEX_ALIASES
        },
        "live_mapping_requests": {
            alias: {
                "method": "PUT",
                "path": f"/{alias}/_mapping",
                "body": mappings,
            }
            for alias in INDEX_ALIASES
        },
    }


def add_new_field(client: Any | None = None) -> dict[str, Any]:
    """Update the templates, then add the new field to the live indices."""

    actual_client = client or create_skewnono_client()
    return {
        "index_templates": put_index_templates(actual_client),
        "live_index_mappings": put_live_index_mappings(actual_client),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            f"Add the {NEW_FIELD} field to the cdsem_idp_ver and "
            "hvsem_idp_ver templates and existing write indices."
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
        result = add_new_field()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
