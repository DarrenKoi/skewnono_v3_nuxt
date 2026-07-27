"""Provision the office-local and production logging rollover families.

Both aliases live on the same company OpenSearch cluster, use the connection
settings loaded by :func:`ops_store.create_client`, and share one canonical
mapping. Their retention policies differ so office-local diagnostics never
mix with production activity.
"""

import argparse
import json
from dataclasses import dataclass
from typing import Any, Literal

from ops_store import OSIndex, create_client

Environment = Literal["local", "production"]


@dataclass(frozen=True)
class LoggingIndexTarget:
    environment: Environment
    alias: str
    retention_age: str

    @property
    def policy_id(self) -> str:
        return f"{self.alias}_retention_policy"

    @property
    def template_name(self) -> str:
        return f"{self.alias}_template"

    @property
    def index_pattern(self) -> str:
        return f"{self.alias}-*"

    @property
    def first_index(self) -> str:
        return f"{self.alias}-000001"


TARGETS: dict[Environment, LoggingIndexTarget] = {
    "local": LoggingIndexTarget("local", "skewnono_logging_local", "30d"),
    "production": LoggingIndexTarget("production", "skewnono_logging", "365d"),
}


def target_for(environment: str) -> LoggingIndexTarget:
    try:
        return TARGETS[environment]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(
            "environment must be 'local' or 'production'"
        ) from exc

# Cluster shape: 4 data nodes. 2 primaries x 1 replica = 4 shard copies, one
# per node. Logs are write-heavy and search-light, so 2 primaries is enough.
SHARDS = 2
REPLICAS = 1
REFRESH_INTERVAL = "30s"
ROLLOVER_SIZE = "20gb"
ROLLOVER_AGE = "7d"
POLICY_PRIORITY = 100

LOG_MAPPING_PROPERTIES: dict[str, Any] = {
    "event_id": {"type": "keyword"},
    "@timestamp": {"type": "date"},
    "level": {"type": "keyword"},
    "logger": {"type": "keyword"},
    "message": {"type": "text"},
    "service": {"type": "keyword"},
    "deployment": {"type": "keyword"},
    "host": {"type": "keyword"},
    "event": {"type": "keyword"},
    "user_id": {"type": "keyword"},
    "api_token_id": {"type": "keyword"},
    "request_id": {"type": "keyword"},
    "method": {"type": "keyword"},
    "path": {"type": "keyword"},
    "query_string": {"type": "keyword", "ignore_above": 2048},
    "status": {"type": "integer"},
    "latency_ms": {"type": "integer"},
    "remote_addr": {"type": "keyword"},
    "feature": {"type": "keyword"},
    "activity_kind": {"type": "keyword"},
    "activity_weight": {"type": "integer"},
    "fab_name_list": {"type": "keyword"},
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


def build_index_settings(target: LoggingIndexTarget) -> dict[str, Any]:
    return {
        "number_of_shards": SHARDS,
        "number_of_replicas": REPLICAS,
        "refresh_interval": REFRESH_INTERVAL,
        "plugins.index_state_management.rollover_alias": target.alias,
    }


def build_index_mappings() -> dict[str, Any]:
    return {
        "dynamic": "false",
        "properties": LOG_MAPPING_PROPERTIES,
    }


def build_ism_policy_body(target: LoggingIndexTarget) -> dict[str, Any]:
    return {
        "policy": {
            "description": (
                f"Roll over {target.alias} indices at {ROLLOVER_SIZE} or "
                f"{ROLLOVER_AGE} and delete backing indices after "
                f"{target.retention_age} from rollover."
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
                            "conditions": {
                                "min_rollover_age": target.retention_age,
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
                    "index_patterns": [target.index_pattern],
                    "priority": POLICY_PRIORITY,
                }
            ],
        }
    }


def build_index_template_body(target: LoggingIndexTarget) -> dict[str, Any]:
    return {
        "index_patterns": [target.index_pattern],
        "priority": POLICY_PRIORITY,
        "template": {
            "settings": build_index_settings(target),
            "mappings": build_index_mappings(),
        },
        "_meta": {
            "description": (
                f"Settings + mappings for the {target.alias} rollover index family."
            )
        },
    }


def build_initial_index_body(target: LoggingIndexTarget) -> dict[str, Any]:
    return {
        "settings": build_index_settings(target),
        "mappings": build_index_mappings(),
        "aliases": {target.alias: {"is_write_index": True}},
    }


def create_skewnono_client() -> Any:
    return create_client()


def put_ism_policy(
    client: Any,
    target: LoggingIndexTarget,
) -> dict[str, Any]:
    return client.transport.perform_request(
        "PUT",
        f"/_plugins/_ism/policies/{target.policy_id}",
        body=build_ism_policy_body(target),
    )


def put_index_template(
    client: Any,
    target: LoggingIndexTarget,
) -> dict[str, Any]:
    return client.transport.perform_request(
        "PUT",
        f"/_index_template/{target.template_name}",
        body=build_index_template_body(target),
    )


def ensure_rollover_index(
    client: Any,
    target: LoggingIndexTarget,
) -> dict[str, Any]:
    index_service = OSIndex(client=client, index=target.alias)

    if index_service.exists(target.alias):
        description = index_service.describe(target.alias)
        rollover = description["rollover"]
        if not rollover["ready"] or not rollover["uses_numbered_suffix"]:
            raise RuntimeError(
                f"{target.alias} already exists, but is not a rollover alias "
                "with a numbered write index. Move or reindex it before "
                "running this setup."
            )
        return {
            "created": False,
            "alias": target.alias,
            "write_index": rollover["write_index"],
            "description": description,
        }

    if index_service.exists(target.first_index, include_aliases=False):
        raise RuntimeError(
            f"{target.first_index} already exists without the {target.alias} "
            "rollover alias. Add the alias manually or remove the "
            "conflicting index."
        )

    response = index_service.create(
        index=target.first_index,
        mappings=build_index_mappings(),
        settings=build_index_settings(target),
        aliases={target.alias: {"is_write_index": True}},
        shards=SHARDS,
        replicas=REPLICAS,
        refresh_interval=REFRESH_INTERVAL,
    )
    return {
        "created": True,
        "alias": target.alias,
        "write_index": target.first_index,
        "response": response,
    }


def put_current_mapping(
    client: Any,
    target: LoggingIndexTarget,
) -> dict[str, Any]:
    """Apply additive mapping updates to existing backing indices.

    The index template only affects future rollover indices. This keeps an
    already-created logging alias compatible with newly added fields without
    recreating its storage.
    """
    return client.indices.put_mapping(
        index=target.alias,
        body=build_index_mappings(),
    )


def build_dry_run_plan(target: LoggingIndexTarget) -> dict[str, Any]:
    return {
        "cluster": {
            "configuration_source": "OPENSEARCH_* environment variables",
        },
        "policy_request": {
            "method": "PUT",
            "path": f"/_plugins/_ism/policies/{target.policy_id}",
            "body": build_ism_policy_body(target),
        },
        "template_request": {
            "method": "PUT",
            "path": f"/_index_template/{target.template_name}",
            "body": build_index_template_body(target),
        },
        "initial_index_request": {
            "method": "PUT",
            "path": f"/{target.first_index}",
            "body": build_initial_index_body(target),
        },
        "mapping_update_request": {
            "method": "PUT",
            "path": f"/{target.alias}/_mapping",
            "body": build_index_mappings(),
        },
    }


def setup_skewnono_logging(
    target: LoggingIndexTarget,
    client: Any | None = None,
) -> dict[str, Any]:
    actual_client = client or create_skewnono_client()
    return {
        "policy": put_ism_policy(actual_client, target),
        "index_template": put_index_template(actual_client, target),
        "index": ensure_rollover_index(actual_client, target),
        "mapping_update": put_current_mapping(actual_client, target),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision environment-isolated SKEWNONO logging aliases."
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("local", "production", "all"),
        help="Logging index family to provision.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the OpenSearch requests without contacting the cluster.",
    )
    return parser.parse_args(argv)


def selected_targets(
    environment: str,
) -> tuple[LoggingIndexTarget] | tuple[LoggingIndexTarget, LoggingIndexTarget]:
    if environment == "all":
        return (TARGETS["local"], TARGETS["production"])
    return (target_for(environment),)


def main() -> int:
    args = parse_args()
    targets = selected_targets(args.environment)
    client = None if args.dry_run else create_skewnono_client()
    result = {
        target.environment: (
            build_dry_run_plan(target)
            if args.dry_run
            else setup_skewnono_logging(target, client)
        )
        for target in targets
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
