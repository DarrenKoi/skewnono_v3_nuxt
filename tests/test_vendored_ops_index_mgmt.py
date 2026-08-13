"""Characterization tests for the vendored ``ops_index_mgmt`` provisioning scripts.

``ops_index_mgmt`` is the fourth vendored package with no package-local tests. Every module in it is a one-shot setup script
for an OpenSearch index family, and each one is built the same way: pure
``build_*`` functions that assemble request bodies, plus an ``ensure_*`` step
that guards against clobbering an index that already exists.

Two families are covered here because the rest of the backend actually depends
on them:

* ``skewnono_logging_local`` and ``skewnono_logging`` — the isolated aliases
  the Flask office-local and production log handlers write to. If either
  retention policy, mapping, or alias name drifts, logging can silently land in
  an auto-created index with no template and no expiry.
* ``hitachi_sem_msr_info`` — the ``meas_hist_cdsem`` / ``meas_hist_hvsem``
  families the office adapters read.

Nothing here contacts a cluster: the ``build_*`` functions are pure, and the
``ensure_*`` guard rails are driven with a fake client.

Vendoring status is per-file: most of ``ops_index_mgmt/`` is a **vendored
copy** of the upstream ``flask_modules`` package and is not edited here, but
``skewnono_logging.py`` is **project-owned** — it does not exist upstream and
carries this repo's local/production logging families, so it is edited here
like any other backend module.
"""

import os

import pytest

from ops_index_mgmt import hitachi_sem_msr_info as sem_msr
from ops_index_mgmt import skewnono_logging as logging_setup


# ── name derivation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("environment", "alias", "retention"),
    [
        ("local", "skewnono_logging_local", "30d"),
        ("production", "skewnono_logging", "365d"),
    ],
)
def test_logging_targets_are_isolated(environment, alias, retention):
    target = logging_setup.target_for(environment)
    assert target.alias == alias
    assert target.retention_age == retention
    assert target.index_pattern == f"{alias}-*"
    assert target.first_index == f"{alias}-000001"
    assert target.policy_id == f"{alias}_retention_policy"
    assert target.template_name == f"{alias}_template"


def test_the_first_backing_index_matches_its_own_index_pattern():
    """ISM attaches the policy by pattern. A first index outside the pattern
    would be created, written to, and never rolled over or deleted."""
    target = logging_setup.target_for("production")
    prefix = target.index_pattern.rstrip("*")
    assert target.first_index.startswith(prefix)


def test_the_sem_msr_helpers_derive_the_same_three_names_per_alias():
    assert sem_msr.index_pattern("meas_hist_cdsem") == "meas_hist_cdsem-*"
    assert sem_msr.backing_index("meas_hist_cdsem") == "meas_hist_cdsem-000001"
    assert sem_msr.index_template_name("meas_hist_cdsem") == "meas_hist_cdsem_template"


def test_the_backing_index_uses_the_six_digit_suffix_rollover_requires():
    """``OSIndex.describe`` refuses to call an alias rollover-ready unless the
    write index ends in digits, and ISM computes the next name by incrementing
    a zero-padded suffix. Six digits is the OpenSearch convention."""
    assert sem_msr.backing_index("x").endswith("-000001")
    assert logging_setup.target_for("production").first_index.endswith("-000001")


# ── index settings ───────────────────────────────────────────────────────────


def test_the_rollover_alias_is_written_into_the_index_settings():
    """``plugins.index_state_management.rollover_alias`` is what tells ISM
    which alias to roll. Without it the rollover action fails on every
    execution and the index grows unbounded."""
    target = logging_setup.target_for("production")
    settings = logging_setup.build_index_settings(target)
    assert settings["plugins.index_state_management.rollover_alias"] == target.alias
    per_alias = sem_msr.build_index_settings("meas_hist_hvsem")
    assert per_alias["plugins.index_state_management.rollover_alias"] == "meas_hist_hvsem"


def test_the_logging_shard_count_matches_the_documented_cluster_shape():
    """2 primaries x 1 replica = 4 shard copies on a 4-data-node cluster, one
    per node. Pinned because the number is a deployment fact, not a default."""
    settings = logging_setup.build_index_settings(
        logging_setup.target_for("production")
    )
    assert (settings["number_of_shards"], settings["number_of_replicas"]) == (2, 1)


def test_the_same_settings_object_backs_the_template_and_the_first_index():
    """If they diverge, the first index and every rolled-over index end up with
    different shard counts — invisible until a query fans out unevenly."""
    target = logging_setup.target_for("production")
    settings = logging_setup.build_index_settings(target)
    assert logging_setup.build_index_template_body(target)["template"]["settings"] == settings
    assert logging_setup.build_initial_index_body(target)["settings"] == settings


# ── mappings ─────────────────────────────────────────────────────────────────


def test_logging_mapping_is_explicit_and_canonical():
    mappings = logging_setup.build_index_mappings()
    assert mappings["dynamic"] == "false"
    properties = mappings["properties"]
    assert properties["event_id"] == {"type": "keyword"}
    assert properties["deployment"] == {"type": "keyword"}
    assert properties["api_token_id"] == {"type": "keyword"}
    assert properties["activity_kind"] == {"type": "keyword"}
    assert properties["fab_name_list"] == {"type": "keyword"}
    assert "request_path" not in properties


def test_the_log_timestamp_and_level_are_typed_for_filtering_not_analysis():
    """``@timestamp`` must be a ``date`` (the ISM age conditions and every
    range query depend on it) and ``level`` a ``keyword`` (an analyzed ``text``
    field cannot be aggregated on)."""
    properties = logging_setup.LOG_MAPPING_PROPERTIES
    assert properties["@timestamp"] == {"type": "date"}
    assert properties["level"] == {"type": "keyword"}


def test_the_query_string_field_caps_its_indexed_length():
    """An unbounded keyword field rejects the whole document above ~32KB, so a
    pathological query string would drop the log line that recorded it."""
    assert logging_setup.LOG_MAPPING_PROPERTIES["query_string"] == {
        "type": "keyword",
        "ignore_above": 2048,
    }


def test_the_exception_field_is_a_nested_object_not_a_flat_string():
    exception = logging_setup.LOG_MAPPING_PROPERTIES["exception"]
    assert set(exception["properties"]) == {"type", "message", "stack"}


# ── ISM policy ───────────────────────────────────────────────────────────────


def test_the_logging_policy_rolls_on_size_or_age_and_then_deletes():
    """Both conditions are needed: size alone lets a quiet week produce one
    enormous stale index, age alone lets a busy day produce one enormous
    index."""
    target = logging_setup.target_for("production")
    states = {
        s["name"]: s
        for s in logging_setup.build_ism_policy_body(target)["policy"]["states"]
    }
    rollover = states["hot"]["actions"][0]["rollover"]
    assert rollover == {
        "min_size": logging_setup.ROLLOVER_SIZE,
        "min_index_age": logging_setup.ROLLOVER_AGE,
    }
    assert states["delete"]["actions"] == [{"delete": {}}]


@pytest.mark.parametrize("environment", ["local", "production"])
def test_retention_starts_after_rollover(environment):
    target = logging_setup.target_for(environment)
    transition = logging_setup.build_ism_policy_body(target)["policy"]["states"][0][
        "transitions"
    ][0]
    assert transition == {
        "state_name": "delete",
        "conditions": {"min_rollover_age": target.retention_age},
    }


@pytest.mark.parametrize("environment", ["local", "production"])
def test_the_retention_age_is_longer_than_the_rollover_age(environment):
    """Deleting sooner than the roll would delete the write index. Pinned as an
    arithmetic sanity check on two constants that are edited independently."""
    target = logging_setup.target_for(environment)
    assert int(target.retention_age.rstrip("d")) > int(
        logging_setup.ROLLOVER_AGE.rstrip("d")
    )


def test_the_ism_template_auto_attaches_the_policy_to_future_indices():
    """Without ``ism_template`` every rolled-over index would need the policy
    attached by hand, and the first missed one grows forever."""
    target = logging_setup.target_for("production")
    ism_template = logging_setup.build_ism_policy_body(target)["policy"]["ism_template"][0]
    assert ism_template == {
        "index_patterns": [target.index_pattern],
        "priority": logging_setup.POLICY_PRIORITY,
    }


def test_one_sem_msr_policy_covers_both_measurement_history_families():
    """A single shared policy is the documented design; per-family policies
    would let the two drift apart on retention."""
    ism_template = sem_msr.build_ism_policy_body()["policy"]["ism_template"][0]
    assert ism_template["index_patterns"] == ["meas_hist_cdsem-*", "meas_hist_hvsem-*"]


# ── initial index body ───────────────────────────────────────────────────────


def test_the_first_index_is_created_as_the_alias_write_index():
    """``is_write_index: True`` is what makes the alias writable at all; an
    alias over an index without it rejects every index request."""
    target = logging_setup.target_for("production")
    aliases = logging_setup.build_initial_index_body(target)["aliases"]
    assert aliases == {target.alias: {"is_write_index": True}}
    assert sem_msr.build_initial_index_body("meas_hist_cdsem")["aliases"] == {
        "meas_hist_cdsem": {"is_write_index": True}
    }


# ── the dry-run plan ─────────────────────────────────────────────────────────


def test_client_configuration_comes_only_from_ops_store(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(logging_setup, "create_client", lambda: sentinel)
    monkeypatch.setattr(logging_setup, "load_env_file", lambda: None)
    assert logging_setup.create_skewnono_client() is sentinel


def test_an_exported_opensearch_host_is_never_overwritten_by_the_env_file(
    monkeypatch,
):
    """The script self-loads ``back_dev_home/.env`` so a bare run finds
    credentials, but an operator who exported a host on the command line is
    pointing at a specific cluster on purpose."""
    monkeypatch.setenv("OPENSEARCH_HOST", "exported.example")
    logging_setup.load_env_file()
    assert os.environ["OPENSEARCH_HOST"] == "exported.example"


def test_the_dry_run_plan_lists_exactly_the_requests_the_real_run_sends():
    """The plan is only useful as a review artefact if it is complete —
    policy, template, first index, and the additive mapping update."""
    target = logging_setup.target_for("production")
    plan = logging_setup.build_dry_run_plan(target)
    assert set(plan) == {
        "cluster",
        "policy_request",
        "template_request",
        "initial_index_request",
        "mapping_update_request",
    }
    assert plan["policy_request"]["path"] == (
        f"/_plugins/_ism/policies/{target.policy_id}"
    )
    assert plan["initial_index_request"]["path"] == f"/{target.first_index}"
    assert plan["template_request"]["path"] == (
        f"/_index_template/{target.template_name}"
    )
    assert plan["mapping_update_request"]["path"] == f"/{target.alias}/_mapping"


def test_the_sem_msr_dry_run_plan_covers_every_alias():
    plan = sem_msr.build_dry_run_plan()
    assert set(plan["template_requests"]) == set(sem_msr.INDEX_ALIASES)
    assert set(plan["initial_index_requests"]) == set(sem_msr.INDEX_ALIASES)


def test_sem_msr_client_refuses_to_run_with_an_unset_password():
    """The password is a blank module constant that the operator fills in
    before running the script. Failing here beats sending anonymous requests
    to a production cluster and reading the 401 as "index missing"."""
    with pytest.raises(RuntimeError, match="OPENSEARCH_PASSWORD"):
        sem_msr.create_skewnono_client()


def test_a_bare_run_provisions_both_environments():
    """The script is run by hand at the office as a plain file path. Requiring
    ``--environment`` there bought nothing — both families live on the same
    cluster and every step is idempotent — so the no-argument run is the one
    the runbook actually wants."""
    assert logging_setup.parse_args([]).environment == "all"
    assert logging_setup.parse_args([]).dry_run is False


def test_an_unknown_environment_is_still_refused():
    with pytest.raises(SystemExit):
        logging_setup.parse_args(["--environment", "staging"])


def test_all_selects_local_then_production():
    assert [
        target.environment for target in logging_setup.selected_targets("all")
    ] == ["local", "production"]


# ── the ensure_rollover_index guard rails ────────────────────────────────────


class FakeIndices:
    """Minimal ``client.indices`` surface for ``OSIndex.exists``/``describe``.

    ``aliases`` maps an index name to its alias config, exactly as
    ``indices.get`` returns it, so the real ``_summarize_aliases`` /
    ``_build_rollover_summary`` code runs unmodified underneath.
    """

    def __init__(self, indices: dict[str, dict], alias_names: set[str] | None = None):
        self.payload = indices
        self.alias_names = alias_names or set()
        self.created: list[tuple[str, dict]] = []

    def exists(self, index=None):
        # `HEAD /<target>` resolves aliases as well as concrete indices --
        # opensearch-py documents the argument as "data streams, indexes, and
        # aliases". Answering False for an alias here (as this fake used to)
        # hid a real failure: OSIndex.describe skips its exists_alias call
        # whenever exists() is True, so against a live cluster a healthy
        # rollover alias came back with is_alias=False and an empty rollover
        # summary, and both the writer preflight and this script's own re-run
        # guard rejected the alias they had just created.
        return index in self.payload or index in self.alias_names

    def exists_alias(self, name=None):
        return name in self.alias_names

    def get(self, index=None):
        resolved = {}
        for name in index.split(","):
            if name in self.payload:
                resolved[name] = self.payload[name]
                continue
            resolved.update(
                {
                    idx: details
                    for idx, details in self.payload.items()
                    if name in details.get("aliases", {})
                }
            )
        return resolved

    def get_alias(self, name=None, index=None):
        if name is not None:
            return {
                idx: details for idx, details in self.payload.items()
                if name in details.get("aliases", {})
            }
        return {idx: self.payload[idx] for idx in index.split(",")}

    def create(self, index=None, body=None):
        self.created.append((index, body))
        return {"acknowledged": True}


class FakeClient:
    def __init__(self, indices: FakeIndices) -> None:
        self.indices = indices


def _healthy_alias(target) -> FakeClient:
    alias = target.alias
    return FakeClient(
        FakeIndices(
            {target.first_index: {"aliases": {alias: {"is_write_index": True}}}},
            alias_names={alias},
        )
    )


@pytest.mark.parametrize("environment", ["local", "production"])
def test_existing_rollover_alias_is_not_recreated(environment):
    """Re-running the provisioning script must be a safe no-op — that is the
    whole reason it checks before creating."""
    target = logging_setup.target_for(environment)
    client = _healthy_alias(target)
    result = logging_setup.ensure_rollover_index(client, target)
    assert result["created"] is False
    assert result["write_index"] == target.first_index
    assert client.indices.created == []


def test_a_missing_alias_creates_the_first_index_with_the_alias_attached():
    target = logging_setup.target_for("production")
    client = FakeClient(FakeIndices({}))
    result = logging_setup.ensure_rollover_index(client, target)
    assert result["created"] is True
    index, body = client.indices.created[0]
    assert index == target.first_index
    assert body["aliases"] == {target.alias: {"is_write_index": True}}
    assert body["mappings"] == logging_setup.build_index_mappings()


def test_an_alias_whose_write_index_lacks_a_numbered_suffix_is_refused():
    """Creating anything on top of a non-rollover alias would produce an index
    family ISM can never roll. The script stops and asks a human."""
    target = logging_setup.target_for("production")
    alias = target.alias
    client = FakeClient(
        FakeIndices(
            {"skewnono_logging_plain": {"aliases": {alias: {"is_write_index": True}}}},
            alias_names={alias},
        )
    )
    with pytest.raises(RuntimeError, match="not a rollover alias"):
        logging_setup.ensure_rollover_index(client, target)


def test_an_alias_with_no_write_index_at_all_is_refused():
    """Several backing indices and no ``is_write_index`` means writes are
    ambiguous; OpenSearch rejects them and ISM cannot roll."""
    target = logging_setup.target_for("production")
    alias = target.alias
    client = FakeClient(
        FakeIndices(
            {target.first_index: {"aliases": {alias: {}}}},
            alias_names={alias},
        )
    )
    with pytest.raises(RuntimeError, match="not a rollover alias"):
        logging_setup.ensure_rollover_index(client, target)


def test_a_bare_first_index_without_the_alias_is_refused():
    """The index name is taken but not aliased — creating it again would fail,
    and adopting it silently could attach the write alias to someone else's
    data."""
    target = logging_setup.target_for("production")
    client = FakeClient(FakeIndices({target.first_index: {"aliases": {}}}))
    with pytest.raises(RuntimeError, match="already exists without"):
        logging_setup.ensure_rollover_index(client, target)


def test_the_sem_msr_guard_rail_names_the_offending_alias():
    """Two families share one script, so the error has to say which one."""
    client = FakeClient(
        FakeIndices({"meas_hist_cdsem-000001": {"aliases": {}}})
    )
    with pytest.raises(RuntimeError, match="meas_hist_cdsem-000001"):
        sem_msr.ensure_rollover_index(client, "meas_hist_cdsem")


def test_the_backend_log_handler_and_this_script_agree_on_the_alias():
    """Cross-package pin. The Flask handler writes to an alias it does not
    create; if the two names drift, production logging lands in an
    auto-created index with no template and no retention policy.

    ``back_dev_home/_logging/tests/test_opensearch_handler.py`` asserts the
    same equality from the other side — kept here too so a change to
    ``ops_index_mgmt`` fails in its own suite rather than only in the feature's.
    """
    from back_dev_home._logging import opensearch_handler

    assert (
        opensearch_handler.DEFAULT_INDEX
        == logging_setup.target_for("production").alias
    )


# ── writer/reader alias agreement ────────────────────────────────────────────


def test_provisioned_aliases_match_the_runtime_logging_targets():
    """The environment→alias map exists twice on purpose — the provisioning
    script must not import Flask plumbing — but if the strings drift, requests
    silently land in an auto-created index the readers never query."""
    from back_dev_home._logging.target import resolve_logging_target

    for environment in ("local", "production"):
        runtime = resolve_logging_target({"SKEWNONO_LOG_ENV": environment})
        provisioned = logging_setup.target_for(environment)
        assert runtime.alias == provisioned.alias
        assert runtime.deployment == environment
