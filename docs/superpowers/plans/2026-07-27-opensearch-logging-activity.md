# OpenSearch Logging and Activity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store SKEWNONO product activity and operational logs in environment-isolated OpenSearch rollover families, then serve `/activity` and `/admin/logs` from those canonical documents through `ops_store`.

**Architecture:** A one-time script under `ops_index_mgmt/` provisions local and production aliases on the same company cluster. Flask resolves one logging target, classifies every request once, and asynchronously writes one idempotent canonical document through `OSDoc`; the activity and admin-log office adapters read that same alias through `OSSearch`. Mock adapters remain network-free for automated tests.

**Tech Stack:** Python 3.11-compatible Flask code, `ops_store` (`OSIndex`, `OSDoc`, `OSSearch`), OpenSearch ISM and aggregations, pytest, Nuxt 4, Vue 3, TypeScript, Node test runner, Markdown.

## Global Constraints

- The application and every logging destination remain inside the company network; do not add external SaaS or internet egress.
- Office localhost and production use the same OpenSearch cluster but different aliases: `skewnono_logging_local` and `skewnono_logging`.
- Local retention is at least 30 days after rollover; production retention is at least 365 days after rollover.
- Both families roll over at 20GB or 7 days, use 2 primary shards, 1 replica, and a 30-second refresh interval.
- Only `ops_index_mgmt/skewnono_logging.py` may create or update logging policies, templates, mappings, aliases, or backing indices.
- Runtime writes use `ops_store.OSDoc`; runtime reads use `ops_store.OSSearch`; runtime alias validation uses `ops_store.OSIndex`.
- The application must not infer logging behavior from `is_cloud()`; `SKEWNONO_LOG_ENV=local|production` is the logging target.
- Request processing must never wait for or fail because of OpenSearch logging.
- No request or response body, authentication header, cookie, password, token, or unredacted secret may be stored.
- `fab_name` remains the scalar backend/DB name; OpenSearch stores the normalized list as `fab_name_list`.
- `activity_kind` is exactly `entry`, `feature`, `background`, or `operation`.
- `/api/sem-list` is `entry`: it counts toward active-user and first/last-seen metrics, but never toward top-feature or FAB page rankings.
- Activity calendar boundaries use `Asia/Seoul`; document timestamps remain UTC.
- Production `first_seen` means earliest retained activity within approximately 365–372 days; local means approximately 30–37 days.
- Automated tests must not connect to the company cluster or mutate real indices.
- Python source must remain compatible with the repository's `target-version = "py311"` rule; add no dependency.
- Preserve the `routes.py` → `data.py` → `providers/mock.py` / `providers/office.py` seam.
- `providers/office_example.py` is tracked; the office copies it to gitignored `providers/office.py`.
- Do not modify or stage the user's unrelated `.remember/today-2026-07-27.md` change.

## File Map

| File | Responsibility |
| --- | --- |
| `ops_index_mgmt/skewnono_logging.py` | Pure builders plus the one-time, idempotent local/production provisioning command. |
| `back_dev_home/_logging/target.py` | Validate `SKEWNONO_LOG_ENV` and return the one runtime alias/deployment target. |
| `back_dev_home/_logging/policy.py` | Normalize FAB context, redact query data, and classify request activity. |
| `back_dev_home/_logging/opensearch_handler.py` | Canonical document conversion, bounded queue, rollover-alias preflight, idempotent bulk retry, and diagnostics. |
| `back_dev_home/_logging/activity.py` | Flask request lifecycle integration and the single request-log emission point. |
| `back_dev_home/activity/providers/mock.py` | Network-free, request-context-aware activity aggregation for local tests. |
| `back_dev_home/activity/providers/opensearch_reader.py` | KST-aware OpenSearch aggregation implementation behind the activity office adapter. |
| `back_dev_home/activity/providers/office_example.py` | Thin tracked office adapter exposing the existing activity provider interface. |
| `back_dev_home/admin_logs/query.py` | Shared log query parsing and OpenSearch-hit normalization. |
| `back_dev_home/admin_logs/providers/mock.py` | Deterministic in-memory log dataset only. |
| `back_dev_home/admin_logs/providers/office_example.py` | Configured-alias OpenSearch search implementation. |
| `front-dev-home/app/utils/operationalDataError.ts` | Pure 403/503 error-to-copy normalization used by both log-backed pages. |
| `front-dev-home/app/pages/activity.vue` | Activity unavailable state and distinct-active-user FAB labeling. |
| `front-dev-home/app/pages/admin/logs.vue` | Environment-neutral title, resolved alias, and explicit unavailable state. |

---

### Task 1: Provision Both Logging Index Families

**Files:**
- Modify: `ops_index_mgmt/skewnono_logging.py`
- Modify: `tests/test_vendored_ops_index_mgmt.py`

**Interfaces:**
- Consumes: `ops_store.create_client()` and `ops_store.OSIndex`.
- Produces: `LoggingIndexTarget`, `target_for(environment)`, environment-parameterized `build_*` functions, `setup_skewnono_logging(target, client=None)`, and CLI `--environment local|production|all`.

- [ ] **Step 1: Replace the single-family characterization tests with failing two-family tests**

Add target, mapping, retention, and secret-source assertions:

```python
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


def test_logging_mapping_is_explicit_and_canonical():
    mappings = logging_setup.build_index_mappings()
    assert mappings["dynamic"] == "false"
    properties = mappings["properties"]
    assert properties["event_id"] == {"type": "keyword"}
    assert properties["deployment"] == {"type": "keyword"}
    assert properties["api_token_id"] == {"type": "keyword"}
    assert properties["activity_kind"] == {"type": "keyword"}
    assert properties["fab_name_list"] == {"type": "keyword"}


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


def test_client_configuration_comes_only_from_ops_store(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(logging_setup, "create_client", lambda: sentinel)
    assert logging_setup.create_skewnono_client() is sentinel
```

Update every existing logging-family test to call
`target = logging_setup.target_for("production")` and pass that target to the
builder or ensure function it exercises. Remove the stale assertion that
`dynamic == "true"` and the blank module-password test. Rewrite the module
docstring so it describes both company-cluster families and environment-only
credentials instead of a production-only alias with embedded connection
defaults.

- [ ] **Step 2: Run the focused tests and confirm the old single-target module fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_vendored_ops_index_mgmt.py -q
```

Expected: failures naming missing `target_for`, missing target parameters,
`dynamic == "true"`, `min_index_age`, and module-level credential constants.

- [ ] **Step 3: Introduce immutable target definitions and parameterize all pure builders**

Replace hardcoded family-name and retention constants with:

```python
from dataclasses import dataclass
from typing import Literal

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
```

Give each builder and cluster operation a required
`target: LoggingIndexTarget` parameter. The resulting typed interfaces are:

- `build_index_settings(target) -> dict[str, Any]`
- `build_ism_policy_body(target) -> dict[str, Any]`
- `build_index_template_body(target) -> dict[str, Any]`
- `build_initial_index_body(target) -> dict[str, Any]`
- `ensure_rollover_index(client, target) -> dict[str, Any]`
- `put_ism_policy(client, target) -> dict[str, Any]`
- `put_index_template(client, target) -> dict[str, Any]`
- `put_current_mapping(client, target) -> dict[str, Any]`
- `build_dry_run_plan(target) -> dict[str, Any]`

Keep the rollover action unchanged and change only the delete transition:

```python
{
    "state_name": "delete",
    "conditions": {"min_rollover_age": target.retention_age},
}
```

Build the canonical mapping with `dynamic: "false"` and explicitly include:

```python
LOG_MAPPING_PROPERTIES = {
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
```

Keep `request_path` out of new documents and templates; the admin reader will
retain its legacy fallback when reading older backing indices.

- [ ] **Step 4: Make client creation environment-only and implement an idempotent multi-target CLI**

Use `ops_store` configuration without embedded cluster values:

```python
def create_skewnono_client() -> Any:
    return create_client()


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
```

Make CLI target selection mandatory and allow the one-time office command to
create both families:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment",
        required=True,
        choices=("local", "production", "all"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def selected_targets(
    environment: str,
) -> tuple[LoggingIndexTarget] | tuple[LoggingIndexTarget, LoggingIndexTarget]:
    if environment == "all":
        return (TARGETS["local"], TARGETS["production"])
    return (target_for(environment),)
```

`main()` must build one shared client only for non-dry runs, process every
selected target, and print:

```json
{
  "local": {},
  "production": {}
}
```

Each value is that target's dry-run plan or setup result. Never print an
OpenSearch password or the complete environment mapping.

- [ ] **Step 5: Add CLI and guard-rail tests**

Add:

```python
def test_environment_is_required_before_any_cluster_call():
    with pytest.raises(SystemExit):
        logging_setup.parse_args([])


def test_all_selects_local_then_production():
    assert [t.environment for t in logging_setup.selected_targets("all")] == [
        "local",
        "production",
    ]


@pytest.mark.parametrize("environment", ["local", "production"])
def test_existing_rollover_alias_is_not_recreated(environment):
    target = logging_setup.target_for(environment)
    client = _healthy_alias(target)
    result = logging_setup.ensure_rollover_index(client, target)
    assert result["created"] is False
    assert result["write_index"] == target.first_index
    assert client.indices.created == []
```

Refactor `_healthy_alias(target)` and every conflicting-index test to derive
its names from the passed target. Assert `build_dry_run_plan(target)` contains
the target-specific policy, template, first index, and mapping update paths.

- [ ] **Step 6: Run the index-management tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_vendored_ops_index_mgmt.py tests/test_vendored_ops_store.py -q
```

Expected: PASS with no network access.

- [ ] **Step 7: Commit Task 1**

```bash
git add ops_index_mgmt/skewnono_logging.py tests/test_vendored_ops_index_mgmt.py
git commit -m "feat(logging): provision local and production index families"
```

---

### Task 2: Centralize Runtime Target, Redaction, FAB Normalization, and Activity Policy

**Files:**
- Create: `back_dev_home/_logging/target.py`
- Create: `back_dev_home/_logging/policy.py`
- Create: `back_dev_home/_logging/tests/test_target.py`
- Create: `back_dev_home/_logging/tests/test_policy.py`

**Interfaces:**
- Consumes: a mapping compatible with `os.environ`.
- Produces: `LoggingTarget`, `LoggingConfigurationError`,
  `resolve_logging_target(environ=None)`, `ActivityDecision`,
  `classify_activity`, `normalize_fab_name_list(values)`, and
  `sanitize_query_string(raw)`.

- [ ] **Step 1: Write failing target-resolution tests**

```python
import pytest

from back_dev_home._logging.target import (
    LoggingConfigurationError,
    resolve_logging_target,
)


@pytest.mark.parametrize(
    ("value", "alias"),
    [
        ("local", "skewnono_logging_local"),
        ("production", "skewnono_logging"),
    ],
)
def test_target_resolves_one_alias(value, alias):
    target = resolve_logging_target({"SKEWNONO_LOG_ENV": value})
    assert target.environment == value
    assert target.deployment == value
    assert target.alias == alias


@pytest.mark.parametrize("value", ["", "cloud", "LOCAL"])
def test_missing_or_invalid_target_fails_closed(value):
    with pytest.raises(LoggingConfigurationError, match="SKEWNONO_LOG_ENV"):
        resolve_logging_target({"SKEWNONO_LOG_ENV": value})
```

- [ ] **Step 2: Run target tests and verify the module is missing**

Run:

```bash
.venv/bin/python -m pytest back_dev_home/_logging/tests/test_target.py -q
```

Expected: collection fails with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the small target interface**

```python
from dataclasses import dataclass
from os import environ
from typing import Literal, Mapping

LoggingEnvironment = Literal["local", "production"]


class LoggingConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoggingTarget:
    environment: LoggingEnvironment
    alias: str
    deployment: str


_TARGETS = {
    "local": LoggingTarget("local", "skewnono_logging_local", "local"),
    "production": LoggingTarget("production", "skewnono_logging", "production"),
}


def resolve_logging_target(
    values: Mapping[str, str] | None = None,
) -> LoggingTarget:
    source = environ if values is None else values
    raw = source.get("SKEWNONO_LOG_ENV", "")
    try:
        return _TARGETS[raw]
    except KeyError as exc:
        raise LoggingConfigurationError(
            "SKEWNONO_LOG_ENV must be 'local' or 'production'"
        ) from exc
```

- [ ] **Step 4: Write failing policy tests for precedence, FAB lists, and redaction**

```python
from back_dev_home._logging.policy import (
    classify_activity,
    normalize_fab_name_list,
    sanitize_query_string,
)


def test_activity_precedence_is_operation_background_entry_feature():
    assert classify_activity(
        user_id="u1", api_token_id="tok", path="/api/sem-list",
        status=200, feature="sem_list",
    ) == ("operation", 0)
    assert classify_activity(
        user_id="u1", api_token_id=None,
        path="/api/cdsem/live-alarm", status=200, feature="live_alarm",
    ) == ("background", 0)
    assert classify_activity(
        user_id="u1", api_token_id=None, path="/api/sem-list",
        status=200, feature="sem_list",
    ) == ("entry", 1)
    assert classify_activity(
        user_id="u1", api_token_id=None,
        path="/api/cdsem/recipe-search", status=200,
        feature="recipe_search",
    ) == ("feature", 1)


def test_failed_anonymous_and_internal_requests_are_operation():
    cases = [
        (None, None, "/api/cdsem/storage", 200),
        ("u1", None, "/api/cdsem/storage", 404),
        ("u1", None, "/api/activity/summary", 200),
        ("u1", None, "/api/admin/logs", 200),
        ("u1", None, "/api/health/services", 200),
        ("u1", None, "/login", 200),
    ]
    for user_id, token_id, path, status in cases:
        assert classify_activity(
            user_id=user_id,
            api_token_id=token_id,
            path=path,
            status=status,
            feature="x",
        ) == ("operation", 0)


def test_fab_list_is_uppercase_ordered_and_deduplicated():
    assert normalize_fab_name_list(["M14,m16", " M14 ", "", None]) == [
        "M14",
        "M16",
    ]


def test_query_redacts_sensitive_values_and_caps_length():
    sanitized = sanitize_query_string(
        b"fab_name=M14&access_token=secret&password=pw&q=recipe"
    )
    assert "fab_name=M14" in sanitized
    assert "q=recipe" in sanitized
    assert "secret" not in sanitized
    assert "pw" not in sanitized
    assert sanitized.count("%5BREDACTED%5D") == 2
    assert len(sanitize_query_string(("q=" + "x" * 3000).encode())) == 2048
```

- [ ] **Step 5: Run policy tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest back_dev_home/_logging/tests/test_policy.py -q
```

Expected: collection fails with `ModuleNotFoundError`.

- [ ] **Step 6: Implement explicit classification and safe normalization**

Use an immutable tuple-compatible decision so tests and callers can unpack it:

```python
from typing import Literal, NamedTuple
from urllib.parse import parse_qsl, urlencode

ActivityKind = Literal["entry", "feature", "background", "operation"]


class ActivityDecision(NamedTuple):
    kind: ActivityKind
    weight: int


_OPERATION_PREFIXES = (
    "/api/activity",
    "/api/admin",
    "/api/health",
    "/api/account/api-tokens",
)
_BACKGROUND_EXACT = {
    "/api/cdsem/live-alarm",
    "/api/hvsem/live-alarm",
    "/api/msr-image",
}
_BACKGROUND_CHILD_PREFIXES = (
    "/api/msr-images",
)
_SENSITIVE_QUERY_PARTS = (
    "password",
    "passwd",
    "token",
    "api_key",
    "secret",
    "authorization",
    "cookie",
)


def _at_or_below(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def classify_activity(
    *,
    user_id: str | None,
    api_token_id: str | None,
    path: str,
    status: int,
    feature: str,
) -> ActivityDecision:
    if (
        not user_id
        or user_id == "-"
        or api_token_id
        or status >= 400
        or not path.startswith("/api/")
        or any(_at_or_below(path, prefix) for prefix in _OPERATION_PREFIXES)
    ):
        return ActivityDecision("operation", 0)
    if path in _BACKGROUND_EXACT or any(
        path.startswith(prefix + "/") for prefix in _BACKGROUND_CHILD_PREFIXES
    ):
        return ActivityDecision("background", 0)
    if feature == "sem_list":
        return ActivityDecision("entry", 1)
    return ActivityDecision("feature", 1)
```

Implement `normalize_fab_name_list(values)` by splitting every non-null input
on commas, trimming, uppercasing, discarding empties, and preserving first-seen
order with a `set`. Implement `sanitize_query_string(raw)` by decoding with
`errors="replace"`, passing the decoded value to `parse_qsl` with
`keep_blank_values=True`, matching sensitive keys case-insensitively after
replacing hyphens with underscores, and checking whether any member of
`_SENSITIVE_QUERY_PARTS` occurs in the normalized key. Replace matching
values with `[REDACTED]`, call `urlencode`, and apply a final 2,048-character
slice.

- [ ] **Step 7: Run both new suites**

Run:

```bash
.venv/bin/python -m pytest \
  back_dev_home/_logging/tests/test_target.py \
  back_dev_home/_logging/tests/test_policy.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add \
  back_dev_home/_logging/target.py \
  back_dev_home/_logging/policy.py \
  back_dev_home/_logging/tests/test_target.py \
  back_dev_home/_logging/tests/test_policy.py
git commit -m "feat(logging): centralize target and activity policy"
```

---

### Task 3: Make OpenSearch Bulk Delivery Idempotent and Observable

**Files:**
- Modify: `back_dev_home/_logging/opensearch_handler.py`
- Modify: `back_dev_home/_logging/tests/test_opensearch_handler.py`
- Modify: `back_dev_home/_logging/tests/conftest.py`

**Interfaces:**
- Consumes: `LoggingTarget`, `resolve_logging_target()`,
  `ops_store.create_client()`, `OSIndex.describe()`, and `OSDoc.bulk()`.
- Produces: `HandlerDiagnostics`, `OpenSearchBulkHandler.snapshot()`, and
  a target-aware `install_opensearch_logging` function.

- [ ] **Step 1: Add failing canonical-document and diagnostics tests**

Extend the `_record` test helper inputs and assert:

```python
def test_document_has_identity_environment_and_bounded_fields(parked):
    parked._deployment = "local"
    doc = parked._record_to_doc(
        _record(
            message="x" * 5000,
            request_id="req-1",
            activity_kind="entry",
            fab_name_list=["M14", "M16"],
            error_name="e" * 2000,
        )
    )
    assert doc["event_id"]
    assert doc["service"] == "skewnono"
    assert doc["deployment"] == "local"
    assert doc["request_id"] == "req-1"
    assert doc["activity_kind"] == "entry"
    assert doc["fab_name_list"] == ["M14", "M16"]
    assert len(doc["message"]) == 4096
    assert len(doc["error_name"]) == 1024


def test_full_queue_increments_drop_count_without_blocking():
    handler = _ParkedShipper(queue_size=1)
    try:
        handler.emit(_record())
        handler.emit(_record())
        snapshot = handler.snapshot()
        assert snapshot.enqueued == 1
        assert snapshot.queue_full_dropped == 1
        assert snapshot.bulk_dropped == 0
        assert snapshot.dropped == 1
        assert snapshot.queue_depth == 1
    finally:
        handler.close()
```

Change `_record` to accept `message: str | None = None` and assign
`msg = message if message is not None else "hello %s"` before constructing
the `LogRecord`. When `message` is provided, force `args=()` so the long value
is returned by `record.getMessage()` rather than stored as a nonstandard
attribute.

Extend the existing unmapped-extra test with
`authorization="Bearer secret"`, `cookie="session=secret"`, and
`request_body={"password": "secret"}`. Assert all three keys and values are
absent from the converted document.

- [ ] **Step 2: Add failing alias-preflight and retry tests**

Add a `_ParkedBulkShipper(OpenSearchBulkHandler)` test helper that overrides
only `_run` to wait on `_stopped`; unlike `_ParkedShipper`, it must exercise
the production `_flush`. Give it fake services through the exact constructor
seams `index_service_factory` and `doc_service_factory`:

```python
class _ParkedBulkShipper(OpenSearchBulkHandler):
    def __init__(self, **kwargs):
        kwargs.setdefault("client_factory", lambda: object())
        kwargs.setdefault("deployment", "local")
        kwargs.setdefault("host", "test-host")
        super().__init__(**kwargs)

    def _run(self):
        self._stopped.wait()


class _BulkRecorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def bulk(self, actions, **_kwargs):
        self.calls.append(list(actions))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _IndexDescription:
    def __init__(self, description):
        self.description = description

    def describe(self, _index):
        return self.description


def _ready_index_factory(_client, _index):
    return _IndexDescription({
        "is_alias": True,
        "rollover": {"ready": True, "uses_numbered_suffix": True},
    })


def _plain_index_factory(_client, _index):
    return _IndexDescription({
        "is_alias": False,
        "rollover": {"ready": False, "uses_numbered_suffix": False},
    })


def test_bulk_actions_use_event_id_as_opensearch_id():
    docs = _BulkRecorder(responses=[(1, [])])
    handler = _ParkedBulkShipper(
        index_service_factory=_ready_index_factory,
        doc_service_factory=lambda _client, _index: docs,
    )
    try:
        doc = handler._record_to_doc(_record())
        handler._flush([doc])
        action = docs.calls[0][0]
        assert action["_id"] == doc["event_id"]
        assert action["_source"] == doc
    finally:
        handler.close()


def test_transport_failure_retries_twice_then_succeeds():
    docs = _BulkRecorder(
        responses=[ConnectionError("one"), ConnectionError("two"), (1, [])]
    )
    sleeps = []
    handler = _ParkedBulkShipper(
        index_service_factory=_ready_index_factory,
        doc_service_factory=lambda _client, _index: docs,
        sleep_fn=sleeps.append,
    )
    try:
        handler._flush([handler._record_to_doc(_record())])
        assert sleeps == [0.5, 1.0]
        assert handler.snapshot().indexed == 1
        assert handler.snapshot().retries == 2
        assert handler.snapshot().queue_full_dropped == 0
        assert handler.snapshot().bulk_dropped == 0
        assert handler.snapshot().dropped == 0
    finally:
        handler.close()


def test_non_rollover_alias_is_never_bulk_written():
    docs = _BulkRecorder(responses=[])
    handler = _ParkedBulkShipper(
        index_service_factory=_plain_index_factory,
        doc_service_factory=lambda _client, _index: docs,
    )
    try:
        handler._flush([handler._record_to_doc(_record())])
        assert handler.snapshot().indexed == 0
        assert handler.snapshot().bulk_dropped == 1
        assert handler.snapshot().dropped == 1
        assert docs.calls == []
    finally:
        handler.close()
```

For partial failures, add one test where a 429 item is retried and a 400
mapping rejection is dropped without retry. Assert only the failed 429
`event_id` appears in the second bulk call.

- [ ] **Step 3: Run the handler tests and verify failures**

Run:

```bash
.venv/bin/python -m pytest \
  back_dev_home/_logging/tests/test_opensearch_handler.py -q
```

Expected: failures for missing deployment, event ID, snapshot, target
resolution, alias preflight, retry, and bounded text.

- [ ] **Step 4: Implement canonical document conversion and diagnostics**

Add:

```python
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from uuid import uuid4


@dataclass(frozen=True)
class HandlerDiagnostics:
    enqueued: int
    indexed: int
    queue_full_dropped: int
    bulk_dropped: int
    retries: int
    bulk_failures: int
    last_success_at: str | None
    last_failure_at: str | None
    queue_depth: int

    @property
    def dropped(self) -> int:
        return self.queue_full_dropped + self.bulk_dropped
```

Store mutable counters behind a lock and return a copied
`HandlerDiagnostics` from `snapshot()`. Remove legacy `request_path` from
`_KNOWN_EXTRA_KEYS`, then add `activity_kind` and `fab_name_list`. Give the
handler a required
`deployment`, optional `uuid_factory=uuid4`, optional
`sleep_fn=time.sleep`, and these injectable service factories:

```python
index_service_factory: Callable[[Any, str], Any] = _make_index_service
doc_service_factory: Callable[[Any, str], Any] = _make_doc_service
```

`_make_index_service(client, index)` lazily imports and returns
`OSIndex(client=client, index=index)`. `_make_doc_service(client, index)`
lazily imports and returns `OSDoc(client=client, index=index)`. Tests pass
factories returning fakes; runtime callers use the defaults.
Update the existing `_Shipper` test helper to default `deployment="test"` so
all older unit tests satisfy the now-required constructor argument. Rewrite
the test module docstring to describe environment-selected internal logging,
not production-only `is_cloud()` behavior. Expose read-only `index` and
`deployment` properties on `OpenSearchBulkHandler`; make `_StubHandler` copy
those two constructor values to matching attributes for installer tests.

Create each source with:

```python
doc = {
    "event_id": str(self._uuid_factory()),
    "@timestamp": ts,
    "level": record.levelname,
    "logger": record.name,
    "message": _bounded(record.getMessage(), 4096),
    "service": "skewnono",
    "deployment": self._deployment,
    "host": self._host,
}
```

Limit `error_name` to 1,024 characters, exception message to 4,096, and
exception stack to 32,768. Omit `None` request extras and retain empty
`fab_name_list` because it intentionally means no FAB context.

- [ ] **Step 5: Validate the rollover alias before constructing `OSDoc`**

Inside `_ensure_doc_service()` create one shared client, then:

```python
index_service = self._index_service_factory(client, self._index)
description = index_service.describe(self._index)
rollover = description["rollover"]
if (
    not description["is_alias"]
    or not rollover["ready"]
    or not rollover["uses_numbered_suffix"]
):
    raise AliasNotReadyError(
        f"{self._index} is not a ready numbered rollover alias; "
        "run ops_index_mgmt/skewnono_logging.py at the office"
    )
self._doc_service = self._doc_service_factory(client, self._index)
```

This check must run before any bulk indexing so OpenSearch cannot auto-create
a plain `skewnono_logging*` index. Define `AliasNotReadyError(RuntimeError)`
in this module. `_flush` catches it before the transport-retry branch, adds
the whole pending batch to `bulk_dropped`, records one bulk failure, and
returns without sleeping. A later batch performs the preflight again, so an
operator can provision the alias without restarting Flask.

- [ ] **Step 6: Implement three-attempt idempotent bulk delivery**

Build actions with stable IDs:

```python
def _action(self, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "_op_type": "index",
        "_index": self._index,
        "_id": item["event_id"],
        "_source": item,
    }
```

Use three total attempts with backoffs `(0.5, 1.0)`. On transport failure,
retry the pending actions. On `(success_count, errors)`, increment indexed
by `success_count`, parse each error operation's `_id` and `status`, retry
only statuses `{429, 500, 502, 503, 504}`, and count other errors as dropped.
After the third attempt, add all remaining actions to `bulk_dropped`. Increment
`bulk_failures` once for each raised bulk call and once for each returned bulk
response containing item errors; do not count each failed item as a separate
bulk failure. Queue overflow increments only `queue_full_dropped`. Any of
these failures updates `last_failure_at`; a response with indexed documents
updates `last_success_at`. Reset both client-backed services after a transport
failure so the next attempt reconnects and revalidates the alias.

Throttle stderr summaries to at most one every 60 seconds:

```text
[opensearch-log] dropped=<n> retries=<n> failures=<n> queue=<n> last=<reason>
```

Never call a Python logger from this error path.

- [ ] **Step 7: Make shutdown bounded and installer target-aware**

`close()` must set the stop event, join the worker for at most two seconds,
drain the remaining queue, make one normal `_flush()` call, and remain
idempotent.

Change installer ordering so the kill switch wins, missing credentials still
skip with a warning, and configured shipping requires a valid target:

```python
if _logging_disabled(os.environ):
    return None
if not os.environ.get("OPENSEARCH_PASSWORD"):
    _stderr("OPENSEARCH_PASSWORD not set; skipping OpenSearch log handler")
    return None
actual_target = target or resolve_logging_target()
handler = OpenSearchBulkHandler(
    client_factory=create_client,
    index=actual_target.alias,
    deployment=actual_target.deployment,
    level=level,
)
```

Before constructing the handler, find an already attached
`OpenSearchBulkHandler` on the root logger. If it exists, verify its configured
index and deployment match `actual_target`, attach that same instance to any
missing named logger, and return it. Raise `LoggingConfigurationError` on a
target mismatch instead of silently shipping to the old alias. Extend the
install-twice test with `assert len(_StubHandler.made) == 1` so idempotence
covers worker construction, not only logger attachment.

Update installer tests to set both `OPENSEARCH_PASSWORD` and
`SKEWNONO_LOG_ENV`. Add a test that a configured password with no target raises
`LoggingConfigurationError`, while the disabled and no-password paths do not
require `SKEWNONO_LOG_ENV`.

- [ ] **Step 8: Run the logging package tests**

Run:

```bash
.venv/bin/python -m pytest back_dev_home/_logging -q
```

Expected: PASS with no OpenSearch connection.

- [ ] **Step 9: Commit Task 3**

```bash
git add \
  back_dev_home/_logging/opensearch_handler.py \
  back_dev_home/_logging/tests/test_opensearch_handler.py \
  back_dev_home/_logging/tests/conftest.py
git commit -m "feat(logging): harden OpenSearch bulk delivery"
```

---

### Task 4: Emit One Classified Request Document and Keep Mock Activity Honest

**Files:**
- Modify: `back_dev_home/_logging/activity.py`
- Modify: `back_dev_home/_logging/tests/test_activity_middleware.py`
- Modify: `back_dev_home/activity/data.py`
- Modify: `back_dev_home/activity/providers/mock.py`
- Modify: `tests/test_activity_home.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/routes.py`
- Create: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_routes.py`

**Interfaces:**
- Consumes: Task 2 policy functions and Task 3 installer.
- Produces: `promote_request_fab_names(*values)`, request extras carrying
  `request_id`, `activity_kind`, `activity_weight`, and `fab_name_list`, plus
  a mock `record_request` accepting `activity_kind` and `fab_name_list`.

- [ ] **Step 1: Rewrite middleware tests around the canonical fields**

Change the successful sem-list expectation to:

```python
record = _only(records, "request")
assert record.request_id
assert record.feature == "sem_list"
assert record.activity_kind == "entry"
assert record.activity_weight == 1
assert record.fab_name_list == ["M16"]
assert not hasattr(record, "request_path")
```

Add:

```python
def test_multi_fab_query_is_normalized(make_app, records):
    client = make_app(user_id="2067928")
    client.get("/api/cdsem/ppid-unavailable?fab_name=M14,m16,M14")
    assert _only(records, "request").fab_name_list == ["M14", "M16"]


def test_sensitive_query_values_are_redacted(make_app, records):
    client = make_app(user_id="2067928")
    client.get("/api/sem-list?fab_name=M14&access_token=secret")
    query = _only(records, "request").query_string
    assert "secret" not in query
    assert "%5BREDACTED%5D" in query


def test_background_poll_is_logged_but_not_recorded(make_app, records, recorded):
    client = make_app(user_id="2067928")
    client.get("/api/cdsem/live-alarm?fab_name=M14")
    record = _only(records, "request")
    assert (record.activity_kind, record.activity_weight) == ("background", 0)
    assert recorded == []
```

Add the live-alarm test route to the purpose-built Flask app. Update
`recorded` expectations to the new seven-argument call:

```python
(
    "2067928",
    "GET",
    "/api/sem-list",
    200,
    "sem_list",
    "entry",
    ["M16"],
)
```

Update the unhandled-exception test to capture both `request_exception` and
the final `request` record and assert their nonempty `request_id` values are
equal. This preserves one correlation ID across the two operational events
without allowing `request_exception` into activity aggregations.

Replace `test_opensearch_shipping_is_cloud_only` with a test asserting
`install_activity_logging()` always asks the installer once; the installer
itself decides whether credentials and target enable shipping.

- [ ] **Step 2: Add mock aggregation tests for entry exclusion and distinct FAB users**

Add:

```python
def test_entry_counts_activity_but_never_top_features(self):
    activity_mock._users.clear()
    data.record_request(
        "u1", "GET", "/api/sem-list", 200, "sem_list", "entry", ["M14"]
    )
    me = data.get_me("u1")
    self.assertEqual(me["this_month"]["requests"], 1)
    self.assertEqual(me["top_features"], [])


def test_fab_total_is_distinct_users_not_requests(self):
    activity_mock._users.clear()
    for _ in range(3):
        data.record_request(
            "u1", "GET", "/api/cdsem/storage", 200,
            "storage", "feature", ["M14"],
        )
    data.record_request(
        "u2", "GET", "/api/sem-list", 200,
        "sem_list", "entry", ["M14"],
    )
    row = data.get_fab_page_usage()["fabs_7d"][0]
    self.assertEqual(row["fab"], "M14")
    self.assertEqual(row["total"], 2)
    self.assertEqual(row["pages"], [{"feature": "storage", "count": 3}])


def test_multi_fab_request_contributes_to_each_bucket_once(self):
    activity_mock._users.clear()
    data.record_request(
        "u1", "GET", "/api/cdsem/storage", 200,
        "storage", "feature", ["M14", "M16"],
    )
    rows = data.get_fab_page_usage()["fabs_7d"]
    self.assertEqual({row["fab"]: row["total"] for row in rows}, {
        "M14": 1,
        "M16": 1,
    })
```

- [ ] **Step 3: Run middleware and mock tests and confirm failures**

Run:

```bash
.venv/bin/python -m pytest \
  back_dev_home/_logging/tests/test_activity_middleware.py \
  tests/test_activity_home.py -q
```

Expected: failures for old `is_cloud()` gating, raw query strings, missing
fields, old record signature, sem-list feature ranking, and request-count FAB
totals.

- [ ] **Step 4: Integrate policy and request context into the middleware**

Remove imports of `is_cloud` and `is_recordable`. In `before_request`, stamp
both start time and a request ID:

```python
g._activity_t0 = time.perf_counter()
g._activity_request_id = str(uuid4())
g._activity_fab_name_list = []
```

Expose a narrow route helper:

```python
def promote_request_fab_names(*values: str | None) -> None:
    existing = getattr(g, "_activity_fab_name_list", [])
    g._activity_fab_name_list = normalize_fab_name_list([*existing, *values])
```

In `_build_extra`, merge `request.args.getlist("fab_name")` with promoted
values, sanitize `request.query_string`, and compute:

```python
decision = classify_activity(
    user_id=user_id,
    api_token_id=getattr(g, "api_token_id", None),
    path=request.path,
    status=status,
    feature=feature,
)
```

Return `request_id`, `activity_kind=decision.kind`,
`activity_weight=decision.weight`, and `fab_name_list`. Return only `path`, not
legacy `request_path`. Keep unauthenticated `user_id` as `None` in extras so
the handler omits it; use `"-"` only in the human-readable message.

Call mock/provider `record_request` only when `decision.weight == 1`, passing
the kind and FAB list. Call `install_opensearch_logging()` unconditionally
from app setup; its own configuration checks keep home/mock startup
network-free.

- [ ] **Step 5: Promote the one body-sourced FAB without logging the body**

In recipe-search compare, immediately after validating and normalizing
`payload["fab_name"]`, call:

```python
from back_dev_home._logging.activity import promote_request_fab_names

promote_request_fab_names(fab_name)
```

Add a route test that installs the logging middleware, posts:

```json
{"fab_name": "m14", "recipe_names": ["R1", "R2"]}
```

and captures the `skewnono.activity` record to assert
`fab_name_list == ["M14"]`. Assert the raw JSON body and recipe names are
absent from `query_string` and structured extras. Build this as a small Flask
app in the new test file: install a `before_request` hook setting
`g.user_id = "u1"`, register the recipe-search blueprint under `/api`,
monkeypatch `get_recipe_compare_data` to return
`{"tool_type": "cd-sem", "recipes": []}`,
monkeypatch the OpenSearch installer and activity recorder to no-ops, then
attach a list-backed handler to `skewnono.activity`. Do not boot the whole
application or select an office provider for this unit test.

- [ ] **Step 6: Update mock state to preserve kind and request-scoped FAB semantics**

Change `record_request` to:

```python
def record_request(
    user_id: str,
    method: str,
    path: str,
    status: int,
    feature: str,
    activity_kind: str,
    fab_name_list: list[str],
) -> None:
```

Extend `_UserState` with:

```python
daily_features: dict[date, dict[str, int]] = field(default_factory=dict)
daily_fabs: dict[date, set[str]] = field(default_factory=dict)
daily_fab_features: dict[date, dict[str, dict[str, int]]] = field(
    default_factory=dict
)
```

For `entry` and `feature`, increment total, daily, first/last seen. Only
`feature` increments `by_feature`, `daily_features`, and FAB page counts.
Use `fab_name_list or ["미지정"]` for active-user FAB membership.

Rewrite summary top-feature windows from `daily_features` instead of
`_scale_features`. Rewrite FAB windows by iterating users:

```python
active_users: dict[str, set[str]] = {}
page_counts: dict[str, dict[str, int]] = {}
```

For each retained day, add `state.user_id` to every active FAB set and merge
only that day's feature counts into `page_counts`. Emit
`total=len(active_users[fab])`, top ten pages, and `(-total, fab)` ordering.

Remove every `is_cloud()` branch, `_office_reader` import, Redis/OpenSearch
writer attempt, and the permanent `state.fab` production assumption. Seed
demo users by filling the new per-day structures under the seed row's FAB;
treat seeded `sem_list` counts as entry totals and exclude them from
`by_feature`/`daily_features`.

Update `data.record_request` to pass all seven arguments through the selected
adapter. Keep `seed_demo_users` explicitly mock-only.

- [ ] **Step 7: Run affected backend tests**

Run:

```bash
.venv/bin/python -m pytest \
  back_dev_home/_logging \
  back_dev_home/activity \
  back_dev_home/ebeam/hitachi/recipe_search/tests/test_routes.py \
  tests/test_activity_home.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```bash
git add \
  back_dev_home/_logging/activity.py \
  back_dev_home/_logging/tests/test_activity_middleware.py \
  back_dev_home/activity/data.py \
  back_dev_home/activity/providers/mock.py \
  tests/test_activity_home.py \
  back_dev_home/ebeam/hitachi/recipe_search/routes.py \
  back_dev_home/ebeam/hitachi/recipe_search/tests/test_routes.py
git commit -m "feat(activity): classify canonical request logs"
```

---

### Task 5: Aggregate the Logging Alias for `/activity`

**Files:**
- Create: `back_dev_home/activity/providers/opensearch_reader.py`
- Create: `back_dev_home/activity/tests/test_office_template.py`
- Modify: `back_dev_home/activity/providers/office_example.py`
- Modify: `back_dev_home/activity/routes.py`
- Modify: `back_dev_home/activity/tests/test_contract.py`
- Modify: `back_dev_home/activity/MIGRATION.md`

**Interfaces:**
- Consumes: `resolve_logging_target()`, `ops_store.OSSearch.search_raw()`,
  `activity/contracts.py`, and `is_admin(user_id)`.
- Produces: `ActivityOpenSearchReader` methods matching all existing activity
  provider functions; office `record_request` is an explicit no-op.

- [ ] **Step 1: Write failing KST query-shape tests**

Create a fake search object that records request bodies and returns queued
responses. With fixed UTC time `2026-07-27T03:00:00Z` (12:00 KST), assert the
history query contains:

```python
common = [
    {"term": {"event": "request"}},
    {"term": {"activity_weight": 1}},
    {"terms": {"activity_kind": ["entry", "feature"]}},
    {"term": {"user_id": "u1"}},
]
```

Assert its `daily` date histogram uses:

```python
{
    "calendar_interval": "day",
    "time_zone": "Asia/Seoul",
    "format": "yyyy-MM-dd",
    "min_doc_count": 0,
    "extended_bounds": {
        "min": "2026-06-28",
        "max": "2026-07-27",
    },
}
```

Assert every top-feature aggregation adds
`{"term": {"activity_kind": "feature"}}`, so entry documents cannot rank.
Add a target-selection test with an injected resolver returning
`LoggingTarget("local", "skewnono_logging_local", "local")`; assert the
injected search factory receives exactly `skewnono_logging_local`. Repeat with
the production target and assert `skewnono_logging`. These are the same two
aliases used by the writer target tests.

- [ ] **Step 2: Write failing response-normalization tests for all five reads**

Use realistic aggregation envelopes and assert:

```python
assert reader.get_me("u1") == {
    "user_id": "u1",
    "is_admin": False,
    "this_month": {"requests": 5, "days_active": 2},
    "top_features": [{"feature": "storage", "count": 3}],
    "daily": expected_30_days,
    "first_seen": "2026-07-01T01:00:00.000Z",
    "last_seen": "2026-07-27T02:00:00.000Z",
}
```

Add separate assertions that:

- `get_user_history("missing") is None`.
- summary cardinalities become DAU/WAU/MAU and use trailing 1/7/30 KST days.
- users are sorted by `(-requests_30d, user_id)`.
- favorite feature comes only from `activity_kind=feature`.
- FAB `total` comes from `active_users.value`, not bucket `doc_count`.
- empty/missing FAB composite keys normalize to `"미지정"`.
- a multi-valued FAB document can appear in both fake FAB buckets.
- generated timestamps are UTC strings.

- [ ] **Step 3: Run the new office-template tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest \
  back_dev_home/activity/tests/test_office_template.py -q
```

Expected: collection fails because `opensearch_reader.py` and the real office
adapter implementation do not exist.

- [ ] **Step 4: Implement shared time bounds and aggregation helpers**

Create:

```python
KST = ZoneInfo("Asia/Seoul")
TOP_FEATURES_CAP = 10
COMPOSITE_PAGE_SIZE = 1000
CARDINALITY_PRECISION = 40000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _kst_day_start(now: datetime, days_ago: int) -> datetime:
    local = now.astimezone(KST)
    day = local.date() - timedelta(days=days_ago)
    return datetime.combine(day, time.min, tzinfo=KST)


def _activity_filters(user_id: str | None = None) -> list[dict[str, Any]]:
    filters = [
        {"term": {"event": "request"}},
        {"term": {"activity_weight": 1}},
        {"terms": {"activity_kind": ["entry", "feature"]}},
    ]
    if user_id is not None:
        filters.append({"term": {"user_id": user_id}})
    return filters
```

Define every trailing window as an inclusive KST calendar window ending
today: DAU starts at `_kst_day_start(now, 0)`, WAU and 7-day features start at
`_kst_day_start(now, 6)`, and MAU, 30-day features, daily history, users, and
FAB-30 start at `_kst_day_start(now, 29)`. FAB-7 also starts six days ago.
Compute this-month start as midnight KST on day 1. Pass these aware datetimes
to OpenSearch as ISO-8601 range bounds; use the matching KST dates for
histogram `extended_bounds`.

`ActivityOpenSearchReader.__init__` accepts injectable `search_factory`,
`target_resolver`, `now`, and `admin_check`. The default search factory lazily
imports and returns `OSSearch(index=alias)`. `_search(body)` resolves the
target and calls `search_raw(body)`.

- [ ] **Step 5: Implement personal history and summary aggregations**

History query uses top-level user activity filters and these named
aggregations:

```python
{
    "size": 0,
    "track_total_hits": True,
    "query": {"bool": {"filter": _activity_filters(user_id)}},
    "aggs": {
        "first_seen": {"min": {"field": "@timestamp"}},
        "last_seen": {"max": {"field": "@timestamp"}},
        "this_month": {
            "filter": {
                "range": {"@timestamp": {"gte": month_start.isoformat()}}
            },
            "aggs": {
                "days": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "calendar_interval": "day",
                        "time_zone": "Asia/Seoul",
                        "format": "yyyy-MM-dd",
                    }
                }
            },
        },
        "daily": {
            "filter": {"range": {"@timestamp": {"gte": day_30.isoformat()}}},
            "aggs": {"days": {"date_histogram": daily_histogram}},
        },
        "features": {
            "filter": {"term": {"activity_kind": "feature"}},
            "aggs": {
                "items": {
                    "terms": {
                        "field": "feature",
                        "size": 10,
                        "order": {"_count": "desc"},
                    }
                }
            },
        },
    },
}
```

Use `this_month.doc_count` for requests, count nonempty day buckets for active
days, fill all 30 daily values from the histogram, and read min/max
`value_as_string`. Read the exact top-level activity count from
`hits.total.value`; `track_total_hits=True` prevents the default 10,000-hit
cap from changing the existence check. `/me` returns a zeroed contract for an
unknown viewer; `get_user_history` returns `None` when this count is zero.

Summary query uses five filter aggregations: `dau`, `wau`, `mau`,
`top_features_7d`, and `top_features_30d`. User windows contain a
`cardinality` subaggregation on `user_id` with
`precision_threshold: 40000`. Feature windows filter
`activity_kind=feature` and aggregate terms on `feature`.

- [ ] **Step 6: Implement paged user and FAB aggregations**

For users, loop a composite aggregation until `after_key` is absent:

```python
"users": {
    "composite": {
        "size": 1000,
        "sources": [{"user_id": {"terms": {"field": "user_id"}}}],
    },
    "aggs": {
        "days": {
            "date_histogram": {
                "field": "@timestamp",
                "calendar_interval": "day",
                "time_zone": "Asia/Seoul",
            }
        },
        "last_seen": {"max": {"field": "@timestamp"}},
        "feature_only": {
            "filter": {"term": {"activity_kind": "feature"}},
            "aggs": {
                "favorite": {
                    "terms": {"field": "feature", "size": 1}
                }
            },
        },
    },
}
```

The top-level query adds the trailing-30-day range. Map bucket `doc_count` to
`requests_30d`, count nonempty day buckets, use `last_seen.value_as_string`,
and return no zero-request rows.

For each 7/30-day FAB window, page this composite source:

```python
{"fab": {
    "terms": {
        "field": "fab_name_list",
        "missing_bucket": True,
        "missing_order": "last",
    }
}}
```

Subaggregations are:

```python
"active_users": {
    "cardinality": {
        "field": "user_id",
        "precision_threshold": 40000,
    }
},
"feature_only": {
    "filter": {"term": {"activity_kind": "feature"}},
    "aggs": {
        "pages": {
            "terms": {
                "field": "feature",
                "size": 10,
                "order": {"_count": "desc"},
            }
        }
    },
}
```

Normalize a null/empty composite key to `"미지정"`, map active-user
cardinality to `total`, map page buckets to `pages`, and sort rows by
`(-total, fab)`.

- [ ] **Step 7: Wire the tracked office adapter and prevent duplicate writes**

Replace the stubs with:

```python
from back_dev_home.activity.providers.opensearch_reader import (
    ActivityOpenSearchReader,
)

_reader = ActivityOpenSearchReader()

get_me = _reader.get_me
get_summary = _reader.get_summary
get_fab_page_usage = _reader.get_fab_page_usage
get_users_list = _reader.get_users_list
get_user_history = _reader.get_user_history


def record_request(*_args, **_kwargs) -> None:
    return None
```

The no-op is deliberate: Task 4 middleware plus Task 3 handler already writes
the canonical document.

- [ ] **Step 8: Normalize activity OpenSearch failures to route-level 503**

Add a logger and one route helper:

```python
def _query(loader):
    try:
        return jsonify(loader())
    except Exception:
        logger.exception("Failed to query OpenSearch activity")
        return error_json(
            "activity_query_failed",
            "Could not query OpenSearch activity",
            503,
        )
```

Use it for `/me`, `/summary`, `/fabs`, and `/users`. For user detail, catch
query exceptions as 503 first, retain the existing `None` → 404 branch, and
do not include raw OpenSearch exception text in the JSON response.

Add route tests that monkeypatch each data call to raise and assert status 503
plus code `activity_query_failed`.

- [ ] **Step 9: Update activity contract and migration guidance**

Update `MIGRATION.md` to name:

- source aliases selected by `SKEWNONO_LOG_ENV`;
- `ops_store.OSSearch`;
- no Redis writer and no mock fallback;
- KST calendar windows;
- retained-window `first_seen`;
- distinct-user FAB totals;
- `record_request` office no-op;
- office copy and verification commands.

Update the contract-test docstring so it no longer describes a stub. Keep the
existing contract shapes unchanged.

- [ ] **Step 10: Run activity and route tests**

Run:

```bash
.venv/bin/python -m pytest \
  back_dev_home/activity \
  tests/test_activity_home.py \
  back_dev_home/_logging/tests/test_activity_middleware.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit Task 5**

```bash
git add \
  back_dev_home/activity/providers/opensearch_reader.py \
  back_dev_home/activity/providers/office_example.py \
  back_dev_home/activity/routes.py \
  back_dev_home/activity/tests/test_contract.py \
  back_dev_home/activity/tests/test_office_template.py \
  back_dev_home/activity/MIGRATION.md
git commit -m "feat(activity): aggregate OpenSearch logging data"
```

---

### Task 6: Move `/admin/logs` OpenSearch Search Behind the Office Adapter

**Files:**
- Create: `back_dev_home/admin_logs/query.py`
- Create: `back_dev_home/admin_logs/tests/test_office_template.py`
- Modify: `back_dev_home/admin_logs/providers/mock.py`
- Modify: `back_dev_home/admin_logs/providers/office_example.py`
- Modify: `back_dev_home/admin_logs/routes.py`
- Modify: `back_dev_home/admin_logs/tests/test_contract.py`
- Modify: `back_dev_home/admin_logs/MIGRATION.md`

**Interfaces:**
- Consumes: `resolve_logging_target()` and `OSSearch.search_raw()`.
- Produces: `ParsedLogQuery`, `parse_log_query(params)`,
  `item_from_hit(hit)`, `response_from_result`, pure mock search, and
  office `query_logs(params)`.

- [ ] **Step 1: Write failing shared-query and office-adapter tests**

Move current parser behavior into tests that import the new module:

```python
def test_parse_log_query_keeps_existing_filter_contract():
    parsed = parse_log_query({
        "level": "error,warning",
        "method": "get",
        "page": "2",
        "page_size": "500",
    })
    assert parsed.page == 2
    assert parsed.page_size == 200
    assert parsed.filters["level"] == "ERROR,WARNING"
    assert {"terms": {"level": ["ERROR", "WARNING"]}} in (
        parsed.query["bool"]["filter"]
    )
```

Add office adapter tests:

```python
def test_office_queries_the_resolved_local_alias(monkeypatch):
    seen = {}

    class FakeSearch:
        def __init__(self, index):
            seen["index"] = index

        def search_raw(self, body):
            seen["body"] = body
            return {"hits": {"total": {"value": 0}, "hits": []}}

    monkeypatch.setenv("SKEWNONO_LOG_ENV", "local")
    monkeypatch.setattr(office_example, "OSSearch", FakeSearch)
    result = office_example.query_logs({})
    assert seen["index"] == "skewnono_logging_local"
    assert result["filters"]["deployment"] == "local"
    assert result["filters"]["index_alias"] == "skewnono_logging_local"


def test_mock_never_constructs_opensearch(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "present")
    result = mock.query_logs({})
    assert result["filters"]["demo_mode"] is True


def test_route_returns_stable_503_without_backend_details(
    admin_client,
    monkeypatch,
):
    def fail(_params):
        raise ConnectionError("secret-internal-host:9200")

    monkeypatch.setattr(routes, "query_logs", fail)
    response = admin_client.get("/api/admin/logs")
    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "log_query_failed"
    assert "secret-internal-host" not in str(body)
```

Assert office pagination uses `from`, `size`, descending `@timestamp`,
`track_total_hits=True`, and the parsed query. Assert hit normalization keeps
the legacy `request_path` fallback and full raw source.

- [ ] **Step 2: Run the new admin-log tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest \
  back_dev_home/admin_logs/tests/test_office_template.py \
  back_dev_home/admin_logs/tests/test_contract.py -q
```

Expected: collection failure for `query.py`, office stub failure, and mock
still selecting OpenSearch when credentials exist.

- [ ] **Step 3: Extract parser and hit normalization without changing the HTTP contract**

Create:

```python
@dataclass(frozen=True)
class ParsedLogQuery:
    query: dict[str, Any]
    filters: dict[str, Any]
    page: int
    page_size: int


def parse_log_query(params: Mapping[str, Any]) -> ParsedLogQuery:
    from_value, to_value = _read_time_range(params)
    page = max(1, _read_int(params, "page", 1))
    page_size = max(
        1,
        min(MAX_PAGE_SIZE, _read_int(params, "page_size", DEFAULT_PAGE_SIZE)),
    )
    query, filters = _build_filter_query(params, from_value, to_value)
    return ParsedLogQuery(
        query=query,
        filters=filters,
        page=page,
        page_size=page_size,
    )


def item_from_hit(hit: dict[str, Any]) -> LogItem:
    source = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
    return {
        "id": str(hit.get("_id", "")),
        "index": str(hit.get("_index", "")),
        "timestamp": source.get("@timestamp"),
        "level": source.get("level"),
        "event": source.get("event"),
        "logger": source.get("logger"),
        "user_id": source.get("user_id"),
        "method": source.get("method"),
        "path": source.get("path") or source.get("request_path"),
        "status": source.get("status"),
        "latency_ms": source.get("latency_ms"),
        "feature": source.get("feature"),
        "message": source.get("message"),
        "exception": (
            source.get("exception")
            if isinstance(source.get("exception"), dict)
            else None
        ),
        "raw": dict(source),
    }
```

Move `_read_str`, `_read_int`, `_read_time_range`, `_split_csv`,
`_total_from_response`, and the UTC timestamp helpers into this module. Rename
the existing `_build_query` body to `_build_filter_query(params, from_value,
to_value)`: remove page parsing from that helper, preserve every current
level/event/method/user/feature/path/status/text-search clause, and return
only `(query, applied_filters)`. This keeps the current validation messages,
defaults, filter keys, and query clauses exactly unchanged.

Add:

```python
def response_from_result(
    result: dict[str, Any],
    parsed: ParsedLogQuery,
    *,
    extra_filters: Mapping[str, Any] | None = None,
) -> LogQueryResponse:
```

It stamps UTC `generated_at`, merges `extra_filters`, and maps only dictionary
hits.

- [ ] **Step 4: Make mock provider deterministic and network-free**

Keep `_demo_source` and `_matches_demo` in `providers/mock.py`. Remove `os`,
`is_cloud`, `INDEX_ALIAS` runtime switching, `OPENSEARCH_PASSWORD`, and
`OSSearch`. `query_logs(params)` always:

```python
parsed = parse_log_query(params)
filters = {**parsed.filters, "demo_mode": True}
rows = [row for row in _demo_source(_utc_now()) if _matches_demo(row, filters)]
```

Apply pagination and pass synthetic hits through `item_from_hit`. Set demo
index names to `skewnono_logging_local-demo` so the label cannot be mistaken
for production.

- [ ] **Step 5: Implement the office adapter with the resolved alias**

```python
from ops_store import OSSearch

from back_dev_home._logging.target import resolve_logging_target
from back_dev_home.admin_logs.query import (
    parse_log_query,
    response_from_result,
)


def query_logs(params):
    target = resolve_logging_target()
    parsed = parse_log_query(params)
    body = {
        "from": (parsed.page - 1) * parsed.page_size,
        "size": parsed.page_size,
        "track_total_hits": True,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": parsed.query,
    }
    result = OSSearch(index=target.alias).search_raw(body)
    return response_from_result(
        result,
        parsed,
        extra_filters={
            "deployment": target.deployment,
            "index_alias": target.alias,
        },
    )
```

Do not catch OpenSearch or configuration exceptions here; the existing route
turns them into `503 log_query_failed`. Change that route's message to the
stable `Could not query OpenSearch logs`; keep the exception only in
`logger.exception`, never in the JSON body.

- [ ] **Step 6: Update admin-log migration and contract guidance**

Document:

- mock is always demo and office is always OpenSearch;
- `SKEWNONO_LOG_ENV` selects the local/production alias;
- there is no credential-based or `is_cloud()` fallback;
- `ops_index_mgmt/skewnono_logging.py --environment all` provisions storage;
- the route is still admin-gated and returns 400/503 at the route layer;
- office copy and contract test commands.

Remove the stale contract-test explanation that mock may query the real index.

- [ ] **Step 7: Run admin-log tests**

Run:

```bash
.venv/bin/python -m pytest back_dev_home/admin_logs -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

```bash
git add \
  back_dev_home/admin_logs/query.py \
  back_dev_home/admin_logs/providers/mock.py \
  back_dev_home/admin_logs/providers/office_example.py \
  back_dev_home/admin_logs/routes.py \
  back_dev_home/admin_logs/tests/test_contract.py \
  back_dev_home/admin_logs/tests/test_office_template.py \
  back_dev_home/admin_logs/MIGRATION.md
git commit -m "feat(admin-logs): query configured OpenSearch logging alias"
```

---

### Task 7: Surface Availability, Correct UI Semantics, and Office Runbook

**Files:**
- Create: `front-dev-home/app/utils/operationalDataError.ts`
- Create: `front-dev-home/app/utils/operationalDataError.test.ts`
- Modify: `front-dev-home/app/pages/activity.vue`
- Modify: `front-dev-home/app/pages/admin/logs.vue`
- Modify: `back_dev_home/.env.example`
- Modify: `docs/api-contracts/activity.yaml`
- Modify: `docs/api-contracts/usage-events.yaml`
- Modify: `docs/back-end/office-data-adapters.md`
- Modify: `docs/office-migration/STATUS.md`

**Interfaces:**
- Consumes: backend 403/503 error bodies and admin-log response
  `filters.index_alias`.
- Produces: `operationalDataErrorMessage(error, fallback)`, explicit
  unavailable UI, correct FAB active-user labeling, and the office provisioning
  runbook.

- [ ] **Step 1: Write failing pure frontend error-copy tests**

```typescript
import assert from 'node:assert/strict'
import test from 'node:test'

import { operationalDataErrorMessage } from './operationalDataError.ts'

test('maps OpenSearch 503 to a stable unavailable message', () => {
  assert.equal(
    operationalDataErrorMessage(
      {
        statusCode: 503,
        data: { error: { code: 'activity_query_failed' } }
      },
      'fallback'
    ),
    'OpenSearch 로그를 일시적으로 조회할 수 없습니다. 잠시 후 다시 시도해 주세요.'
  )
})

test('maps admin forbidden without exposing a raw FetchError', () => {
  assert.equal(
    operationalDataErrorMessage(
      { statusCode: 403, data: { error: { code: 'forbidden' } } },
      'fallback'
    ),
    '관리자만 접근할 수 있는 페이지입니다.'
  )
})

test('uses the supplied fallback for unrelated failures', () => {
  assert.equal(
    operationalDataErrorMessage(new Error('network'), '조회에 실패했습니다.'),
    '조회에 실패했습니다.'
  )
})
```

- [ ] **Step 2: Run the test and verify the utility is missing**

Run:

```bash
cd front-dev-home
node --test app/utils/operationalDataError.test.ts
```

Expected: module-not-found failure for `operationalDataError.ts`.

- [ ] **Step 3: Implement the pure error normalizer**

```typescript
type ErrorShape = {
  statusCode?: number
  data?: {
    error?: { code?: string }
    data?: { error?: { code?: string } }
  }
}

export const operationalDataErrorMessage = (
  error: unknown,
  fallback: string
): string => {
  const value = error as ErrorShape | null
  const code = value?.data?.error?.code ?? value?.data?.data?.error?.code
  if (value?.statusCode === 403 || code === 'forbidden') {
    return '관리자만 접근할 수 있는 페이지입니다.'
  }
  if (
    value?.statusCode === 503
    || code === 'activity_query_failed'
    || code === 'log_query_failed'
  ) {
    return 'OpenSearch 로그를 일시적으로 조회할 수 없습니다. 잠시 후 다시 시도해 주세요.'
  }
  return fallback
}
```

- [ ] **Step 4: Update activity and admin-log UI without adding a Vue test harness**

In `activity.vue`, use the helper in `loadError` and keep the existing retry
action. Change summary hints to trailing-window language:

```typescript
hint: '최근 7일 활동한 사용자'
hint: '최근 30일 활동한 사용자'
```

In each FAB selector row, label the number so it cannot be read as raw
requests:

```vue
<span class="tabular-nums text-xs shrink-0 opacity-80">
  활성 {{ row.total.toLocaleString() }}명
</span>
```

Keep page bars as feature-request counts.

In `admin/logs.vue`:

- change the title from `Production Logs` to `운영 로그`;
- replace hardcoded `skewnono_logging` with
  `logs?.filters?.index_alias ?? 'OpenSearch logging'`;
- keep the demo badge;
- replace page-local 403 parsing with `operationalDataErrorMessage`;
- compute `loadError` from the current `useAsyncData` error and render its
  alert before the no-results branch;
- render `일치하는 로그가 없습니다` only under
  `v-else-if="logs?.items?.length === 0"`, so a 503 can never be presented as
  an empty successful result. Leave the most recently resolved
  `logs.items` untouched if Nuxt still supplies data while a refresh error is
  present.

- [ ] **Step 5: Update environment and contract documentation**

Add this tracked template section under OpenSearch:

```dotenv
# Logging target is REQUIRED when OpenSearch logging or the activity/admin
# office adapters are enabled.
# Office PC localhost:
# SKEWNONO_LOG_ENV=local
# Company production cloud:
# SKEWNONO_LOG_ENV=production
# Emergency write kill switch; readers still report 503 if storage is down.
# OPENSEARCH_LOGGING_DISABLED=false
```

Rewrite `activity.yaml` to state:

- OpenSearch `skewnono_logging*` is the office source;
- UTC storage and KST day/month boundaries;
- trailing 7-day WAU and trailing 30-day MAU;
- entry plus feature for active users;
- feature only for rankings;
- retained-window `first_seen`;
- `/activity/fabs`, distinct active-user `total`, multi-FAB behavior, and
  `"미지정"`;
- 503 `activity_query_failed`;
- no Redis or mock fallback in office mode.

Rewrite `usage-events.yaml` as the canonical logging document contract:

```yaml
storage:
  local_alias: skewnono_logging_local
  production_alias: skewnono_logging
  local_retention: 30d after rollover
  production_retention: 365d after rollover
writer: back_dev_home/_logging/opensearch_handler.py via ops_store.OSDoc
readers:
  - back_dev_home/activity/providers/opensearch_reader.py
  - back_dev_home/admin_logs/providers/office_example.py
```

List every mapped field from the approved design and the exact activity
classification precedence. Remove the obsolete `usage_events` monthly index,
Redis counters, 13-month retention, `is_cloud()` writer, and fallback notes.

- [ ] **Step 6: Update the office runbook and migration status**

Document the only cluster-changing command:

```bash
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all \
  --dry-run
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all
```

State that both commands run only on the company network, the first is
read-only, and the second is idempotent but cluster-mutating. Add checks for:

```text
skewnono_logging_local-000001 → skewnono_logging_local
skewnono_logging-000001       → skewnono_logging
```

In `docs/office-migration/STATUS.md`, set `activity` and `admin_logs` to
`구현완료` with verification date `-`. Do not mark them `office` until the
company-cluster smoke checks pass.

- [ ] **Step 7: Run frontend, documentation, and complete backend gates**

Run:

```bash
cd front-dev-home
npm test
npm run typecheck
npm run lint
```

Expected: all new/affected frontend tests pass. If lint reports pre-existing
errors in untouched files, record the exact files and verify no changed file
appears in the report; do not suppress rules.

Then run from the repository root:

```bash
.venv/bin/python -m pytest tests back_dev_home -q
.venv/bin/python -m ruff check back_dev_home tests
npm run lint:md
git diff --check
```

Expected: backend tests pass, ruff passes for its configured scope, Markdown
reports 0 errors, and diff check is silent.

- [ ] **Step 8: Verify exact change scope**

Run:

```bash
git status --short
git diff --stat
git diff -- .remember/today-2026-07-27.md
```

Expected: `.remember/today-2026-07-27.md` still contains only the user's
pre-existing change and is neither staged nor modified by this work.

- [ ] **Step 9: Commit Task 7**

```bash
git add \
  front-dev-home/app/utils/operationalDataError.ts \
  front-dev-home/app/utils/operationalDataError.test.ts \
  front-dev-home/app/pages/activity.vue \
  front-dev-home/app/pages/admin/logs.vue \
  back_dev_home/.env.example \
  docs/api-contracts/activity.yaml \
  docs/api-contracts/usage-events.yaml \
  docs/back-end/office-data-adapters.md \
  docs/office-migration/STATUS.md
git commit -m "feat(logging): surface availability and office setup"
```

## Office Execution After Implementation

These steps are intentionally not part of automated implementation because
they require the company network and mutate the shared cluster.

1. Set `OPENSEARCH_*` credentials in the office environment.
2. Run the `--environment all --dry-run` command and inspect both policy,
   template, mapping, initial-index, and mapping-update requests.
3. Confirm the installed OpenSearch ISM plugin accepts
   `min_rollover_age`.
4. Run `--environment all` once.
5. Copy tracked adapters:

   ```bash
   cp back_dev_home/activity/providers/office_example.py \
     back_dev_home/activity/providers/office.py
   cp back_dev_home/admin_logs/providers/office_example.py \
     back_dev_home/admin_logs/providers/office.py
   ```

6. Set:

   ```dotenv
   SKEWNONO_ACTIVITY_PROVIDER=office
   SKEWNONO_ADMIN_LOGS_PROVIDER=office
   SKEWNONO_LOG_ENV=local
   ```

   Leave unrelated feature-provider settings unchanged; these overrides move
   only the two log-backed readers.

7. Run:

   ```bash
   SKEWNONO_ACTIVITY_PROVIDER=office \
     .venv/bin/python -m pytest back_dev_home/activity -q
   SKEWNONO_ADMIN_LOGS_PROVIDER=office \
     .venv/bin/python -m pytest back_dev_home/admin_logs -q
   ```

8. Start Flask, make one sem-list entry request and one feature request with
   `fab_name=M14`, and verify both appear only in
   `skewnono_logging_local`.
9. Verify `/activity` counts the user as active, excludes `sem_list` from top
   features, and reports M14 FAB activity.
10. Verify `/admin/logs` displays the local alias, both request documents, and
    no unredacted secret query values.
11. For production deployment, change only `SKEWNONO_LOG_ENV=production`,
    keep the same `OPENSEARCH_*` cluster, and verify smoke requests enter only
    `skewnono_logging`.
12. Inspect ISM explain output for both aliases, then change the two migration
    status rows from `구현완료` to `office` with the actual verification date.
