"""Create the skewnono_logging rollover index family and its ISM policy.

Mirrors the layout of `hitachi_sem_msr_info.py` so the operational story is
consistent: one shared ISM policy, one composable index template, one
write/search alias, and a first numbered backing index.

The Flask backend writes log documents to the `skewnono_logging` alias via
`back_dev_home._logging.opensearch_handler.OpenSearchBulkHandler` when
running in production (`is_cloud()` is true).
"""

import argparse
import json
from typing import Any

from ops_store import OSIndex, create_client

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_ALIAS = "skewnono_logging"
POLICY_ID = "skewnono_logging_retention_policy"
TEMPLATE_NAME = f"{INDEX_ALIAS}_template"

# Cluster shape: 4 data nodes. 2 primaries x 1 replica = 4 shard copies, one
# per node. Logs are write-heavy and search-light, so 2 primaries is enough.
SHARDS = 2
REPLICAS = 1
REFRESH_INTERVAL = "30s"
ROLLOVER_SIZE = "20gb"
ROLLOVER_AGE = "7d"
RETENTION_AGE = "30d"
POLICY_PRIORITY = 100

INDEX_PATTERN = f"{INDEX_ALIAS}-*"
FIRST_INDEX = f"{INDEX_ALIAS}-000001"

LOG_MAPPING_PROPERTIES: dict[str, Any] = {
    "@timestamp": {"type": "date"},
    "level": {"type": "keyword"},
    "logger": {"type": "keyword"},
    "message": {"type": "text"},
    "host": {"type": "keyword"},
    "event": {"type": "keyword"},
    "user_id": {"type": "keyword"},
    "request_id": {"type": "keyword"},
    "method": {"type": "keyword"},
    "path": {"type": "keyword"},
    "request_path": {"type": "keyword"},
    "query_string": {"type": "keyword", "ignore_above": 2048},
    "status": {"type": "integer"},
    "latency_ms": {"type": "integer"},
    "remote_addr": {"type": "keyword"},
    "feature": {"type": "keyword"},
    "activity_weight": {"type": "integer"},
    "error_code": {"type": "keyword"},
    "error_name": {"type": "keyword"},
    "exception": {
        "properties": {
            "type": {"type": "keyword"},
            "message": {"type": "text"},
            "stack": {"type": "text"},
        }
    },
}


def build_index_settings() -> dict[str, Any]:
    return {
        "number_of_shards": SHARDS,
        "number_of_replicas": REPLICAS,
        "refresh_interval": REFRESH_INTERVAL,
        "plugins.index_state_management.rollover_alias": INDEX_ALIAS,
    }


def build_index_mappings() -> dict[str, Any]:
    return {
        "dynamic": "true",
        "properties": LOG_MAPPING_PROPERTIES,
    }


def build_ism_policy_body() -> dict[str, Any]:
    return {
        "policy": {
            "description": (
                f"Roll over {INDEX_ALIAS} indices at {ROLLOVER_SIZE} or "
                f"{ROLLOVER_AGE} and delete backing indices after "
                f"{RETENTION_AGE}."
            ),
            "schema_version": 1,
            "default_state": "hot",
            "states": [
                {
                    "name": "hot",
                    "actions": [
                        {
                            "rollover": {
                                "min_size": ROLLOVER_SIZE,
                                "min_index_age": ROLLOVER_AGE,
                            }
                        }
                    ],
                    "transitions": [
                        {
                            "state_name": "delete",
                            "conditions": {"min_index_age": RETENTION_AGE},
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
                    "index_patterns": [INDEX_PATTERN],
                    "priority": POLICY_PRIORITY,
                }
            ],
        }
    }


def build_index_template_body() -> dict[str, Any]:
    return {
        "index_patterns": [INDEX_PATTERN],
        "priority": POLICY_PRIORITY,
        "template": {
            "settings": build_index_settings(),
            "mappings": build_index_mappings(),
        },
        "_meta": {
            "description": (
                f"Settings + mappings for the {INDEX_ALIAS} rollover index family."
            )
        },
    }


def build_initial_index_body() -> dict[str, Any]:
    return {
        "settings": build_index_settings(),
        "mappings": build_index_mappings(),
        "aliases": {INDEX_ALIAS: {"is_write_index": True}},
    }


def create_skewnono_client() -> Any:
    if not OPENSEARCH_PASSWORD:
        raise RuntimeError(
            "Set OPENSEARCH_PASSWORD at the top of "
            "ops_index_mgmt/skewnono_logging.py before running this script."
        )
    return create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )


def put_ism_policy(client: Any) -> dict[str, Any]:
    return client.transport.perform_request(
        "PUT",
        f"/_plugins/_ism/policies/{POLICY_ID}",
        body=build_ism_policy_body(),
    )


def put_index_template(client: Any) -> dict[str, Any]:
    return client.transport.perform_request(
        "PUT",
        f"/_index_template/{TEMPLATE_NAME}",
        body=build_index_template_body(),
    )


def ensure_rollover_index(client: Any) -> dict[str, Any]:
    index_service = OSIndex(client=client, index=INDEX_ALIAS)

    if index_service.exists(INDEX_ALIAS):
        description = index_service.describe(INDEX_ALIAS)
        rollover = description["rollover"]
        if not rollover["ready"] or not rollover["uses_numbered_suffix"]:
            raise RuntimeError(
                f"{INDEX_ALIAS} already exists, but is not a rollover alias "
                "with a numbered write index. Move or reindex it before "
                "running this setup."
            )
        return {
            "created": False,
            "alias": INDEX_ALIAS,
            "write_index": rollover["write_index"],
            "description": description,
        }

    if index_service.exists(FIRST_INDEX, include_aliases=False):
        raise RuntimeError(
            f"{FIRST_INDEX} already exists without the {INDEX_ALIAS} "
            "rollover alias. Add the alias manually or remove the "
            "conflicting index."
        )

    response = index_service.create(
        index=FIRST_INDEX,
        mappings=build_index_mappings(),
        settings=build_index_settings(),
        aliases={INDEX_ALIAS: {"is_write_index": True}},
        shards=SHARDS,
        replicas=REPLICAS,
        refresh_interval=REFRESH_INTERVAL,
    )
    return {
        "created": True,
        "alias": INDEX_ALIAS,
        "write_index": FIRST_INDEX,
        "response": response,
    }


def put_current_mapping(client: Any) -> dict[str, Any]:
    """Apply additive mapping updates to existing backing indices.

    The index template only affects future rollover indices. This keeps an
    already-created `skewnono_logging` alias compatible with newly added fields
    without recreating production log storage.
    """
    return client.indices.put_mapping(
        index=INDEX_ALIAS,
        body=build_index_mappings(),
    )


def build_dry_run_plan() -> dict[str, Any]:
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
            "path": f"/{FIRST_INDEX}",
            "body": build_initial_index_body(),
        },
        "mapping_update_request": {
            "method": "PUT",
            "path": f"/{INDEX_ALIAS}/_mapping",
            "body": build_index_mappings(),
        },
    }


def setup_skewnono_logging(client: Any | None = None) -> dict[str, Any]:
    actual_client = client or create_skewnono_client()
    policy_result = put_ism_policy(actual_client)
    template_result = put_index_template(actual_client)
    index_result = ensure_rollover_index(actual_client)
    mapping_result = put_current_mapping(actual_client)
    return {
        "policy": policy_result,
        "index_template": template_result,
        "index": index_result,
        "mapping_update": mapping_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            f"Create the {INDEX_ALIAS} rollover index, index template, "
            f"alias, and a {RETENTION_AGE} ISM retention policy."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the OpenSearch requests without contacting the cluster.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        result = build_dry_run_plan()
    else:
        result = setup_skewnono_logging()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
