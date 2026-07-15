"""Create tool_maintenance_plan rollover index, template, alias, and ISM policy."""

import argparse
import json
from typing import Any

from ops_store import OSIndex, create_client

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_ALIAS = "tool_maintenance_plan"
POLICY_ID = "tool_maintenance_plan_retention_policy"
TEMPLATE_NAME = "tool_maintenance_plan_template"

SHARDS = 2
REPLICAS = 1
REFRESH_INTERVAL = "30s"

ROLLOVER_DOC_COUNT = 1000000
RETENTION_AGE = "1095d"
POLICY_PRIORITY = 100

# 8192 chars * 3 bytes (Korean UTF-8) stays under Lucene's 32766-byte term cap.
NOTE_KEYWORD_IGNORE_ABOVE = 8192

DATE_FIELDS = (
    "tool_start_tm",
    "tool_end_tm",
    "ll_dt",
    "limit_dt",
    "org_dt",
    "chg_tm",
)
NOTE_FIELDS = ("work_item_nm",)


def index_pattern() -> str:
    return f"{INDEX_ALIAS}-*"


def backing_index() -> str:
    return f"{INDEX_ALIAS}-000001"


def build_mappings() -> dict[str, Any]:
    """Return the explicit mapping for the declared columns."""

    properties: dict[str, Any] = {}
    for field in DATE_FIELDS:
        properties[field] = {"type": "date"}
    for field in NOTE_FIELDS:
        properties[field] = {
            "type": "text",
            "analyzer": "nori",
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": NOTE_KEYWORD_IGNORE_ABOVE,
                }
            },
        }
    return {"properties": properties}


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
            "ops_index_mgmt/tool_maintenance_plan.py before running this script."
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


def setup_tool_maintenance_plan(client: Any | None = None) -> dict[str, Any]:
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
            "3-year ISM policy."
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
        result = setup_tool_maintenance_plan()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Reference: ingesting a dataframe into tool_maintenance_plan
# ---------------------------------------------------------------------------
# Not executed by this script. Copy/adapt at the office once the index exists.
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
# # 1. ISO timestamp columns -> pandas datetime (NaT for unparseable).
# for col in DATE_FIELDS:
#     if col in plan_df.columns:
#         plan_df[col] = pd.to_datetime(plan_df[col], errors="coerce")
#
# # 2. Drop rows with empty/NaN doc_id, then drop in-batch duplicates.
# #    Use nullable "string" dtype so NaN stays NA (plain astype(str) turns
# #    NaN into the literal "nan" and would slip past the filter).
# before = len(plan_df)
# plan_df["doc_id"] = plan_df["doc_id"].astype("string").str.strip()
# plan_df = plan_df[plan_df["doc_id"].notna() & (plan_df["doc_id"] != "")]
# plan_df = plan_df.drop_duplicates(subset="doc_id", keep="first")
# print(f"filtered {before - len(plan_df)} rows (empty or duplicate doc_id)")
#
# # 3. Bulk index. op_type="create" surfaces duplicate doc_id on re-runs;
# #    switch to "index" only if you want upsert-by-doc_id semantics.
# success_count, errors = doc_service.bulk_index_dataframe(
#     plan_df,
#     index="tool_maintenance_plan",
#     id_field="doc_id",
#     op_type="create",
# )
# print(f"indexed: {success_count}, errors: {len(errors)}")
# for err in errors[:5]:
#     print(err)
