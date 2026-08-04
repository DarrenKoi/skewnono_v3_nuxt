"""Provision the chat conversation logging rollover families.

Chat turns carry user and assistant message content, which the activity
logging index (``skewnono_logging``) deliberately never stores. These
families keep that content in their own aliases so retention and access can
be governed separately from operational logs. Both aliases live on the same
company OpenSearch cluster and use the connection settings loaded by
:func:`ops_store.create_client`.

Run it as a plain script — no arguments provisions both environments::

    .venv/bin/python ops_index_mgmt/skewnono_chat_logging.py            # local + production
    .venv/bin/python ops_index_mgmt/skewnono_chat_logging.py --dry-run  # review first

Every step is idempotent, so re-running is a safe no-op.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# ISM computes the next backing index by incrementing a zero-padded suffix, so
# a write index that does not end in digits can never be rolled over.
NUMBERED_SUFFIX = re.compile(r".*-\d+$")

REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    from ops_store import OSIndex, create_client
except ModuleNotFoundError:
    # `python ops_index_mgmt/skewnono_chat_logging.py` puts THIS file's
    # directory on sys.path, not the repo root, so the sibling `ops_store`
    # package is invisible. (`python -m ops_index_mgmt.skewnono_chat_logging`
    # gets the repo root for free from `-m`.) Add it back so both work.
    sys.path.insert(0, str(REPO_ROOT))
    from ops_store import OSIndex, create_client

Environment = Literal["local", "production"]


@dataclass(frozen=True)
class ChatLoggingIndexTarget:
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


TARGETS: dict[Environment, ChatLoggingIndexTarget] = {
    "local": ChatLoggingIndexTarget("local", "skewnono_chat_logging_local", "30d"),
    "production": ChatLoggingIndexTarget("production", "skewnono_chat_logging", "365d"),
}


def target_for(environment: str) -> ChatLoggingIndexTarget:
    try:
        return TARGETS[environment]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(
            "environment must be 'local' or 'production'"
        ) from exc


# One document per completed chat turn is orders of magnitude lighter than the
# per-request activity stream, so a single primary is enough; the replica keeps
# the family readable through one node loss on the 4-node cluster.
SHARDS = 1
REPLICAS = 1
REFRESH_INTERVAL = "30s"
ROLLOVER_SIZE = "10gb"
ROLLOVER_AGE = "30d"
POLICY_PRIORITY = 100

CHAT_MAPPING_PROPERTIES: dict[str, Any] = {
    "event_id": {"type": "keyword"},
    "@timestamp": {"type": "date"},
    "service": {"type": "keyword"},
    "deployment": {"type": "keyword"},
    "host": {"type": "keyword"},
    "user_id": {"type": "keyword"},
    "thread_id": {"type": "keyword"},
    "request_id": {"type": "keyword"},
    "message_id": {"type": "keyword"},
    "model": {"type": "keyword"},
    "runtime": {"type": "keyword"},
    "scope_status": {"type": "keyword"},
    "scope_reason_code": {"type": "keyword"},
    "user_content": {"type": "text"},
    "assistant_content": {"type": "text"},
    "prompt_tokens": {"type": "integer"},
    "completion_tokens": {"type": "integer"},
    "latency_ms": {"type": "integer"},
    "source_count": {"type": "integer"},
    "source_ids": {"type": "keyword"},
    "tool_call_count": {"type": "integer"},
}


def build_index_settings(target: ChatLoggingIndexTarget) -> dict[str, Any]:
    return {
        "number_of_shards": SHARDS,
        "number_of_replicas": REPLICAS,
        "refresh_interval": REFRESH_INTERVAL,
        "plugins.index_state_management.rollover_alias": target.alias,
    }


def build_index_mappings() -> dict[str, Any]:
    return {
        "dynamic": "false",
        "properties": CHAT_MAPPING_PROPERTIES,
    }


def build_ism_policy_body(target: ChatLoggingIndexTarget) -> dict[str, Any]:
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


def build_index_template_body(target: ChatLoggingIndexTarget) -> dict[str, Any]:
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


def build_initial_index_body(target: ChatLoggingIndexTarget) -> dict[str, Any]:
    return {
        "settings": build_index_settings(target),
        "mappings": build_index_mappings(),
        "aliases": {target.alias: {"is_write_index": True}},
    }


def load_env_file() -> None:
    """Load ``back_dev_home/.env`` so a bare script run finds OPENSEARCH_*.

    The credentials this script needs live in the same .env the Flask app
    factory loads, but nothing loads it for a standalone run. Best-effort:
    an already-exported OPENSEARCH_HOST wins (``override=False``), and a
    missing python-dotenv or .env just leaves the environment as it was.
    """
    if os.environ.get("OPENSEARCH_HOST"):
        return
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(REPO_ROOT / "back_dev_home" / ".env")


def create_skewnono_client() -> Any:
    load_env_file()
    return create_client()


def put_ism_policy(
    client: Any,
    target: ChatLoggingIndexTarget,
) -> dict[str, Any]:
    return client.transport.perform_request(
        "PUT",
        f"/_plugins/_ism/policies/{target.policy_id}",
        body=build_ism_policy_body(target),
    )


def put_index_template(
    client: Any,
    target: ChatLoggingIndexTarget,
) -> dict[str, Any]:
    return client.transport.perform_request(
        "PUT",
        f"/_index_template/{target.template_name}",
        body=build_index_template_body(target),
    )


def rollover_write_index(index_service: Any, alias: str) -> str | None:
    """Return the alias's numbered write index, or None if it is not usable.

    Reads the per-alias entry rather than ``describe()["rollover"]`` for the
    same reason as skewnono_logging.py: the per-alias entry is correct under
    both the pre- and post-56cff99 vendored ops_store, and this script is
    meant to run standalone next to either.
    """
    if not index_service.alias_exists(alias):
        return None
    summary = index_service.describe(alias).get("aliases", {}).get(alias, {})
    write_index = summary.get("write_index")
    if isinstance(write_index, str) and NUMBERED_SUFFIX.fullmatch(write_index):
        return write_index
    return None


def ensure_rollover_index(
    client: Any,
    target: ChatLoggingIndexTarget,
) -> dict[str, Any]:
    index_service = OSIndex(client=client, index=target.alias)

    if index_service.alias_exists(target.alias):
        write_index = rollover_write_index(index_service, target.alias)
        if write_index is None:
            raise RuntimeError(
                f"{target.alias} already exists, but is not a rollover alias "
                "with a numbered write index. Move or reindex it before "
                "running this setup."
            )
        return {
            "created": False,
            "alias": target.alias,
            "write_index": write_index,
            "description": index_service.describe(target.alias),
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
    target: ChatLoggingIndexTarget,
) -> dict[str, Any]:
    """Apply additive mapping updates to existing backing indices.

    The index template only affects future rollover indices. This keeps an
    already-created alias compatible with newly added fields without
    recreating its storage.
    """
    return client.indices.put_mapping(
        index=target.alias,
        body=build_index_mappings(),
    )


def build_dry_run_plan(target: ChatLoggingIndexTarget) -> dict[str, Any]:
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


def setup_skewnono_chat_logging(
    target: ChatLoggingIndexTarget,
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
        description="Provision environment-isolated chat conversation aliases."
    )
    parser.add_argument(
        "--environment",
        default="all",
        choices=("local", "production", "all"),
        help=(
            "Index family to provision. Defaults to 'all' so a bare run "
            "provisions both local and production."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the OpenSearch requests without contacting the cluster.",
    )
    return parser.parse_args(argv)


def selected_targets(
    environment: str,
) -> tuple[ChatLoggingIndexTarget, ...]:
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
            else setup_skewnono_chat_logging(target, client)
        )
        for target in targets
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
