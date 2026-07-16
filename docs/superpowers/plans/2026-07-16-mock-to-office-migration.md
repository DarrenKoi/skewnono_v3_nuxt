# Mock→Office Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 19 data features under `back_dev_home/` switchable mock↔office via `SKEWNONO_<FEATURE>_PROVIDER` env vars, gated by provider-independent contract tests, with a colocated `MIGRATION.md` GLM prompt per feature.

**Architecture:** Cut a provider seam per feature (`data.py` thin switch → `providers/mock.py` verbatim-moved code + `providers/office.py` stub), validate response shapes with one shared TypedDict validator (`_core/contract_check.py`), and prove zero behavior change with a temporary parity-snapshot harness. Spec: `docs/superpowers/specs/2026-07-16-mock-to-office-migration-design.md`.

**Tech Stack:** Python 3.14, Flask, pytest (`.venv/bin/pytest`), TypedDict-based contracts. No new dependencies.

## Global Constraints

- Mock behavior must not change: `providers/mock.py` is the old `data.py` moved verbatim (imports fixed only). Parity harness must stay green after every seam cut.
- `routes.py` never changes in restructure tasks (it already imports only from `.data`).
- Env names follow the existing bare convention from `ebeam/hitachi/*`: `get_data_provider("activity")` → `SKEWNONO_ACTIVITY_PROVIDER` (NOT `ebeam_`-prefixed; the five existing hitachi features already use bare `skew`, `storage`, etc.).
- Contract tests import from `<feature>.data` (the switch), never `providers.mock` — the active env var decides the provider under test.
- Validator policy: extra dict keys allowed; missing required keys / wrong types fail with full path.
- `MIGRATION.md` files are English; `docs/office-migration/STATUS.md` is Korean (`~입니다` style, MD060 compact tables).
- Run `npm run lint:md` after creating/editing any Markdown; new files must be clean (pre-existing errors in old docs are not in scope).
- Run all tests as `.venv/bin/pytest back_dev_home` from the repo root.
- Commit per task as written; do NOT push.

---

### Task 1: Parity snapshot harness (temporary scaffolding)

**Files:**
- Create: `back_dev_home/_parity_snapshot/__init__.py` (empty)
- Create: `back_dev_home/_parity_snapshot/endpoints.py`
- Create: `back_dev_home/_parity_snapshot/capture.py`
- Create: `back_dev_home/_parity_snapshot/test_parity.py`
- Create: `back_dev_home/_parity_snapshot/golden/` (generated JSON, committed)

**Interfaces:**
- Produces: `golden/*.json` snapshots + `test_parity.py`, used by every restructure task (Tasks 3–12) as the "nothing changed" gate. Deleted in Task 17.

- [ ] **Step 1: Print the real URL map to finalize the endpoint list**

```bash
.venv/bin/python -c "
from back_dev_home import create_app
app = create_app()
for r in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if 'GET' in r.methods:
        print(r.rule)
"
```

Note the concrete `tool_slug` values (e.g. `cdsem`, `hvsem`) that the `ebeam/hitachi` blueprints register under, and the exact prefixes of the 10 target features' GET routes.

- [ ] **Step 2: Write the endpoint list**

`back_dev_home/_parity_snapshot/endpoints.py` — extend the list below with the slug-resolved `pm-planning` / `recipe-search` / `lateral` routes found in Step 1 (one entry per registered slug). Parameterized detail routes (e.g. `/activity/users/<user_id>`) are covered indirectly by the contract tests; skip them here.

```python
"""Curated GET endpoints pinned during the provider-seam refactor.

TEMPORARY scaffolding - delete this whole folder after the migration lands
(spec section 9). Parity means identical status+body before and after a seam
cut, so non-200 responses are still valid pins.

Mocks that embed wall-clock timestamps drift across days: re-run capture.py
immediately before starting each seam cut, in the same session.
"""

ENDPOINTS: list[str] = [
    "/api/activity/me",
    "/api/activity/summary",
    "/api/activity/fabs",
    "/api/activity/users",
    "/api/admin/logs",
    "/api/admin/access",
    "/api/account/api-tokens",
    "/api/announcements",
    "/api/health/services",
    "/api/cdsem/device-statistics/r3-device-grp",
    "/api/cdsem/device-statistics/device-desc",
    "/api/cdsem/device-statistics/recipe-statistics",
    "/api/cdsem/device-statistics/recipe-params",
    "/api/cdsem/device-statistics/rules",
    "/api/cdsem/device-statistics/recipe-trend",
    # + slug-resolved routes from Step 1, e.g.:
    # "/api/cdsem/pm-planning/fleet",
    # "/api/cdsem/recipe-search/recipes",
    # "/api/cdsem/recipe-search/lateral",
]
```

- [ ] **Step 3: Write the capture script**

`back_dev_home/_parity_snapshot/capture.py`:

```python
"""Capture golden responses. Run BEFORE cutting a seam:

    .venv/bin/python -m back_dev_home._parity_snapshot.capture
"""

import json
import random
from pathlib import Path

GOLDEN = Path(__file__).parent / "golden"


def slug(path: str) -> str:
    return path.strip("/").replace("/", "__")


def make_client():
    random.seed(20260716)  # before create_app: pins import-time mock generation
    from back_dev_home import create_app

    app = create_app()
    app.testing = True
    client = app.test_client()
    client.set_cookie("LASTUSER", "parity-runner")
    return client


def main() -> None:
    from back_dev_home._parity_snapshot.endpoints import ENDPOINTS

    GOLDEN.mkdir(exist_ok=True)
    client = make_client()
    for path in ENDPOINTS:
        resp = client.get(path)
        body = resp.get_json(silent=True)
        if body is None:
            body = resp.get_data(as_text=True)
        payload = {"path": path, "status": resp.status_code, "body": body}
        out = GOLDEN / f"{slug(path)}.json"
        out.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )
        print(f"{resp.status_code} {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write the comparison test**

`back_dev_home/_parity_snapshot/test_parity.py`:

```python
import json
from pathlib import Path

import pytest

from back_dev_home._parity_snapshot.capture import GOLDEN, make_client, slug
from back_dev_home._parity_snapshot.endpoints import ENDPOINTS


@pytest.fixture(scope="module")
def client():
    return make_client()


@pytest.mark.parametrize("path", ENDPOINTS, ids=slug)
def test_endpoint_unchanged(client, path):
    golden_file = GOLDEN / f"{slug(path)}.json"
    assert golden_file.exists(), f"no golden for {path}; run capture.py first"
    golden = json.loads(golden_file.read_text())
    resp = client.get(path)
    body = resp.get_json(silent=True)
    if body is None:
        body = resp.get_data(as_text=True)
    assert resp.status_code == golden["status"]
    assert body == golden["body"]
```

- [ ] **Step 5: Capture goldens and verify self-parity**

```bash
.venv/bin/python -m back_dev_home._parity_snapshot.capture
.venv/bin/pytest back_dev_home/_parity_snapshot -q
```

Expected: all endpoints PASS. If an endpoint fails against its own fresh capture, that mock is non-deterministic across processes — find the source (`grep -n "random\|now()" back_dev_home/<feature>/data.py`) and either pin it inside `make_client()` (additional seed) or, for wall-clock drift, note it in `endpoints.py` and rely on same-session re-capture.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/_parity_snapshot
git commit -m "test(parity): temporary golden-response harness for provider-seam refactor"
```

---

### Task 2: Shared contract validator `_core/contract_check.py`

**Files:**
- Create: `back_dev_home/_core/__init__.py` (empty, if missing)
- Create: `back_dev_home/_core/contract_check.py`
- Create: `back_dev_home/_core/tests/__init__.py` (empty)
- Test: `back_dev_home/_core/tests/test_contract_check.py`

**Interfaces:**
- Produces: `assert_matches(value, contract, path="$") -> None` raising `ContractViolation` (subclass of `AssertionError`). Every feature contract test (Tasks 3–15) imports `from back_dev_home._core.contract_check import assert_matches`.

- [ ] **Step 1: Write the failing tests**

`back_dev_home/_core/tests/test_contract_check.py`:

```python
from typing import Literal, NotRequired, TypedDict

import pytest

from back_dev_home._core.contract_check import ContractViolation, assert_matches


class Row(TypedDict):
    eqp_id: str
    version: int
    available: Literal["On", "Off"]
    note: NotRequired[str]


class Nested(TypedDict):
    rows: list[Row]
    total: int


GOOD_ROW: Row = {"eqp_id": "EQ-01", "version": 3, "available": "On"}


def test_valid_payload_passes():
    assert_matches(GOOD_ROW, Row)


def test_extra_keys_are_allowed():
    assert_matches({**GOOD_ROW, "office_only_field": 123}, Row)


def test_missing_required_key_fails_with_path():
    with pytest.raises(ContractViolation, match=r"\$\.version: required key missing"):
        assert_matches({"eqp_id": "EQ-01", "available": "On"}, Row)


def test_wrong_type_fails_with_path():
    with pytest.raises(ContractViolation, match=r"\$\.version: expected int"):
        assert_matches({**GOOD_ROW, "version": "3"}, Row)


def test_bad_literal_fails():
    with pytest.raises(ContractViolation, match=r"\$\.available"):
        assert_matches({**GOOD_ROW, "available": "Maybe"}, Row)


def test_not_required_key_checked_when_present():
    with pytest.raises(ContractViolation, match=r"\$\.note: expected str"):
        assert_matches({**GOOD_ROW, "note": 42}, Row)


def test_nested_list_paths():
    bad = {"rows": [GOOD_ROW, {"eqp_id": 7, "version": 1, "available": "On"}], "total": 2}
    with pytest.raises(ContractViolation, match=r"\$\.rows\[1\]\.eqp_id: expected str"):
        assert_matches(bad, Nested)


def test_optional_none_passes():
    assert_matches(None, str | None)
    assert_matches("x", str | None)


def test_union_no_arm_fails():
    with pytest.raises(ContractViolation, match=r"no union arm matched"):
        assert_matches(3.5, str | int)


def test_bool_is_not_int():
    with pytest.raises(ContractViolation, match=r"expected int"):
        assert_matches({**GOOD_ROW, "version": True}, Row)


def test_int_accepted_for_float():
    class P(TypedDict):
        value: float

    assert_matches({"value": 3}, P)


def test_plain_dict_value_type_checked():
    with pytest.raises(ContractViolation, match=r"\$\['b'\]: expected int"):
        assert_matches({"a": 1, "b": "x"}, dict[str, int])


def test_non_dict_for_typeddict_fails():
    with pytest.raises(ContractViolation, match=r"\$: expected Row"):
        assert_matches(["not", "a", "dict"], Row)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest back_dev_home/_core -q
```

Expected: FAIL — `ModuleNotFoundError: back_dev_home._core.contract_check`.

- [ ] **Step 3: Write the validator**

`back_dev_home/_core/contract_check.py`:

```python
"""Structural validation of provider payloads against TypedDict contracts.

Shared by every feature's tests/test_contract.py (spec section 4). Policy:
extra dict keys are ALLOWED (office sources may return more fields; the
frontend ignores them). Missing required keys or wrong types FAIL with the
full path to the offending value, so the office LLM can self-correct from
pytest output alone.
"""

from __future__ import annotations

import types
import typing
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints


class ContractViolation(AssertionError):
    """A payload does not structurally match its contract."""


def assert_matches(value: Any, contract: Any, path: str = "$") -> None:
    origin = get_origin(contract)

    if contract is Any:
        return
    if contract is None or contract is type(None):
        if value is not None:
            _fail(path, "None", value)
    elif typing.is_typeddict(contract):
        _check_typeddict(value, contract, path)
    elif origin in (Union, types.UnionType):
        _check_union(value, contract, path)
    elif origin is Literal:
        if value not in get_args(contract):
            _fail(path, f"one of {get_args(contract)!r}", value)
    elif origin is list:
        if not isinstance(value, list):
            _fail(path, "list", value)
        item_type = (get_args(contract) or (Any,))[0]
        for i, item in enumerate(value):
            assert_matches(item, item_type, f"{path}[{i}]")
    elif origin is dict:
        if not isinstance(value, dict):
            _fail(path, "dict", value)
        key_type, value_type = get_args(contract) or (Any, Any)
        for key, item in value.items():
            assert_matches(key, key_type, f"{path} key {key!r}")
            assert_matches(item, value_type, f"{path}[{key!r}]")
    elif isinstance(contract, type):
        _check_scalar(value, contract, path)
    else:
        raise TypeError(f"Unsupported contract annotation at {path}: {contract!r}")


def _check_typeddict(value: Any, contract: Any, path: str) -> None:
    if not isinstance(value, dict):
        _fail(path, contract.__name__, value)
    hints = get_type_hints(contract)
    for key in contract.__required_keys__:
        if key not in value:
            raise ContractViolation(
                f"{path}.{key}: required key missing ({contract.__name__})"
            )
        assert_matches(value[key], hints[key], f"{path}.{key}")
    for key in contract.__optional_keys__:
        if key in value:
            assert_matches(value[key], hints[key], f"{path}.{key}")
    # Extra keys: allowed by policy.


def _check_union(value: Any, contract: Any, path: str) -> None:
    errors: list[str] = []
    for arm in get_args(contract):
        try:
            assert_matches(value, arm, path)
            return
        except ContractViolation as exc:
            errors.append(str(exc))
    raise ContractViolation(
        f"{path}: no union arm matched {type(value).__name__} — " + " | ".join(errors)
    )


def _check_scalar(value: Any, contract: type, path: str) -> None:
    if contract is int:
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(path, "int", value)
    elif contract is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(path, "float", value)
    elif not isinstance(value, contract):
        _fail(path, contract.__name__, value)


def _fail(path: str, expected: str, value: Any) -> None:
    shown = repr(value)
    if len(shown) > 120:
        shown = shown[:117] + "..."
    raise ContractViolation(
        f"{path}: expected {expected}, got {type(value).__name__} ({shown})"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest back_dev_home/_core -q
```

Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_core
git commit -m "feat(core): shared TypedDict contract validator for provider gates"
```

---

### Task 3: Restructure `activity` (exemplar)

**Files:**
- Create: `back_dev_home/activity/providers/__init__.py` (empty)
- Create: `back_dev_home/activity/providers/mock.py` (git mv from `data.py`)
- Create: `back_dev_home/activity/providers/office.py`
- Create: `back_dev_home/activity/contracts.py`
- Create: `back_dev_home/activity/MIGRATION.md`
- Create: `back_dev_home/activity/tests/__init__.py` (empty)
- Test: `back_dev_home/activity/tests/test_contract.py`
- Modify: `back_dev_home/activity/data.py` (rewritten as thin switch)

**Interfaces:**
- Consumes: `assert_matches` from Task 2, parity harness from Task 1.
- Produces: `activity.data` keeps exporting `get_me(user_id)`, `get_summary()`, `get_fab_page_usage()`, `get_users_list()`, `get_user_history(user_id)`, `is_recordable(user_id, path, status)`, `record_request(...)`, `seed_demo_users(...)` — external importers are `routes.py`, `_logging/activity.py` (is_recordable, record_request), and `back_dev_home/__init__.py` (seed_demo_users). Signatures unchanged.

- [ ] **Step 1: Re-capture parity goldens (same session)**

```bash
.venv/bin/python -m back_dev_home._parity_snapshot.capture && .venv/bin/pytest back_dev_home/_parity_snapshot -q
```

Expected: PASS (fresh goldens self-consistent).

- [ ] **Step 2: Cut the seam**

```bash
mkdir -p back_dev_home/activity/providers back_dev_home/activity/tests
touch back_dev_home/activity/providers/__init__.py back_dev_home/activity/tests/__init__.py
git mv back_dev_home/activity/data.py back_dev_home/activity/providers/mock.py
```

Then fix relative imports inside `providers/mock.py` (module moved one level deeper): change any `from ..` to `from ...` and `from .` to `from ..`. Check the file header — `activity/data.py` imports stdlib + TypedDict only, so likely no changes; verify with:

```bash
.venv/bin/python -c "import back_dev_home.activity.providers.mock"
```

- [ ] **Step 3: Write the new thin switch `data.py`**

`back_dev_home/activity/data.py` (copy each delegating `def` line's signature exactly from `providers/mock.py`; the list of public symbols is fixed by the Produces block above):

```python
"""SWAP SURFACE for activity tracking.

Routes, _logging middleware, and the app factory import only this module.
The selected adapter lives in providers/mock.py or providers/office.py.
``is_recordable`` is provider-independent policy and lives here.
``seed_demo_users`` is demo seeding and always uses mock.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.activity.providers.mock import (
    is_recordable,       # pure predicate: same rule in both modes
    seed_demo_users,     # dev/demo seeding: mock-only by design
)


__all__ = [
    "get_me",
    "get_summary",
    "get_fab_page_usage",
    "get_users_list",
    "get_user_history",
    "is_recordable",
    "record_request",
    "seed_demo_users",
]


def _provider():
    if get_data_provider("activity") == "office":
        from back_dev_home.activity.providers import office
        return office
    from back_dev_home.activity.providers import mock
    return mock
```

Then append one delegating function per public symbol, copying the exact `def` line from `providers/mock.py`, e.g.:

```python
def get_me(user_id: str):
    return _provider().get_me(user_id)


def get_summary():
    return _provider().get_summary()
```

…and the same for `get_fab_page_usage`, `get_users_list`, `get_user_history`, `record_request` (copy `record_request`'s full multi-parameter signature verbatim from mock.py).

- [ ] **Step 4: Verify parity and existing suite**

```bash
.venv/bin/pytest back_dev_home/_parity_snapshot -q
.venv/bin/pytest back_dev_home -q
```

Expected: all PASS. Any diff means the seam cut changed behavior — fix before proceeding.

- [ ] **Step 5: Commit the seam cut**

```bash
git add -A back_dev_home/activity
git commit -m "refactor(activity): cut provider seam (mock code moved verbatim)"
```

- [ ] **Step 6: Extract contracts**

`activity/providers/mock.py` already defines the response TypedDicts (lines ~64–131: `FeatureCount`, `DailyCount`, `MeThisMonth`, `MeResponse`, `SummaryResponse`, `UserListRow`, `UserListResponse`, `UserHistoryResponse`, `FabPageCount`, `FabUsageRow`, `FabUsageResponse`). Move those class definitions verbatim into a new `back_dev_home/activity/contracts.py` with the docstring `"""Stable response contracts for activity endpoints."""`, and in `providers/mock.py` replace them with:

```python
from back_dev_home.activity.contracts import (
    DailyCount,
    FabPageCount,
    FabUsageResponse,
    FabUsageRow,
    FeatureCount,
    MeResponse,
    MeThisMonth,
    SummaryResponse,
    UserHistoryResponse,
    UserListResponse,
    UserListRow,
)
```

Verify: `.venv/bin/pytest back_dev_home/_parity_snapshot -q` → PASS (parity is FULL-suite only — the activity feature records the harness's own requests, so subset runs are order-dependent).

- [ ] **Step 7: Write the office stub**

`back_dev_home/activity/providers/office.py`:

```python
"""Office adapter for activity tracking — NOT CONNECTED YET.

Implement every function listed in activity/MIGRATION.md against the office
OpenSearch activity index. Normalize results to activity/contracts.py shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The activity office adapter has not been connected yet. "
        "Set SKEWNONO_ACTIVITY_PROVIDER=mock until it is ready."
    )


def get_me(user_id):
    return _not_connected()


def get_summary():
    return _not_connected()


def get_fab_page_usage():
    return _not_connected()


def get_users_list():
    return _not_connected()


def get_user_history(user_id):
    return _not_connected()


def record_request(*args, **kwargs):
    return _not_connected()
```

- [ ] **Step 8: Write the contract test**

`back_dev_home/activity/tests/test_contract.py` (adjust the response-key access — e.g. `users["users"]` — to the real field names now visible in `contracts.py`):

```python
"""Contract gate for activity. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/activity
Office: SKEWNONO_ACTIVITY_PROVIDER=office .venv/bin/pytest back_dev_home/activity
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.activity import data
from back_dev_home.activity.contracts import (
    FabUsageResponse,
    MeResponse,
    SummaryResponse,
    UserHistoryResponse,
    UserListResponse,
)


def test_summary_matches_contract():
    assert_matches(data.get_summary(), SummaryResponse)


def test_fab_page_usage_matches_contract():
    assert_matches(data.get_fab_page_usage(), FabUsageResponse)


def test_users_list_matches_contract():
    assert_matches(data.get_users_list(), UserListResponse)


def test_me_and_history_match_contract():
    # Derive a real user id from the active provider so this test is
    # provider-independent (office has different users than mock).
    users = data.get_users_list()["users"]
    if not users:
        pytest.skip("active provider returned no users")
    user_id = users[0]["user_id"]
    assert_matches(data.get_me(user_id), MeResponse)
    history = data.get_user_history(user_id)
    if history is not None:
        assert_matches(history, UserHistoryResponse)
```

- [ ] **Step 9: Run the gate both ways**

```bash
.venv/bin/pytest back_dev_home/activity -q
SKEWNONO_ACTIVITY_PROVIDER=office .venv/bin/pytest back_dev_home/activity -q 2>&1 | tail -3
```

Expected: first PASS; second fails with `NotImplementedError ... SKEWNONO_ACTIVITY_PROVIDER=mock` (proves the switch selects office).

- [ ] **Step 10: Write `MIGRATION.md`**

`back_dev_home/activity/MIGRATION.md` — fill the `Mock behavior` and `Notes` lines by reading `providers/mock.py` (sort order, date formats, empty-value behavior the frontend relies on); inline each endpoint's contract TypedDict source from `contracts.py`:

```markdown
# activity — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/activity/me

- Handler: `routes.py` → `data.get_me(user_id)` (user id from LASTUSER cookie)
- Contract: `MeResponse` — <inline the TypedDict source here>
- Mock behavior: <2-3 lines from providers/mock.py>
- Office data source: <!-- OFFICE: OpenSearch activity index name + query -->
- Notes: <semantic expectations: date format, ordering, empty handling>

## Endpoint: GET /api/activity/summary
… (same block shape for /summary, /fabs, /users, /users/<user_id>)

## Write path: record_request(...)

- Called by `_logging` middleware on every recordable request.
- Office implementation writes to the activity index; `is_recordable` policy
  lives in `data.py` and is NOT reimplemented.
- Office data source: <!-- OFFICE: index/pipeline name -->

## Verify

    SKEWNONO_ACTIVITY_PROVIDER=office .venv/bin/pytest back_dev_home/activity
```

- [ ] **Step 11: Lint and commit**

```bash
npm run lint:md 2>&1 | grep "activity/MIGRATION" || echo CLEAN
git add -A back_dev_home/activity
git commit -m "feat(activity): contract gate, office stub, GLM migration prompt"
```

---

### Task 4: Restructure `admin_logs`

**Files:**
- Create: `back_dev_home/admin_logs/providers/__init__.py`, `providers/mock.py` (git mv from `data.py`), `providers/office.py`, `contracts.py`, `MIGRATION.md`, `tests/__init__.py`
- Test: `back_dev_home/admin_logs/tests/test_contract.py`
- Modify: `back_dev_home/admin_logs/data.py`

**Interfaces:**
- Consumes: `assert_matches` (Task 2), parity harness (Task 1).
- Produces: `admin_logs.data.query_logs(...)` — signature copied verbatim from the old `data.py`; sole consumer is `routes.py` (`GET /api/admin/logs`).

Same 11-step recipe as Task 3, instantiated for `admin_logs`. Concretely:

- [ ] **Step 1: Re-capture parity, cut seam** (`git mv data.py providers/mock.py`, fix relative imports, `python -c "import back_dev_home.admin_logs.providers.mock"`)
- [ ] **Step 2: New `data.py`:**

```python
"""SWAP SURFACE for admin logs. Routes import only this module."""

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = ["query_logs"]


def _provider():
    if get_data_provider("admin_logs") == "office":
        from back_dev_home.admin_logs.providers import office
        return office
    from back_dev_home.admin_logs.providers import mock
    return mock


def query_logs(*args, **kwargs):
    return _provider().query_logs(*args, **kwargs)
```

Replace the `*args, **kwargs` with the exact parameter list copied from `providers/mock.py::query_logs` (keyword defaults included) so IDEs and GLM see the real signature.

- [ ] **Step 3: Parity + suite green** (`pytest back_dev_home/_parity_snapshot -q` — always the full parity suite, never -k subsets — then full suite). Commit `refactor(admin_logs): cut provider seam`.
- [ ] **Step 4: Derive `contracts.py`.** Inspect the shape:

```bash
.venv/bin/python -c "
import json
from back_dev_home.admin_logs.providers import mock
print(json.dumps(mock.query_logs(), indent=2, default=str)[:2000])
"
```

(If `query_logs` requires arguments, copy the defaults `routes.py` passes.) Write one TypedDict per distinct dict shape observed (response envelope + row), `total=True`, `NotRequired[...]` for keys that appear only sometimes. If `providers/mock.py` already defines TypedDicts, MOVE them instead (Task 3 Step 6 pattern).

- [ ] **Step 5: `providers/office.py` stub** — same shape as Task 3 Step 7 with `query_logs(*args, **kwargs)` and message `"Set SKEWNONO_ADMIN_LOGS_PROVIDER=mock until it is ready."`
- [ ] **Step 6: `tests/test_contract.py`:**

```python
"""Contract gate for admin_logs. Runs against the ACTIVE provider via data.py."""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.admin_logs import data
from back_dev_home.admin_logs.contracts import LogsResponse  # name per Step 4


def test_query_logs_matches_contract():
    assert_matches(data.query_logs(), LogsResponse)
```

- [ ] **Step 7: Gate both ways** (mock PASS; `SKEWNONO_ADMIN_LOGS_PROVIDER=office` → NotImplementedError).
- [ ] **Step 8: `MIGRATION.md`** — Task 3 Step 10 template with one endpoint block (`GET /api/admin/logs`, handler `routes.py` → `data.query_logs(...)`, note admin-only middleware) and verify line `SKEWNONO_ADMIN_LOGS_PROVIDER=office .venv/bin/pytest back_dev_home/admin_logs`.
- [ ] **Step 9: Lint, commit** `feat(admin_logs): contract gate, office stub, GLM migration prompt`.

---

### Task 5: Restructure `announcements`

**Files:** same layout under `back_dev_home/announcements/`; Modify `data.py`.

**Interfaces:**
- Produces: `announcements.data.get_announcements()` (signature verbatim from old `data.py`); consumer `routes.py` (`GET /api/announcements`).

Same recipe as Task 4 with substitutions:

- [ ] Seam cut → commit `refactor(announcements): cut provider seam`
- [ ] `data.py` switch: feature key `"announcements"`, delegate `get_announcements` (copy exact signature)
- [ ] Contracts derived via `mock.get_announcements()` dump → `AnnouncementsResponse` (+ row TypedDict)
- [ ] Office stub message: `SKEWNONO_ANNOUNCEMENTS_PROVIDER=mock`
- [ ] Test: `assert_matches(data.get_announcements(), AnnouncementsResponse)`
- [ ] Gate both ways; `MIGRATION.md` (endpoint `GET /api/announcements`; office source hint `<!-- OFFICE: Redis key or index -->`); lint
- [ ] Commit `feat(announcements): contract gate, office stub, GLM migration prompt`

---

### Task 6: Restructure `health`

**Files:** same layout under `back_dev_home/health/`; Modify `data.py`.

**Interfaces:**
- Produces: `health.data.get_services_health()` (signature verbatim); consumer `routes.py` (`GET /api/health/services`).

Same recipe as Task 4. Substitutions: feature key `"health"`, env `SKEWNONO_HEALTH_PROVIDER`, contract `ServicesHealthResponse`. `MIGRATION.md` note: the office implementation performs REAL probes (OpenSearch ping, Redis ping) instead of returning canned statuses — the contract fixes only the response shape, statuses may legitimately differ from mock. Commits: `refactor(health): cut provider seam`, then `feat(health): contract gate, office stub, GLM migration prompt`.

---

### Task 7: Restructure `api_tokens`

**Files:** same layout under `back_dev_home/api_tokens/`; Modify `data.py`.

**Interfaces:**
- Produces: `api_tokens.data`: `list_tokens(...)`, `create_token(...)`, `revoke_token(...)` (signatures verbatim from old `data.py`); consumer `routes.py` (GET/POST/DELETE `/api/account/api-tokens`).

Same recipe as Task 4, plus the stateful-CRUD nuance:

- [ ] Seam cut; `data.py` switch with the three delegating functions (exact signatures); parity (full suite — never -k subsets) + suite; commit `refactor(api_tokens): cut provider seam`.
- [ ] Contracts: dump `mock.list_tokens(...)` and `mock.create_token(...)` return shapes → `TokenRow`, `TokenListResponse`, `CreateTokenResponse` (create returns the secret once — keep that key `NotRequired` in `TokenRow` if absent from list output).
- [ ] Office stub (`SKEWNONO_API_TOKENS_PROVIDER=mock` message) for all three functions.
- [ ] Test — roundtrip so it is provider-safe (creates then revokes its own token):

```python
"""Contract gate for api_tokens. Runs against the ACTIVE provider via data.py."""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.api_tokens import data
from back_dev_home.api_tokens.contracts import CreateTokenResponse, TokenListResponse


def test_list_tokens_matches_contract():
    assert_matches(data.list_tokens("contract-gate-user"), TokenListResponse)


def test_create_then_revoke_roundtrip():
    created = data.create_token("contract-gate-user", "contract-gate-token")
    assert_matches(created, CreateTokenResponse)
    token_id = created["token"]["token_id"]  # adjust key names to contracts.py
    data.revoke_token("contract-gate-user", token_id)
```

(Adjust argument lists to the real signatures found in mock.py — routes.py shows how they're called.)

- [ ] Gate both ways; `MIGRATION.md` with three endpoint blocks + note "office backend is Redis (`<!-- OFFICE: key pattern -->`); revoke must be idempotent"; lint; commit `feat(api_tokens): contract gate, office stub, GLM migration prompt`.

---

### Task 8: Restructure `access_control`

**Files:** same layout under `back_dev_home/access_control/`; Modify `data.py`.

**Interfaces:**
- Produces: `access_control.data`: `list_denied(...)`, `list_exceptions(...)`, `add_exception(...)`, `remove_exception(...)` — switched; `BLOCKED_PREFIX` (constant) and `StoreUnavailableError` (exception type) re-exported unswitched. Consumer `routes.py` (GET `/api/admin/access`, POST/DELETE `/api/admin/access/exceptions`).

Same recipe as Task 7 (stateful CRUD), with one addition — the new `data.py` starts:

```python
"""SWAP SURFACE for X-ID access control."""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.access_control.providers.mock import (
    BLOCKED_PREFIX,          # policy constant: provider-independent
    StoreUnavailableError,   # error type shared by both providers
)
```

`providers/office.py` must RAISE the same `StoreUnavailableError` (imported from `providers.mock`) when Redis is down, so `routes.py` error handling keeps working — record this rule in `MIGRATION.md`. Contract test covers `list_denied` + `list_exceptions` shapes and an `add_exception`/`remove_exception` roundtrip with a synthetic user id `"contract-gate-x00000"`. Env: `SKEWNONO_ACCESS_CONTROL_PROVIDER`. Commits: `refactor(access_control): cut provider seam`, `feat(access_control): contract gate, office stub, GLM migration prompt`.

---

### Task 9: Restructure `ebeam/cdsem/device_statistics` (has external importers)

**Files:**
- Same layout under `back_dev_home/ebeam/cdsem/device_statistics/`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py:34` (import fix)

**Interfaces:**
- Produces: `device_statistics.data`: `get_r3_device_grp()`, `get_device_desc()`, `get_recipe_params(...)`, `get_weekly_trend_data(...)` + whatever else `routes.py` imports — switched. `_lot_index` stays mock-internal.
- External importers: `ebeam/hitachi/_analytics.py:74` uses `get_device_desc`/`get_r3_device_grp` via `data` (keeps working through the switch); `ebeam/hitachi/recipe_tat/providers/mock.py:34` imports the PRIVATE `_lot_index` from `data` — this import must be repointed.

Same recipe as Task 4, with two extra steps:

- [ ] **Import repoint:** in `ebeam/hitachi/recipe_tat/providers/mock.py` change

```python
from back_dev_home.ebeam.cdsem.device_statistics.data import _lot_index
```

to

```python
from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import _lot_index
```

Mock fixtures interlocking with mock fixtures is correct — `_lot_index` must NOT go through the switch (office mode would break recipe_tat's mock).

- [ ] **Full route import check:** `routes.py` has 6 GET endpoints — open it and delegate every `data` function it imports (the four listed above plus any others in its import block).

Env: `SKEWNONO_DEVICE_STATISTICS_PROVIDER`. Contracts derived per endpoint dump (Task 4 Step 4 pattern). `MIGRATION.md` gets 6 endpoint blocks. Parity: full suite only. Commits: `refactor(device_statistics): cut provider seam (repoint recipe_tat mock import)`, `feat(device_statistics): contract gate, office stub, GLM migration prompt`.

---

### Task 10: Restructure `ebeam/hitachi/pm_planning`

**Files:** same layout under `back_dev_home/ebeam/hitachi/pm_planning/`; `contracts.py` ALREADY EXISTS — keep it, do not regenerate.

**Interfaces:**
- Produces: `pm_planning.data.get_pm_planning_fleet(...)` (signature verbatim); consumer `routes.py` (`GET /api/<tool_slug>/pm-planning/fleet`).

Same recipe as Task 4, except Step 4 (contracts) is: verify the existing `contracts.py` covers the response of `get_pm_planning_fleet` (dump the mock output and cross-check field names; extend only if a returned key is missing). Env: `SKEWNONO_PM_PLANNING_PROVIDER`. Contract test calls `data.get_pm_planning_fleet()` with the default args `routes.py` uses (open routes.py, copy the call). `MIGRATION.md` notes the route is slug-parameterized. Commits: `refactor(pm_planning): cut provider seam`, `feat(pm_planning): contract gate, office stub, GLM migration prompt`.

---

### Task 11: Restructure `ebeam/hitachi/recipe_search`

**Files:** same layout under `back_dev_home/ebeam/hitachi/recipe_search/` (452-line `data.py` moves verbatim).

**Interfaces:**
- Produces: `recipe_search.data`: `get_recipe_catalog(...)`, `get_recipe_open_data(...)`, `get_recipe_compare_data(...)` — switched; `ToolType` re-exported unswitched (type alias). Consumer `routes.py` (GET `recipes`, GET `recipe-detail`, POST `compare`).

Same recipe as Task 4. `data.py` re-exports `ToolType` from `providers.mock` the way `meas_hist/data.py` re-exports its types. Contracts: dump all three functions' outputs (catalog first; use a recipe name from the catalog as the arg for `get_recipe_open_data` — same derive-args-from-prior-call pattern as Task 3 Step 8). Env: `SKEWNONO_RECIPE_SEARCH_PROVIDER`. `MIGRATION.md`: 3 endpoint blocks; note POST `compare`'s request body comes from the frontend compare picker. Commits: `refactor(recipe_search): cut provider seam`, `feat(recipe_search): contract gate, office stub, GLM migration prompt`.

---

### Task 12: Restructure `ebeam/lateral_recipe`

**Files:** same layout under `back_dev_home/ebeam/lateral_recipe/`.

**Interfaces:**
- Produces: `lateral_recipe.data.get_lateral_recipe(...)` (signature verbatim); consumer `routes.py` (`GET /api/<tool_slug>/recipe-search/lateral`).

Same recipe as Task 4. Env: `SKEWNONO_LATERAL_RECIPE_PROVIDER`. Contract `LateralRecipeResponse` derived from mock dump (args copied from routes.py call). Commits: `refactor(lateral_recipe): cut provider seam`, `feat(lateral_recipe): contract gate, office stub, GLM migration prompt`.

---

### Task 13: Backfill `sem_list`, `hardware`, `skew`, `storage` (contracts exist)

**Files:**
- Create: `tests/__init__.py` + `tests/test_contract.py` + `MIGRATION.md` in each of: `back_dev_home/sem_list/`, `back_dev_home/ebeam/hitachi/hardware/`, `back_dev_home/ebeam/hitachi/skew/`, `back_dev_home/ebeam/hitachi/storage/`

**Interfaces:**
- Consumes existing seams: `sem_list.data.get_sem_list() -> list[SemListRow]`; `hardware.data.get_hardware_service(...)`; `skew.data.get_skew_check(...)`; `storage.data.get_storage(...)` + `get_ppid_unavailable(...)`. Contracts already in each feature's `contracts.py`.

- [ ] **Step 1: sem_list test** — `back_dev_home/sem_list/tests/test_contract.py`:

```python
"""Contract gate for sem_list. Runs against the ACTIVE provider via data.py."""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.sem_list import data
from back_dev_home.sem_list.contracts import SemListRow


def test_sem_list_matches_contract():
    rows = data.get_sem_list()
    assert rows, "sem list must not be empty"
    assert_matches(rows, list[SemListRow])
```

- [ ] **Step 2: hardware / skew / storage tests** — same file shape; call each `data` function with the default arguments its `routes.py` passes (open each routes.py and copy the call), asserting against the existing `contracts.py` types. `storage` gets two test functions (`get_storage`, `get_ppid_unavailable`).
- [ ] **Step 3: Run** `.venv/bin/pytest back_dev_home/sem_list back_dev_home/ebeam/hitachi/hardware back_dev_home/ebeam/hitachi/skew back_dev_home/ebeam/hitachi/storage -q` → PASS.
- [ ] **Step 4: MIGRATION.md × 4** — Task 3 Step 10 template; endpoints from each `routes.py`; env names already wired: `SKEWNONO_SEM_LIST_PROVIDER`, `SKEWNONO_HARDWARE_PROVIDER`, `SKEWNONO_SKEW_PROVIDER`, `SKEWNONO_STORAGE_PROVIDER` (verify each `data.py`'s `get_data_provider("...")` key and use exactly that).
- [ ] **Step 5: Lint, commit** `feat(backfill): contract gates + migration prompts for sem_list, hardware, skew, storage`.

---

### Task 14: Backfill `meas_hist`, `afm`, `recipe_tat`, `fail_issue` (derive contracts)

**Files:**
- Create: `contracts.py` (meas_hist, afm, recipe_tat, fail_issue — move existing TypedDicts out of `providers/mock.py` where they exist, else derive from dumps), `tests/__init__.py`, `tests/test_contract.py`, `MIGRATION.md` in each feature folder.

**Interfaces:**
- Consumes existing seams: `meas_hist.data` (`get_meas_hist`, `find_meas_hist_by_msr`, `search_meas_hist`, `get_meas_hist_facets`); `afm.data` (`get_tools`, `list_afm_files`, `get_afm_file_detail`, `get_profile_points`, `list_user_activities`, `get_user_analytics`); `recipe_tat.data` (`get_ranking`, `get_summary`, `get_daily_trend`, `get_devices`); `fail_issue.data` (`get_summary`, `get_daily_trend`, `get_align_ranking`, `get_meas_ranking`, `get_devices`).

- [ ] **Step 1: meas_hist** — `providers/mock.py` already defines `MeasHistRow`, `MeasHistResponse`, `MeasHistSearchResponse`, `MeasHistFacetsResponse`, `ToolType` (re-exported by `data.py`). Move them to `meas_hist/contracts.py`; import back into `providers/mock.py` and `data.py` from contracts (keep `data.py`'s `__all__` unchanged). Run full suite → PASS. Test file asserts: `get_meas_hist()` → `MeasHistResponse`, `search_meas_hist()` → `MeasHistSearchResponse`, `get_meas_hist_facets()` → `MeasHistFacetsResponse`, and `find_meas_hist_by_msr(<msr from a prior search result>)` → `MeasHistRow | None`.
- [ ] **Step 2: afm, recipe_tat, fail_issue** — same: move TypedDicts from `providers/mock.py` into `contracts.py` where defined; for shapes without TypedDicts, dump the mock output (Task 4 Step 4 command pattern) and write them. Tests call each read function with args copied from routes.py defaults, derive entity args from prior calls (Task 3 Step 8 pattern).
- [ ] **Step 3: Run** the four feature suites + `back_dev_home/_parity_snapshot` + full suite → PASS (moving TypedDicts must not change behavior).
- [ ] **Step 4: MIGRATION.md × 4** with each feature's endpoint blocks from `routes.py`, verify lines using each `data.py`'s exact `get_data_provider("...")` key (`meas_hist`, `afm`, `recipe_tat`, `fail_issue`).
- [ ] **Step 5: Lint, commit** `feat(backfill): contracts + gates + migration prompts for meas_hist, afm, recipe_tat, fail_issue`.

---

### Task 15: Backfill `msr_file` (provider-independent gate alongside the mock pin)

**Files:**
- Create: `back_dev_home/msr_file/contracts.py`, `back_dev_home/msr_file/MIGRATION.md`
- Create: `back_dev_home/msr_file/tests/test_contract_gate.py` (new file; existing `test_contract.py` is mock-pinned and stays untouched)

**Interfaces:**
- Consumes: `msr_file.data.get_msr_file(msr, msr_class, total_images)` and `get_msr_image(name) -> str`.

- [ ] **Step 1:** Derive `contracts.py` from `mock.get_msr_file("MSR-CONTRACT-0001", "ADI", 40)` (the existing test's synthetic args) — envelope + `exe_detail_info` + parameter-summary TypedDicts. Use `NotRequired` for the office-gated keys the existing test forbids in mock (`site_layout_hash`, `recipe_revision`, etc.) so office responses that INCLUDE them still pass the gate.
- [ ] **Step 2:** `tests/test_contract_gate.py`:

```python
"""Provider-independent contract gate for msr_file (runs via data.py).

The sibling test_contract.py intentionally pins MOCK-ONLY invariants and
imports providers.mock directly - do not merge these files.
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.msr_file import data
from back_dev_home.msr_file.contracts import MsrFileResponse


def test_msr_file_matches_contract():
    result = data.get_msr_file("MSR-CONTRACT-0001", "ADI", 40)
    assert result is not None
    assert_matches(result, MsrFileResponse)
```

- [ ] **Step 3:** Run `.venv/bin/pytest back_dev_home/msr_file -q` → all PASS (old + new).
- [ ] **Step 4:** `MIGRATION.md` — endpoint blocks from `routes.py`; explicitly instruct: "office MUST emit the canonical metadata keys that mock forbids (`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`, `sequence_timestamp`) — they unlock the layout-dependent analyses; see tests/test_contract.py docstring." Verify line: `SKEWNONO_MSR_FILE_PROVIDER=office .venv/bin/pytest back_dev_home/msr_file/tests/test_contract_gate.py` (the mock-pin test is EXCLUDED from the office gate — it asserts mock-only behavior; note the exact `get_data_provider` key from `msr_file/data.py`).
- [ ] **Step 5:** Lint, commit `feat(msr_file): provider-independent contract gate + migration prompt`.

---

### Task 16: Central status doc `docs/office-migration/STATUS.md` (Korean)

**Files:**
- Create: `docs/office-migration/STATUS.md`

**Interfaces:**
- Consumes: the final feature list, env names, and MIGRATION.md paths from Tasks 3–15.

- [ ] **Step 1:** Write the checklist. Korean, formal `~입니다` endings, MD060 compact tables. Structure:

```markdown
# Mock → Office 전환 현황

백엔드 기능별 데이터 소스 전환 체크리스트입니다. 각 기능의 전환 절차는
해당 폴더의 `MIGRATION.md`에 있으며, 계약 테스트가 통과한 뒤에만
환경변수를 전환합니다.

## 전환 절차

1. GLM이 `<기능>/MIGRATION.md`를 읽고 `providers/office.py`를 구현합니다.
2. `SKEWNONO_<기능>_PROVIDER=office .venv/bin/pytest back_dev_home/<기능>` 이 통과해야 합니다.
3. Flask 실행 환경변수에 추가하고 재시작한 뒤, 아래 표를 갱신합니다.

## 현황

| 기능 | 환경변수 | 계약 | 상태 | 검증일 |
| --- | --- | --- | --- | --- |
| activity | SKEWNONO_ACTIVITY_PROVIDER | activity/contracts.py | mock | - |
| admin_logs | SKEWNONO_ADMIN_LOGS_PROVIDER | admin_logs/contracts.py | mock | - |
| … (19개 기능 전부, Tasks 3–15에서 확정된 환경변수 이름 그대로) | | | | |
```

Every row's env name must be copied from the feature's `data.py` `get_data_provider("...")` key — no guessing.

- [ ] **Step 2:** `npm run lint:md 2>&1 | grep office-migration || echo CLEAN` → CLEAN.
- [ ] **Step 3:** Commit `docs: office migration status checklist (Korean)`.

---

### Task 17: Teardown, full verification, live check

**Files:**
- Delete: `back_dev_home/_parity_snapshot/` (entire folder)

- [ ] **Step 1: Final parity run before deletion**

```bash
.venv/bin/python -m back_dev_home._parity_snapshot.capture
.venv/bin/pytest back_dev_home -q
```

Expected: everything PASS (parity + all contract gates + pre-existing tests).

- [ ] **Step 2: Delete the harness**

```bash
git rm -r back_dev_home/_parity_snapshot
.venv/bin/pytest back_dev_home -q
```

Expected: PASS (contract tests remain the permanent safety net).

- [ ] **Step 3: Live check via the /verify skill flow** — start the Flask mock server + Nuxt, and confirm in the browser that two restructured features render unchanged (suggested: `활동` activity page and the device-statistics page, since both had their data modules moved). This follows the project's `verify` skill; screenshots to `.playwright-mcp/screenshots/`.

- [ ] **Step 4: Negative smoke of the switch**

```bash
SKEWNONO_ACTIVITY_PROVIDER=bogus .venv/bin/python -c "
from back_dev_home._runtime.data_provider import get_data_provider
try:
    get_data_provider('activity')
    raise SystemExit('FAIL: expected RuntimeError')
except RuntimeError as e:
    print('OK:', e)
"
```

Expected: `OK: Invalid data provider 'bogus' ...`.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove temporary parity harness; contract gates are the permanent net"
```

---

### Task 18: Project skill `home-to-office` (convention audit)

**Files:**
- Create: `.claude/skills/home-to-office/SKILL.md`

**Interfaces:**
- Consumes: the convention established by Tasks 2–16 (folder layout, env keys, gate commands, MIGRATION.md structure, STATUS.md rows). The skill is the convention's enforcement loop for all FUTURE feature work.

- [ ] **Step 1: Write the skill**

`.claude/skills/home-to-office/SKILL.md`:

````markdown
---
name: home-to-office
description: Audit backend features against the mock→office provider convention before conveying work to the office. Use when the user says "office check", "sync check", "convey to office", "office 준비", or before /leave-office when back_dev_home changed.
argument-hint: [feature-name … | leave empty to auto-detect from git]
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

# Office Sync Check

Audit one or more `back_dev_home/` features against the provider convention
(spec: `docs/superpowers/specs/2026-07-16-mock-to-office-migration-design.md`)
so that everything created or modified at home is office-ready: folder
structure, contracts, gates, and the GLM 5.2 prompt.

## 1. Determine scope

- If arguments name features, audit those.
- Otherwise auto-detect: `git status --porcelain` + `git diff HEAD~5 --name-only`,
  map touched files under `back_dev_home/<feature>/` to features (a route-owning
  folder = has `routes.py`). Also flag NEW route-owning folders that have no
  provider split at all.

## 2. Audit each feature (report table, one row per check)

| # | Check | How |
| --- | --- | --- |
| 1 | Folder layout | `contracts.py`, `data.py`, `MIGRATION.md`, `providers/mock.py`, `providers/office.py`, `tests/test_contract.py` all exist |
| 2 | Thin switch | `data.py` calls `get_data_provider("<key>")`; contains no data generation (no random/fixtures/loops building rows) |
| 3 | Routes discipline | `routes.py` imports only from `.data` (grep for `providers` imports — must be none) |
| 4 | Endpoint coverage | every `@bp.get/post/put/delete` in `routes.py` has a matching `## Endpoint:` block in `MIGRATION.md` |
| 5 | Contract coverage | every data function used by `routes.py` has an assert in `tests/test_contract.py`; tests import `from … import data`, never `providers.mock` (exception: mock-pin tests, e.g. msr_file) |
| 6 | Office stub honest | every public function in `providers/mock.py` that `data.py` switches exists in `providers/office.py` (implemented or `_not_connected`) |
| 7 | Placeholders intact | `MIGRATION.md` still has `<!-- OFFICE: -->` slots for anything only knowable at the office |
| 8 | STATUS row | `docs/office-migration/STATUS.md` has a row with the feature's exact `get_data_provider` key as `SKEWNONO_<KEY>_PROVIDER` |
| 9 | Gate green | `.venv/bin/pytest back_dev_home/<feature> -q` passes |
| 10 | Office switch wired | `SKEWNONO_<KEY>_PROVIDER=office .venv/bin/pytest back_dev_home/<feature> -q` fails with NotImplementedError (or passes if office is implemented) — anything else means the switch is broken |

## 3. Fix or report

- Auto-fix mechanical gaps after showing the user what's missing: create
  missing stubs/tests/MIGRATION blocks following the `activity` and `sem_list`
  exemplars (copy their file shapes exactly; derive contracts from mock output).
- NEVER auto-edit `providers/mock.py` logic or `routes.py` — report only.
- New endpoints added to an existing feature: update `contracts.py` (new
  TypedDicts), add the contract test, add the MIGRATION.md endpoint block,
  extend `providers/office.py` with the new `_not_connected` stub.
- Finish with `npm run lint:md` if any Markdown changed, and print a final
  READY / NOT READY verdict per feature with the office verify command:
  `SKEWNONO_<KEY>_PROVIDER=office .venv/bin/pytest back_dev_home/<feature>`
````

- [ ] **Step 2: Dry-run the skill checklist manually against one finished feature**

Run checks 1–10 by hand for `activity` (or `sem_list`): every check must pass, proving the checklist matches what Tasks 3–15 actually built. Any mismatch = fix the SKILL.md wording now.

- [ ] **Step 3: Lint and commit**

```bash
npm run lint:md 2>&1 | grep home-to-office || echo CLEAN
git add .claude/skills/home-to-office
git commit -m "feat(skills): home-to-office convention audit skill"
```

---

## Self-Review Notes

- Spec coverage: section 3 convention → Tasks 3–12; section 4 validator → Task 2; section 5 gates → every feature task; section 6 MIGRATION.md → Steps in Tasks 3–15; section 7 STATUS.md → Task 16; section 9 parity → Tasks 1, 17; `_auth` exclusion → not touched by any task.
- Env-name convention: this plan uses bare feature keys (existing `ebeam/hitachi` convention), superseding the spec's `ebeam_recipe_search` example — spec updated to match.
- Signatures marked "copy verbatim from mock.py" are deliberate: the seam must mirror whatever the mock defines today; inventing them in the plan risks drift.
