"""Index and alias management services."""

import re
from typing import Any, Literal

from .base import OSBase

_ROLLOVER_INDEX_PATTERN = re.compile(r".*-\d+$")


def _join_indices(index_names: list[str]) -> str:
    return ",".join(sorted(dict.fromkeys(index_names)))


def _summarize_aliases(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    aliases: dict[str, dict[str, Any]] = {}

    for index_name, details in payload.items():
        alias_details = details.get("aliases")
        if not isinstance(alias_details, dict):
            continue

        for alias_name, alias_config in alias_details.items():
            summary = aliases.setdefault(
                alias_name,
                {
                    "backing_indices": [],
                    "write_index": None,
                },
            )
            summary["backing_indices"].append(index_name)
            if (
                isinstance(alias_config, dict)
                and alias_config.get("is_write_index") is True
            ):
                summary["write_index"] = index_name

    for summary in aliases.values():
        summary["backing_indices"].sort()

    return dict(sorted(aliases.items()))


def _build_rollover_summary(
    name: str,
    *,
    is_index: bool,
    is_alias: bool,
    alias_summary: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    alias_name: str | None = None

    if is_alias and name in alias_summary:
        alias_name = name
    elif is_index:
        for candidate, details in alias_summary.items():
            if details.get("write_index") == name:
                alias_name = candidate
                break

    if alias_name is None:
        return {
            "alias": None,
            "backing_indices": [],
            "write_index": None,
            "ready": False,
            "uses_numbered_suffix": False,
        }

    details = alias_summary[alias_name]
    write_index = details.get("write_index")
    uses_numbered_suffix = bool(
        isinstance(write_index, str)
        and _ROLLOVER_INDEX_PATTERN.fullmatch(write_index)
    )

    return {
        "alias": alias_name,
        "backing_indices": list(details["backing_indices"]),
        "write_index": write_index,
        "ready": write_index is not None,
        "uses_numbered_suffix": uses_numbered_suffix,
    }


class OSIndex(OSBase):
    """Class-based index CRUD wrapper around the OpenSearch indices API."""

    def exists(
        self,
        index: str | None = None,
        *,
        include_aliases: bool = True,
    ) -> bool:
        name = self._resolve_index(index)
        if self.client.indices.exists(index=name):
            return True
        if include_aliases:
            return self.client.indices.exists_alias(name=name)
        return False

    def alias_exists(self, alias: str | None = None) -> bool:
        name = self._resolve_index(alias)
        return self.client.indices.exists_alias(name=name)

    def describe(
        self,
        index: str | None = None,
        *,
        include_metadata: bool = False,
    ) -> dict[str, Any]:
        name = self._resolve_index(index)
        is_index = self.client.indices.exists(index=name)
        is_alias = False

        if not is_index:
            is_alias = self.client.indices.exists_alias(name=name)

        if not is_index and not is_alias:
            return {
                "name": name,
                "exists": False,
                "resource_type": "missing",
                "is_index": False,
                "is_alias": False,
                "backing_indices": [],
                "aliases": {},
                "searchable_names": [],
                "rollover": {
                    "alias": None,
                    "backing_indices": [],
                    "write_index": None,
                    "ready": False,
                    "uses_numbered_suffix": False,
                },
            }

        metadata: dict[str, Any] | None = None
        if is_index:
            metadata = self.client.indices.get(index=name)
            backing_indices = sorted(metadata)
            alias_summary = _summarize_aliases(metadata)
        else:
            target_aliases = self.client.indices.get_alias(name=name)
            backing_indices = sorted(target_aliases)
            alias_payload = self.client.indices.get_alias(
                index=_join_indices(backing_indices)
            )
            alias_summary = _summarize_aliases(alias_payload)
            if include_metadata:
                metadata = self.client.indices.get(
                    index=_join_indices(backing_indices)
                )

        searchable_names = sorted(
            {name, *backing_indices, *alias_summary.keys()}
        )
        result = {
            "name": name,
            "exists": True,
            "resource_type": "index" if is_index else "alias",
            "is_index": is_index,
            "is_alias": is_alias,
            "backing_indices": backing_indices,
            "aliases": alias_summary,
            "searchable_names": searchable_names,
            "rollover": _build_rollover_summary(
                name,
                is_index=is_index,
                is_alias=is_alias,
                alias_summary=alias_summary,
            ),
        }

        if include_metadata and metadata is not None:
            result["metadata"] = metadata

        return result

    def recreate_index(
        self,
        index: str,
        shards: int = 1,
        replica: int = 0,
        mappings: dict[str, Any] | None = None,
        aliases: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.exists(index, include_aliases=False):
            self.delete(index)
        return self.create(
            index=index,
            mappings=mappings,
            aliases=aliases,
            shards=shards,
            replicas=replica,
        )

    def create(
        self,
        *,
        index: str | None = None,
        mappings: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
        aliases: dict[str, Any] | None = None,
        shards: int = 1,
        replicas: int = 0,
        refresh_interval: str = "30s",
    ) -> dict[str, Any]:
        name = self._resolve_index(index)
        index_settings = dict(settings or {})
        index_settings.setdefault("number_of_shards", shards)
        index_settings.setdefault("number_of_replicas", replicas)
        index_settings.setdefault("refresh_interval", refresh_interval)

        body: dict[str, Any] = {"settings": index_settings}
        if mappings:
            body["mappings"] = mappings
        if aliases:
            body["aliases"] = aliases

        return self.client.indices.create(index=name, body=body)

    def create_rollover_index(
        self,
        index: str,
        shards: int = 1,
        replicas: int = 0,
        *,
        mappings: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        backing_index = f"{index}-000001"
        alias = f"{index}_alias"
        return self.create(
            index=backing_index,
            mappings=mappings,
            settings=settings,
            aliases={alias: {"is_write_index": True}},
            shards=shards,
            replicas=replicas,
        )

    def create_ism_policy(
        self,
        policy_id: str,
        index_pattern: str,
        *,
        rollover_conditions: dict[str, Any] | None = None,
        retention_age: str | None = None,
        priority: int = 100,
        description: str = "",
    ) -> dict[str, Any]:
        hot_actions: list[dict[str, Any]] = []
        if rollover_conditions:
            hot_actions.append({"rollover": rollover_conditions})

        states: list[dict[str, Any]] = [
            {
                "name": "hot",
                "actions": hot_actions,
                "transitions": (
                    [{"state_name": "delete", "conditions": {"min_index_age": retention_age}}]
                    if retention_age
                    else []
                ),
            }
        ]
        if retention_age:
            states.append(
                {
                    "name": "delete",
                    "actions": [{"delete": {}}],
                    "transitions": [],
                }
            )

        body = {
            "policy": {
                "description": description,
                "default_state": "hot",
                "states": states,
                "ism_template": [
                    {"index_patterns": [index_pattern], "priority": priority}
                ],
            }
        }
        return self.client.transport.perform_request(
            "PUT",
            f"/_plugins/_ism/policies/{policy_id}",
            body=body,
        )

    def attach_ism_policy(self, policy_id: str, index: str) -> dict[str, Any]:
        return self.client.transport.perform_request(
            "POST",
            f"/_plugins/_ism/add/{index}",
            body={"policy_id": policy_id},
        )

    def delete_ism_policy(self, policy_id: str) -> dict[str, Any]:
        return self.client.transport.perform_request(
            "DELETE",
            f"/_plugins/_ism/policies/{policy_id}",
        )

    def delete(self, index: str | None = None) -> dict[str, Any]:
        name = self._resolve_index(index)
        return self.client.indices.delete(index=name)

    def get_settings(self, index: str | None = None) -> dict[str, Any]:
        name = self._resolve_index(index)
        return self.client.indices.get_settings(index=name)

    def get_mapping(self, index: str | None = None) -> dict[str, Any]:
        name = self._resolve_index(index)
        return self.client.indices.get_mapping(index=name)

    def update_settings(
        self,
        settings: dict[str, Any],
        *,
        index: str | None = None,
    ) -> dict[str, Any]:
        name = self._resolve_index(index)
        return self.client.indices.put_settings(
            index=name,
            body={"index": settings},
        )

    def refresh(self, index: str | None = None) -> dict[str, Any]:
        name = self._resolve_index(index)
        return self.client.indices.refresh(index=name)

    def get_aliases(self, index: str | None = None) -> dict[str, Any]:
        name = index or self.default_index
        if name is None:
            return self.client.indices.get_alias()
        return self.client.indices.get_alias(index=name)

    def update_aliases(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        return self.client.indices.update_aliases(body={"actions": actions})

    def rollover(
        self,
        *,
        alias: str | None = None,
        new_index: str | None = None,
        conditions: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
        mappings: dict[str, Any] | None = None,
        aliases: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        name = self._resolve_index(alias)
        body: dict[str, Any] = {}
        if conditions:
            body["conditions"] = conditions
        if settings:
            body["settings"] = settings
        if mappings:
            body["mappings"] = mappings
        if aliases:
            body["aliases"] = aliases

        params = {"dry_run": True} if dry_run else None
        kwargs: dict[str, Any] = {"alias": name}
        if new_index is not None:
            kwargs["new_index"] = new_index
        if body:
            kwargs["body"] = body
        if params is not None:
            kwargs["params"] = params

        return self.client.indices.rollover(**kwargs)

    def reindex_from_remote(
        self,
        *,
        source_host: str,
        source_index: str | list[str],
        dest_index: str | None = None,
        source_username: str | None = None,
        source_password: str | None = None,
        query: dict[str, Any] | None = None,
        size: int = 1000,
        op_type: Literal["index", "create"] = "index",
        conflicts: Literal["abort", "proceed"] = "abort",
        slices: int = 1,
        refresh: bool = False,
        wait_for_completion: bool = False,
        requests_per_second: float | None = None,
        socket_timeout: str = "1m",
        connect_timeout: str = "10s",
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        remote: dict[str, Any] = {
            "host": source_host,
            "socket_timeout": socket_timeout,
            "connect_timeout": connect_timeout,
        }
        if source_username is not None:
            remote["username"] = source_username
        if source_password is not None:
            remote["password"] = source_password
        if headers:
            remote["headers"] = headers

        source: dict[str, Any] = {
            "remote": remote,
            "index": source_index,
            "size": size,
        }
        if query is not None:
            source["query"] = query

        body: dict[str, Any] = {
            "conflicts": conflicts,
            "source": source,
            "dest": {
                "index": self._resolve_index(dest_index),
                "op_type": op_type,
            },
        }

        # Remote reindex doesn't support automatic slicing; parallelize by
        # issuing multiple calls with manual source.slice {id, max} instead.
        params: dict[str, Any] = {
            "wait_for_completion": wait_for_completion,
            "slices": slices,
            "refresh": refresh,
        }
        if requests_per_second is not None:
            params["requests_per_second"] = requests_per_second

        return self.client.reindex(body=body, params=params)
