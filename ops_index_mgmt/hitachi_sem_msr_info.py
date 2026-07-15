"""Create Hitachi SEM MSR rollover indices and their shared ISM policy."""

import argparse
import json
from typing import Any

from ops_store import OSIndex, create_client

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_ALIASES = ("meas_hist_cdsem", "meas_hist_hvsem")
POLICY_ID = "sem_meas_hist_retention_policy"

SHARDS = 3
REPLICAS = 1
REFRESH_INTERVAL = "30s"
ROLLOVER_AGE = "60d"
RETENTION_AGE = "365d"
POLICY_PRIORITY = 100


def index_pattern(alias: str) -> str:
    return f"{alias}-*"


def backing_index(alias: str) -> str:
    return f"{alias}-000001"


def index_template_name(alias: str) -> str:
    return f"{alias}_template"


def build_index_settings(alias: str) -> dict[str, Any]:
    """Return index settings shared by the first and rolled-over indices."""

    return {
        "number_of_shards": SHARDS,
        "number_of_replicas": REPLICAS,
        "refresh_interval": REFRESH_INTERVAL,
        "plugins.index_state_management.rollover_alias": alias,
    }


def build_ism_policy_body() -> dict[str, Any]:
    """Return one ISM policy shared by both SEM MSR index families."""

    index_patterns = [index_pattern(alias) for alias in INDEX_ALIASES]
    return {
        "policy": {
            "description": (
                f"Rollover SEM measurement history indices after {ROLLOVER_AGE} "
                f"and delete backing indices after {RETENTION_AGE}."
            ),
            "schema_version": 1,
            "default_state": "hot",
            "states": [
                {
                    "name": "hot",
                    "actions": [
                        {
                            "rollover": {
                                "min_index_age": ROLLOVER_AGE,
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
                    "actions": [
                        {
                            "delete": {},
                        }
                    ],
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
        },
        "_meta": {
            "description": f"Settings for the {alias} rollover index family."
        },
    }


def build_initial_index_body(alias: str) -> dict[str, Any]:
    """Return the body used to create the first concrete backing index."""

    return {
        "settings": build_index_settings(alias),
        "aliases": {
            alias: {
                "is_write_index": True,
            }
        },
    }


def create_skewnono_client() -> Any:
    """Create a client for the skewnono OpenSearch cluster."""

    if not OPENSEARCH_PASSWORD:
        raise RuntimeError(
            "Set OPENSEARCH_PASSWORD at the top of "
            "ops_index_mgmt/hitachi_sem_msr_info.py before running this script."
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
    """Create or update all SEM MSR index templates."""

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
                f"{alias} already exists, but it is not a rollover alias with "
                "a numbered write index. Move or reindex it before running "
                "this setup."
            )
        return {
            "created": False,
            "alias": alias,
            "write_index": rollover["write_index"],
            "description": description,
        }

    if index_service.exists(first_index, include_aliases=False):
        raise RuntimeError(
            f"{first_index} already exists without the {alias} rollover alias. "
            "Add the alias manually or remove the conflicting index."
        )

    response = index_service.create(
        index=first_index,
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
    """Ensure both SEM MSR rollover aliases have a first backing index."""

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


def setup_sem_msr_info(client: Any | None = None) -> dict[str, Any]:
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
            "Create meas_hist_cdsem and meas_hist_hvsem rollover indices, "
            "index templates, aliases, and a shared one-year ISM policy."
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
        result = setup_sem_msr_info()

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
