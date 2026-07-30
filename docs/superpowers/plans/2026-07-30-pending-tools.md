# 미연결 장비 (Firewall-Request View) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the tools present in the company-wide SEM roster but not yet reachable by skewnono, so their IPs can be handed to the IT service team as a firewall-exception request.

**Architecture:** A new `GET /api/sem-list/pending` endpoint diffs office Redis key `v3_df_sem_list` (full roster) against `v3_df_sem_avail` (reachable subset) on `eqp_id`. The existing `GET /api/sem-list` response is left byte-identical, because six other features resolve `eqp_id → eqp_ip` through it. A new root-level `/tool-roster` page fetches the diff **on demand only** and renders a `fab_name × eqp_model_cd` count matrix with a per-tool-type filter, a drill-down list, an IP-list clipboard action and CSV export.

**Tech Stack:** Flask blueprints, pandas, `back_dev_home/_runtime/office_redis.py`; Nuxt 4 + NuxtUI, `useAsyncData`, `node --test`.

**Spec:** `docs/superpowers/specs/2026-07-30-pending-tools-design.md`

## Global Constraints

- Do **not** modify `back_dev_home/sem_list/data.py`'s existing `get_sem_list()` behavior, and do not change what `GET /api/sem-list` returns. Row count stays 300.
- Never edit `providers/office.py` (gitignored copy). All office work goes in `providers/office_example.py`.
- Office DB facts land in **both** `docs/datatables/sem_list.txt` and `providers/mock.py` in the same commit (CLAUDE.md).
- Mark office-fact provenance: `user-confirmed 2026-07-30` for what the user confirmed, `OFFICE-VERIFY` for the unverified `v3_df_sem_list` column list.
- Colors from `--sk-*` tokens only, never inline hex (`DESIGN.md`).
- Markdown tables use markdownlint `MD060` `compact` style. Run `npm run lint:md` after any Markdown edit.
- Stale-arrival threshold is exactly **180 days**, defined once as a named constant.
- Pending mock fleet is exactly **14** tools; connected mock fleet is exactly **300**.
- Backend commands run from the repo root as `.venv/bin/python -m pytest`, never bare `pytest`.

## File Structure

| File | Responsibility |
| --- | --- |
| `back_dev_home/sem_list/contracts.py` | Add `PendingToolRow` TypedDict |
| `back_dev_home/sem_list/providers/mock.py` | Split generator into connected + pending; correct docstring |
| `back_dev_home/sem_list/data.py` | Add `get_pending_tools()` dispatcher |
| `back_dev_home/sem_list/routes.py` | Add `GET /sem-list/pending` |
| `back_dev_home/sem_list/providers/office_example.py` | Add roster-minus-avail diff |
| `back_dev_home/sem_list/tests/test_contract.py` | Contract + disjointness gates |
| `back_dev_home/sem_list/tests/test_office_template.py` | New. Pure-normalizer tests for the office diff |
| `docs/datatables/sem_list.txt` | Schema of record: 3 keys, `updt_dt` meaning, lifecycle |
| `back_dev_home/sem_list/MIGRATION.md` | Office adapter instructions for the new endpoint |
| `front-dev-home/app/utils/pendingToolMatrix.ts` | Pure aggregation, grouping, staleness, IP list |
| `front-dev-home/app/utils/pendingToolMatrix.test.ts` | `node --test` coverage of the above |
| `front-dev-home/app/composables/usePendingToolsApi.ts` | On-demand fetch |
| `front-dev-home/app/pages/tool-roster.vue` | The screen |
| `front-dev-home/app/utils/headerNav.ts` | Header entry point |

---

## Task 1: Contract, mock adapter, and schema doc

Delivers `get_pending_tools()` under the mock provider plus the corrected office facts. One commit, because CLAUDE.md requires the schema doc and `mock.py` to move together.

**Files:**

- Modify: `back_dev_home/sem_list/contracts.py`
- Modify: `back_dev_home/sem_list/providers/mock.py`
- Modify: `back_dev_home/sem_list/tests/test_contract.py`
- Modify: `docs/datatables/sem_list.txt`

**Interfaces:**

- Consumes: nothing (first task).
- Produces:
  - `back_dev_home.sem_list.contracts.PendingToolRow` — TypedDict with keys
    `fac_id, eqp_id, eqp_model_cd, eqp_grp_id, vendor_nm, eqp_ip, fab_name, updt_dt`, all `str`.
  - `back_dev_home.sem_list.providers.mock.get_pending_tools() -> list[PendingToolRow]` — returns exactly 14 rows.
  - `back_dev_home.sem_list.providers.mock.get_sem_list() -> list[SemListRow]` — unchanged signature, still 300 rows.

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/sem_list/tests/test_contract.py`:

```python
from back_dev_home.sem_list.contracts import PendingToolRow, SemListRow


def test_pending_tools_matches_contract():
    rows = data.get_pending_tools()
    assert_matches(rows, list[PendingToolRow])
    if get_data_provider("sem_list") == "mock":
        assert rows, "mock pending tools must not be empty"


def test_pending_tools_are_disjoint_from_the_connected_fleet():
    # The whole feature is a set difference. If a tool could appear in both,
    # the screen would ask IT to open a firewall for a tool already reachable.
    connected = {row["eqp_id"] for row in data.get_sem_list()}
    pending = {row["eqp_id"] for row in data.get_pending_tools()}
    assert connected & pending == set()


def test_every_pending_tool_has_an_ip():
    # Every tool is assigned an IP when it is installed in the fab
    # (user-confirmed 2026-07-30). The IP is the payload of the IT request, so
    # a blank one makes the row useless rather than merely incomplete.
    for row in data.get_pending_tools():
        assert row["eqp_ip"], f"{row['eqp_id']} has no eqp_ip"


def test_connected_fleet_size_is_unchanged():
    if get_data_provider("sem_list") == "mock":
        assert len(data.get_sem_list()) == 300
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest back_dev_home/sem_list -q
```

Expected: FAIL with `ImportError: cannot import name 'PendingToolRow'`.

- [ ] **Step 3: Add the contract**

Replace the whole of `back_dev_home/sem_list/contracts.py`:

```python
"""Stable Python contracts for SEM equipment rows."""

from typing import Literal, TypedDict


__all__ = ["PendingToolRow", "SemListRow"]


class SemListRow(TypedDict):
    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_ip: str
    fab_name: str
    # ISO string. The tool's FIRST ARRIVAL time at the fab, not a roster
    # update time; imprecise for old tools, trustworthy for recent ones
    # (user-confirmed 2026-07-30).
    updt_dt: str
    available: Literal["On", "Off"]
    # Free-form string (digits + letters), e.g. "1A". "" (empty) when the
    # fleet row has no matching entry in the office version store
    # (see sem_list/MIGRATION.md).
    version: str


class PendingToolRow(TypedDict):
    """A tool in the company roster that skewnono cannot reach yet.

    Every tool is firewalled when it is first installed in the fab, so this
    is the normal initial state of every tool rather than a fault. A row
    leaves this list when IT opens its IP and it starts appearing in
    ``v3_df_sem_avail``.

    Deliberately NOT a widened ``SemListRow``:

    * no ``available`` / ``version`` — both come from Redis keys this tool is
      not in yet, so there is no value the office could supply and a sentinel
      would be a fiction the contract invented.
    * ``vendor_nm`` carries no ``Literal`` constraint, unlike ``SemListRow``.
      The office adapter raises on an unknown vendor for the connected fleet,
      which is right there and wrong here: this screen exists to surface tools
      we have not onboarded, so a new vendor must show up on it, not 502 it.
    """

    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: str
    # Always populated: assigned at fab installation (user-confirmed
    # 2026-07-30). This is the value the IT firewall request is made of.
    eqp_ip: str
    # "" when the tool has no fab assignment yet; the UI buckets those as 미배정
    # rather than dropping them.
    fab_name: str
    updt_dt: str
```

- [ ] **Step 4: Split the mock generator**

In `back_dev_home/sem_list/providers/mock.py`, replace the module docstring's
office-source paragraph (lines 3–11, the block naming two Redis keys) with:

```python
"""Deterministic Phase 1 adapter for the SEM equipment list.

Office counterpart — schema of record: `docs/datatables/sem_list.txt`.
THREE Redis keys, each a pandas DataFrame serialized to parquet:

    v3_df_sem_list      the FULL company roster — every tool, all tool types
    v3_df_sem_avail     the subset skewnono can actually reach
    v3_df_sem_version   columns [eqp_ip, version]

`v3_df_sem_avail` is a derived subset, not the roster (user-confirmed
2026-07-30). Every tool is assigned an `eqp_ip` when it is installed in the
fab and is FIREWALLED from that moment; it only enters `v3_df_sem_avail`
once IT opens that IP. So `v3_df_sem_list - v3_df_sem_avail` is exactly the
queue of firewall-exception requests, and "in the roster but unreachable" is
the normal initial state of every tool rather than an error.

`get_sem_list()` serves the reachable fleet (the `_avail` + `_version` merge);
`get_pending_tools()` serves the difference. Contract details worth mirroring
here:

* `updt_dt` is the tool's FIRST ARRIVAL time at the fab, NOT a roster-update
  timestamp (user-confirmed 2026-07-30). It is imprecise for old tools and
  trustworthy for recent ones, which is what makes it usable for telling a
  genuine new arrival from a long-abandoned roster entry.
* `version` is a FREE-FORM STRING ("1A"), not a number — do not sort it
  numerically anywhere.
* `vendor_nm` is HITACHI or AMAT for the reachable fleet, and the office
  adapter raises on a third value there. `PendingToolRow` deliberately does
  NOT constrain it — a newly installed tool from a new vendor must appear on
  the 미연결 screen instead of 502-ing it.
* `available` arrives as any of on/off/true/false/1/0 and is normalized to
  "On"/"Off". This mock emits the normalized form directly. Pending tools
  have no `available` at all.
* the fleet carries no `tool_type` column — it is derived from `eqp_model_cd`.
  Note the two classifiers disagree: backend `_tool_specs.model_to_tool_type`
  returns None for AMAT models, while frontend `classifyToolType` resolves
  all four tool types. The 미연결 screen uses the frontend one.

THIS IS THE FLEET IDENTITY SOURCE, and that has a consequence for home runs.
`storage`, `lateral_recipe`, `hardware/sharpness`, `hardware/reso_center` and
`hardware/mdc` all resolve eqp_id -> eqp_ip / fab_name through this roster, so
those office adapters REFUSE to run while sem_list is on mock: a fabricated IP
matches zero documents and is indistinguishable from "no data". Turning one of
them onto office therefore means turning sem_list on too.
"""
```

Correct the AMAT comment at lines 52–58 — it currently claims every
tool-scoped view filters these out, which the new screen deliberately does
not:

```python
# AMAT tools, deferred to 2027. They belong in the inventory but are NOT
# CD/HV-SEM, so backend `model_to_tool_type()` returns None and the
# tool-scoped ebeam views filter them out. The 미연결 screen is the
# exception: it groups by the FRONTEND classifier, which resolves these to
# 'verity-sem' / 'provision', and shows them under their own filter chip —
# their firewall requests get filed too, just not this year. Kept rare here
# because at the old ~50% they crowded the CD/HV-SEM pages down to half a
# fleet. The prefix pool is unverified; nothing classifies by prefix (it only
# builds eqp_ids), so it is cosmetic.
```

Change the `updt_dt` offset in the connected generator. Find:

```python
        updt_dt = (
            now - timedelta(days=rng.randint(0, 90))
        ).isoformat().replace("+00:00", "Z")
```

Replace with:

```python
        # Arrival time, so the fleet's values span years — a roster of tools
        # that all arrived within 90 days would teach that this column is a
        # recency signal, which is exactly the misreading the docs used to
        # encode. Values change freely: check_contract.py compares key sets
        # and value TYPES, never value equality.
        updt_dt = (
            now - timedelta(days=rng.randint(0, 2555))
        ).isoformat().replace("+00:00", "Z")
```

Add the pending cluster table after the `EQP_GRP_PREFIXES` constant:

```python
# Newly installed tools awaiting an IT firewall exception. An explicit table,
# not a random draw: what this fixture has to stand in for is the SHAPE of an
# arrival batch — a few fab x model cells holding several tools each — and a
# uniform random draw produces a matrix of all 1s that never exercises the
# aggregation. Counts and ids are invented; only the shape is claimed.
#
#                fab_name  fac_id  eqp_model_cd     prefix  count  days_ago
_PENDING_CLUSTERS = [
    ("M16A", "M16", "CG6380", "ECDX", 2, 8),
    ("M16B", "M16", "GT2000", "ECDX", 4, 15),
    ("M14B", "M14", "TP4000", "PCD", 5, 22),
    # Older than the UI's 180-day staleness threshold — exercises 오래됨.
    ("M16A", "M16", "VERITYSEM_4", "VCD", 2, 400),
    # No fab assignment yet — exercises the 미배정 bucket. Kept on a different
    # row from the stale one so each edge case is reachable on its own.
    ("", "M11", "PROVISION_10", "ACD", 1, 30),
]
```

Replace `_generate_rows` and `get_sem_list` with the split generator:

```python
def _generate_rows(n_rows: int = 300, seed: int = 42) -> list[SemListRow]:
    ...  # body unchanged apart from the updt_dt edit above


def _generate_pending(
    taken: set[str], seed: int = 43
) -> list[PendingToolRow]:
    """The 14 roster tools skewnono cannot reach yet.

    ``taken`` is the connected fleet's eqp_id set. Ids are re-rolled on
    collision rather than drawn from a reserved numeric range, so the
    disjointness invariant holds even if the connected generator's id scheme
    changes later.
    """
    rng = random.Random(seed)
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    used = set(taken)
    rows: list[PendingToolRow] = []

    for fab_name, fac_id, model, prefix, count, days_ago in _PENDING_CLUSTERS:
        vendor_nm = "AMAT" if model in AMAT_MODELS else "HITACHI"
        for _ in range(count):
            eqp_id = f"{prefix}{rng.randint(100, 999)}"
            while eqp_id in used:
                eqp_id = f"{prefix}{rng.randint(100, 999)}"
            used.add(eqp_id)

            ip_prefix = "177" if rng.random() < 0.5 else "197"
            rows.append(PendingToolRow(
                fac_id=fac_id,
                eqp_id=eqp_id,
                eqp_model_cd=model,
                eqp_grp_id=f"{rng.choice(EQP_GRP_PREFIXES)}{rng.randint(1, 3):02d}",
                vendor_nm=vendor_nm,
                # Always present: assigned at fab installation.
                eqp_ip=(
                    f"{ip_prefix}.{rng.randint(1, 254)}"
                    f".{rng.randint(1, 254)}.{rng.randint(1, 254)}"
                ),
                fab_name=fab_name,
                updt_dt=(
                    now - timedelta(days=days_ago)
                ).isoformat().replace("+00:00", "Z"),
            ))

    return rows


def get_sem_list() -> list[SemListRow]:
    return _generate_rows()


def get_pending_tools() -> list[PendingToolRow]:
    return _generate_pending({row["eqp_id"] for row in _generate_rows()})
```

Add `PendingToolRow` to the contracts import at the top of the file:

```python
from back_dev_home.sem_list.contracts import PendingToolRow, SemListRow
```

- [ ] **Step 5: Wire the dispatcher just enough for the tests to run**

The tests call `data.get_pending_tools()`. Add to `back_dev_home/sem_list/data.py`
— update `__all__` and append the function:

```python
__all__ = ["PendingToolRow", "SemListRow", "get_pending_tools", "get_sem_list"]


def get_pending_tools() -> list[PendingToolRow]:
    if get_data_provider("sem_list") == "office":
        from back_dev_home.sem_list.providers.office import (
            get_pending_tools as load_pending_tools,
        )
    else:
        from back_dev_home.sem_list.providers.mock import (
            get_pending_tools as load_pending_tools,
        )

    return load_pending_tools()
```

And widen its contracts import:

```python
from back_dev_home.sem_list.contracts import PendingToolRow, SemListRow
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/sem_list -q
```

Expected: PASS, 5 tests.

- [ ] **Step 7: Verify nothing downstream moved**

`back_dev_home/meas_hist/providers/mock.py:60` imports this mock's
`get_sem_list`. It filters on `eqp_model_cd` only and never reads `updt_dt`,
so the widened arrival range must not affect it.

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS, the full suite (~1320+ tests).

- [ ] **Step 8: Update the schema doc**

In `docs/datatables/sem_list.txt`:

Replace the two-key block (lines 9–18) with a three-key one:

```text
저장 형태: Redis, pandas DataFrame 을 parquet 직렬화(df.to_parquet(), 값 선두
4바이트가 b"PAR1"). 세 개의 key 로 나뉘어 있습니다.

Key 1 -> "v3_df_sem_list"    : 전사 전체 명부. 모든 tool type 을 포함하며
                               VeritySEM 과 Provision 도 들어 있습니다.
                               (user-confirmed 2026-07-30)
Key 2 -> "v3_df_sem_avail"   : 위 명부 중 접속이 확인된 부분집합입니다.
                               version 컬럼이 **없습니다**.
Key 3 -> "v3_df_sem_version" : 컬럼 [eqp_ip, version] 두 개짜리 보조 table.

장비 lifecycle (user-confirmed 2026-07-30)

모든 장비는 fab 에 반입되는 시점에 eqp_ip 를 부여받고, 그 순간부터 네트워크
방화벽에 막혀 있습니다. IT 서비스팀이 해당 IP 를 열어 준 뒤에야
v3_df_sem_avail 에 들어옵니다. 따라서

    v3_df_sem_list - v3_df_sem_avail  =  방화벽 해제 요청 대기 목록

이며, "명부에 있으나 접속되지 않음"은 오류가 아니라 모든 장비가 반드시 한 번
거치는 정상 초기 상태입니다. GET /api/sem-list/pending 이 이 차집합을
eqp_id 기준으로 계산합니다.

Key 2 와 Key 3 은 eqp_ip 를 기준으로 LEFT merge 합니다(fleet 이 왼쪽). fleet
row 는 한 건도 버리지 않으며, version 이 없는 row 는 빈 문자열("")이 됩니다.
version table 에 같은 eqp_ip 가 여러 건 있으면 fleet row 가 복제되므로, merge
전에 eqp_ip 기준으로 중복 제거(마지막 값 유지)합니다.

Key 1 의 정확한 컬럼 목록은 아직 확인되지 않았습니다(OFFICE-VERIFY). Key 2 와
같은 identity 컬럼을 가지며 available 컬럼이 없다고 가정하고 있습니다.
확인 방법:

    .venv/bin/python -m scripts.inspect_redis_key v3_df_sem_list
```

Replace the `updt_dt` entry (lines 31–32) with:

```text
updt_dt -> string(ISO): **장비가 fab 에 최초 반입된 시각**입니다.
                        명부 갱신 시각이 아닙니다 (user-confirmed 2026-07-30).
                        오래된 장비의 값은 정확하지 않으나 최근 장비의 값은
                        신뢰할 수 있습니다. 따라서 신규 반입 여부 판단에는
                        쓸 수 있지만, 오래된 값을 근거로 row 를 숨기지는
                        않습니다. pandas Timestamp 로 오면 isoformat() 으로
                        변환합니다.
```

Append to the 주의 list:

```text
5. VeritySEM / Provision 은 v3_df_sem_list 에 포함됩니다
   (user-confirmed 2026-07-30). 백엔드 model_to_tool_type() 은 이 모델들에
   None 을 반환하지만 프론트 classifyToolType() 은 verity-sem / provision 으로
   해석합니다. 미연결 장비 화면은 프론트 분류기를 사용하므로 이 장비들도
   자기 필터 chip 아래에 표시됩니다.
```

- [ ] **Step 9: Lint the Markdown and commit**

```bash
npm run lint:md
```

Expected: `Summary: 0 error(s)`. (`docs/datatables/*.txt` is not linted, but
this step guards against an accidental `.md` edit.)

```bash
git add back_dev_home/sem_list/contracts.py \
        back_dev_home/sem_list/providers/mock.py \
        back_dev_home/sem_list/data.py \
        back_dev_home/sem_list/tests/test_contract.py \
        docs/datatables/sem_list.txt
git commit -m "feat(sem_list): add pending-tools contract and mock adapter

The office roster is THREE Redis keys, not two: v3_df_sem_list is the full
company roster and v3_df_sem_avail a derived reachable subset. Every tool is
assigned an IP at fab installation and firewalled from that moment, so
roster-minus-avail is the IT firewall-request queue and 'in the roster but
unreachable' is every tool's normal initial state.

Also corrects updt_dt: it is the tool's FIRST ARRIVAL time, not the '명부 갱신
시각' the schema doc claimed. The mock generated it as a uniform 0-90 days ago,
which actively taught the wrong reading; arrival times now span years.

All user-confirmed 2026-07-30. v3_df_sem_list's exact column list stays
OFFICE-VERIFY, checkable with scripts/inspect_redis_key.py."
```

---

## Task 2: Route

**Files:**

- Modify: `back_dev_home/sem_list/routes.py`
- Create: `back_dev_home/sem_list/tests/test_routes.py`

**Interfaces:**

- Consumes: `back_dev_home.sem_list.data.get_pending_tools()` from Task 1.
- Produces: `GET /api/sem-list/pending` → JSON array of `PendingToolRow`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/sem_list/tests/test_routes.py`:

```python
"""Route-level gate for sem_list.

The pending endpoint is separate from /api/sem-list on purpose: six features
resolve eqp_id -> eqp_ip through the roster response, so unreachable tools
must never appear there.
"""

from back_dev_home import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_pending_endpoint_returns_rows():
    response = _client().get("/api/sem-list/pending")

    assert response.status_code == 200
    rows = response.get_json()
    assert isinstance(rows, list)
    assert rows
    assert set(rows[0]) == {
        "fac_id", "eqp_id", "eqp_model_cd", "eqp_grp_id",
        "vendor_nm", "eqp_ip", "fab_name", "updt_dt",
    }


def test_pending_endpoint_never_leaks_into_the_roster_endpoint():
    client = _client()
    roster = {row["eqp_id"] for row in client.get("/api/sem-list").get_json()}
    pending = {row["eqp_id"] for row in client.get("/api/sem-list/pending").get_json()}

    assert roster & pending == set()
```

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/sem_list/tests/test_routes.py -q
```

Expected: FAIL with a 404 on `/api/sem-list/pending`.

- [ ] **Step 3: Add the route**

Replace `back_dev_home/sem_list/routes.py`:

```python
from flask import Blueprint, jsonify

from back_dev_home.sem_list.data import get_pending_tools, get_sem_list

bp = Blueprint("sem_list", __name__)


@bp.get("/sem-list")
def sem_list():
    rows = get_sem_list()
    return jsonify(rows)


@bp.get("/sem-list/pending")
def sem_list_pending():
    """Roster tools skewnono cannot reach yet — the firewall-request queue.

    Separate from /sem-list because that response is the fleet identity
    source six other features join through; adding unreachable tools there
    would put them in every tool picker in the app.
    """
    rows = get_pending_tools()
    return jsonify(rows)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/sem_list -q
```

Expected: PASS, 7 tests.

- [ ] **Step 5: Confirm the rate limiter did not reject the second call**

`/api/*` is rate-limited to 20 requests / 5 s per user. Two calls in one test
is fine, but confirm the suite is green as a whole rather than only in
isolation:

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/sem_list/routes.py back_dev_home/sem_list/tests/test_routes.py
git commit -m "feat(sem_list): expose GET /api/sem-list/pending

Kept separate from /api/sem-list, whose response is the fleet identity source
that storage, lateral_recipe, hardware/{sharpness,reso_center,mdc} and
meas_hist resolve eqp_id -> eqp_ip through. A route test asserts the two
endpoints never share an eqp_id."
```

---

## Task 3: Office adapter template

**Files:**

- Modify: `back_dev_home/sem_list/providers/office_example.py`
- Create: `back_dev_home/sem_list/tests/test_office_template.py`
- Modify: `back_dev_home/sem_list/MIGRATION.md`

**Interfaces:**

- Consumes: `PendingToolRow` (Task 1); existing module helpers `_to_text`,
  `_as_iso_string`, `_load_dataframe`, `_redis_client`, `_REDIS_KEY`.
- Produces:
  - `office_example.get_pending_tools() -> list[PendingToolRow]`
  - `office_example._select_pending(roster: pd.DataFrame, connected: pd.DataFrame) -> list[PendingToolRow]`
    — the pure part, so tests never touch a cluster.
  - `office_example._ROSTER_KEY = "v3_df_sem_list"`

- [ ] **Step 1: Write the failing tests**

Create `back_dev_home/sem_list/tests/test_office_template.py`:

```python
"""Office sem_list adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds fabricated
DataFrames to the pure selector.
"""

import pandas as pd
import pytest

from back_dev_home.sem_list.providers import office_example as office


def _roster(rows: list[dict]) -> pd.DataFrame:
    base = {
        "fac_id": "M16",
        "eqp_id": "ECDX100",
        "eqp_model_cd": "CG6300",
        "eqp_grp_id": "G-ECD-01",
        "vendor_nm": "HITACHI",
        "eqp_ip": "177.1.1.1",
        "fab_name": "M16A",
        "updt_dt": "2026-07-20T00:00:00Z",
    }
    return pd.DataFrame([{**base, **row} for row in rows])


def _connected(eqp_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"eqp_id": eqp_ids})


def test_pending_is_the_roster_minus_the_reachable_subset():
    roster = _roster([{"eqp_id": "ECDX100"}, {"eqp_id": "ECDX200"}])

    rows = office._select_pending(roster, _connected(["ECDX100"]))

    assert [row["eqp_id"] for row in rows] == ["ECDX200"]


def test_no_pending_tools_is_an_empty_list_not_an_error():
    roster = _roster([{"eqp_id": "ECDX100"}])

    assert office._select_pending(roster, _connected(["ECDX100"])) == []


def test_an_empty_roster_is_an_empty_list():
    assert office._select_pending(_roster([]), _connected([])) == []


def test_diff_is_on_eqp_id_not_eqp_ip():
    # eqp_id is the tool's name and always present; diffing on eqp_ip would
    # misclassify a tool whose IP was reassigned.
    roster = _roster([{"eqp_id": "ECDX200", "eqp_ip": "177.1.1.1"}])
    connected = pd.DataFrame({"eqp_id": ["ECDX100"], "eqp_ip": ["177.1.1.1"]})

    rows = office._select_pending(roster, connected)

    assert [row["eqp_id"] for row in rows] == ["ECDX200"]


def test_missing_roster_column_names_the_column():
    roster = _roster([{"eqp_id": "ECDX200"}]).drop(columns=["fab_name"])

    with pytest.raises(ValueError) as err:
        office._select_pending(roster, _connected([]))

    assert "fab_name" in str(err.value)
    assert office._ROSTER_KEY in str(err.value)


def test_missing_eqp_id_on_the_connected_frame_names_the_key():
    with pytest.raises(ValueError) as err:
        office._select_pending(_roster([{}]), pd.DataFrame({"eqp_ip": ["1.1.1.1"]}))

    assert "eqp_id" in str(err.value)
    assert office._REDIS_KEY in str(err.value)


def test_an_unknown_vendor_is_passed_through_not_rejected():
    # The opposite of get_sem_list's rule. This screen exists to surface tools
    # we have not onboarded, so a new vendor must appear rather than 502.
    roster = _roster([{"eqp_id": "ECDX200", "vendor_nm": "NEWVENDOR"}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["vendor_nm"] == "NEWVENDOR"


def test_a_blank_fab_name_survives_for_the_ui_to_bucket():
    roster = _roster([{"eqp_id": "ECDX200", "fab_name": ""}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["fab_name"] == ""


def test_a_timestamp_arrival_becomes_an_iso_string():
    roster = _roster([{"eqp_id": "ECDX200", "updt_dt": pd.Timestamp("2026-07-20")}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["updt_dt"] == "2026-07-20T00:00:00"


def test_bytes_cells_are_decoded_as_utf8():
    roster = _roster([{"eqp_id": "ECDX200", "fab_name": "R3".encode()}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["fab_name"] == "R3"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/python -m pytest back_dev_home/sem_list/tests/test_office_template.py -q
```

Expected: FAIL with `AttributeError: module ... has no attribute '_select_pending'`.

- [ ] **Step 3: Implement the office diff**

Append to `back_dev_home/sem_list/providers/office_example.py`, and add
`PendingToolRow` to its contracts import:

```python
from back_dev_home.sem_list.contracts import PendingToolRow, SemListRow
```

```python
_ROSTER_KEY = "v3_df_sem_list"

# No `available` and no `version`: both live in keys a pending tool is not in.
_PENDING_REQUIRED_COLUMNS = frozenset(
    {
        "fac_id",
        "eqp_id",
        "eqp_model_cd",
        "eqp_grp_id",
        "vendor_nm",
        "eqp_ip",
        "fab_name",
        "updt_dt",
    }
)


def _normalize_pending(df: pd.DataFrame) -> list[PendingToolRow]:
    """Shape roster rows into the contract.

    Note what this does NOT do, unlike `_normalize`: it does not validate
    `vendor_nm` against a known set, and it does not map `available`. A tool
    we have not onboarded may legitimately carry a vendor we have never seen,
    and rejecting it would empty the one screen meant to reveal it.
    """
    return [
        PendingToolRow(
            fac_id=_to_text(rec["fac_id"]),
            eqp_id=_to_text(rec["eqp_id"]),
            eqp_model_cd=_to_text(rec["eqp_model_cd"]),
            eqp_grp_id=_to_text(rec["eqp_grp_id"]),
            vendor_nm=_to_text(rec["vendor_nm"]).strip().upper(),
            eqp_ip=_to_text(rec["eqp_ip"]).strip(),
            fab_name=_to_text(rec["fab_name"]).strip(),
            updt_dt=_as_iso_string(rec["updt_dt"]),
        )
        for rec in df.to_dict(orient="records")
    ]


def _select_pending(
    roster: pd.DataFrame, connected: pd.DataFrame
) -> list[PendingToolRow]:
    """Roster minus reachable, diffed on ``eqp_id``.

    ``eqp_id`` and not ``eqp_ip``: the id is the tool's name and every roster
    row has one, whereas an ip can be reassigned. Kept separate from
    :func:`get_pending_tools` so it is testable without a Redis.
    """
    missing = _PENDING_REQUIRED_COLUMNS - set(roster.columns)
    if missing:
        raise ValueError(
            f"Redis key {_ROSTER_KEY!r} DataFrame is missing columns: "
            f"{sorted(missing)} (got {sorted(roster.columns)})"
        )
    if _MERGE_KEY not in roster.columns and "eqp_id" not in roster.columns:
        raise ValueError(f"Redis key {_ROSTER_KEY!r} has no 'eqp_id' column")
    if "eqp_id" not in connected.columns:
        raise ValueError(
            f"Redis key {_REDIS_KEY!r} has no 'eqp_id' column to diff against "
            f"(got {sorted(connected.columns)})."
        )

    if roster.empty:
        return []
    pending = roster[~roster["eqp_id"].isin(set(connected["eqp_id"]))]
    if pending.empty:
        return []
    return _normalize_pending(pending)


def get_pending_tools() -> list[PendingToolRow]:
    client = _redis_client()
    roster = _load_dataframe(client, _ROSTER_KEY)
    connected = _load_dataframe(client, _REDIS_KEY)
    return _select_pending(roster, connected)
```

Also extend the module docstring's key list to name all three keys and state
that `v3_df_sem_avail` is a derived subset, mirroring Task 1's `mock.py`
docstring.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/sem_list -q
```

Expected: PASS, 17 tests.

- [ ] **Step 5: Check the whole suite and ruff**

```bash
.venv/bin/python -m pytest -q
ruff check back_dev_home/sem_list scripts
```

Expected: pytest PASS; ruff reports nothing for `back_dev_home/sem_list`.
(`scripts/probe_recipe_ftp.py` has a pre-existing `F402` — not yours, leave it.)

- [ ] **Step 6: Document the endpoint in MIGRATION.md**

Append a section to `back_dev_home/sem_list/MIGRATION.md` after the existing
`GET /api/sem-list` section, and correct that section's "**two** Redis keys"
to three:

````markdown
## Endpoint: GET /api/sem-list/pending

- Handler: `routes.py` → `data.get_pending_tools()`
- Contract: `PendingToolRow` — the eight identity columns, no `available`
  and no `version` (both live in keys a pending tool is not in yet).
- Office data source: `v3_df_sem_list` (full company roster) diffed against
  `v3_df_sem_avail` (reachable subset) on **`eqp_id`**.

  ```python
  pending = roster[~roster["eqp_id"].isin(set(connected["eqp_id"]))]
  ```

  Every tool is assigned an `eqp_ip` at fab installation and is firewalled
  from that moment, entering `v3_df_sem_avail` only once IT opens the IP. So
  this difference is the firewall-request queue, and an empty result means
  every roster tool is reachable — a valid response, not an error.
- `v3_df_sem_list`'s exact column list is **OFFICE-VERIFY**. It is assumed to
  carry the same identity columns as `v3_df_sem_avail` minus `available`. If
  that is wrong, `_select_pending` raises with the missing column names.
  Check it first with:

  ```bash
  .venv/bin/python -m scripts.inspect_redis_key v3_df_sem_list
  ```

- Unlike `get_sem_list`, an unknown `vendor_nm` is **passed through**, not
  rejected. This screen exists to surface tools that have not been onboarded,
  so a new vendor must appear on it rather than 502 the request.
- Mock behavior: 14 tools in 5 fab × model clusters, one with `fab_name=""`
  and one arriving 400 days ago, so the UI's 미배정 and 오래됨 paths both have
  data at home.
````

- [ ] **Step 7: Lint and commit**

```bash
npm run lint:md
```

Expected: `Summary: 0 error(s)`.

```bash
git add back_dev_home/sem_list/providers/office_example.py \
        back_dev_home/sem_list/tests/test_office_template.py \
        back_dev_home/sem_list/MIGRATION.md
git commit -m "feat(sem_list): office adapter for the pending-tools diff

Diffs v3_df_sem_list against v3_df_sem_avail on eqp_id -- the id is the tool's
name and always present, whereas an ip can be reassigned. The pure selector
_select_pending() is split out so the 10 tests feed fabricated DataFrames and
never reach a cluster.

Unknown vendors pass through here, the opposite of get_sem_list's rule: this
endpoint's job is surfacing tools we have not onboarded, so rejecting an
unfamiliar vendor would empty the screen meant to reveal it. Missing columns
raise with the column list, so a wrong OFFICE-VERIFY guess about
v3_df_sem_list's schema is diagnosable instead of showing an empty table."
```

---

## Task 4: Matrix aggregation util

Pure functions only, so `npm test` covers them.

**Files:**

- Create: `front-dev-home/app/utils/pendingToolMatrix.ts`
- Create: `front-dev-home/app/utils/pendingToolMatrix.test.ts`

**Interfaces:**

- Consumes: `classifyToolType` from `~/composables/useSemListApi`; `ToolType` from `~/stores/navigation`.
- Produces, all from `~/utils/pendingToolMatrix`:
  - `interface PendingToolRow` — mirrors the backend contract (8 string fields)
  - `UNASSIGNED_FAB = '미배정'`, `UNCLASSIFIED = 'unclassified'`, `STALE_ARRIVAL_DAYS = 180`
  - `type PendingToolGroup = ToolType | 'unclassified'`
  - `groupOf(row: PendingToolRow): PendingToolGroup`
  - `countByGroup(rows: PendingToolRow[]): Map<PendingToolGroup, number>`
  - `filterByGroup(rows: PendingToolRow[], group: PendingToolGroup | 'all'): PendingToolRow[]`
  - `buildPendingToolMatrix(rows: PendingToolRow[]): PendingToolMatrix`
  - `interface PendingToolMatrix { fabs: string[], models: string[], counts: number[][], fabTotals: number[], modelTotals: number[], total: number }`
  - `cellRows(rows: PendingToolRow[], fab: string, model: string): PendingToolRow[]`
  - `isStaleArrival(updtDt: string, now: Date): boolean`
  - `ipList(rows: PendingToolRow[]): string`

- [ ] **Step 1: Write the failing tests**

Create `front-dev-home/app/utils/pendingToolMatrix.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  STALE_ARRIVAL_DAYS,
  UNASSIGNED_FAB,
  buildPendingToolMatrix,
  cellRows,
  countByGroup,
  filterByGroup,
  groupOf,
  ipList,
  isStaleArrival
} from './pendingToolMatrix.ts'
import type { PendingToolRow } from './pendingToolMatrix.ts'

const tool = (
  eqp_id: string,
  eqp_model_cd: string,
  fab_name: string,
  eqp_ip = '177.1.1.1',
  updt_dt = '2026-07-01T00:00:00Z'
): PendingToolRow => ({
  fac_id: fab_name.startsWith('R') ? 'R3' : 'M16',
  eqp_id,
  eqp_model_cd,
  eqp_grp_id: 'G-ECD-01',
  vendor_nm: eqp_model_cd.startsWith('VERITYSEM') || eqp_model_cd.startsWith('PROVISION')
    ? 'AMAT'
    : 'HITACHI',
  eqp_ip,
  fab_name,
  updt_dt
})

test('groupOf resolves all four tool types and falls back to unclassified', () => {
  assert.equal(groupOf(tool('A', 'CG6380', 'M16A')), 'cd-sem')
  assert.equal(groupOf(tool('B', 'GT2000', 'M16A')), 'cd-sem')
  assert.equal(groupOf(tool('C', 'TP4000', 'M14B')), 'hv-sem')
  assert.equal(groupOf(tool('D', 'VERITYSEM_4', 'M16A')), 'verity-sem')
  assert.equal(groupOf(tool('E', 'PROVISION_10', 'M11A')), 'provision')
  // A model the company installs next year. This bucket is the only thing
  // keeping a new tool type from vanishing off the arrivals screen.
  assert.equal(groupOf(tool('F', 'ZZ9000', 'M16A')), 'unclassified')
})

test('countByGroup counts every group present', () => {
  const counts = countByGroup([
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M16A'),
    tool('C', 'TP4000', 'M14B'),
    tool('D', 'ZZ9000', 'M16A')
  ])

  assert.equal(counts.get('cd-sem'), 2)
  assert.equal(counts.get('hv-sem'), 1)
  assert.equal(counts.get('unclassified'), 1)
  assert.equal(counts.get('verity-sem'), undefined)
})

test('filterByGroup with all returns everything unchanged', () => {
  const rows = [tool('A', 'CG6380', 'M16A'), tool('C', 'TP4000', 'M14B')]
  assert.deepEqual(filterByGroup(rows, 'all'), rows)
})

test('filterByGroup narrows to one tool type', () => {
  const rows = [tool('A', 'CG6380', 'M16A'), tool('C', 'TP4000', 'M14B')]
  assert.deepEqual(filterByGroup(rows, 'hv-sem').map(r => r.eqp_id), ['C'])
})

test('buildPendingToolMatrix cross-tabulates fab against model', () => {
  const matrix = buildPendingToolMatrix([
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M16A'),
    tool('C', 'GT2000', 'M16B'),
    tool('D', 'CG6380', 'M16B')
  ])

  assert.deepEqual(matrix.fabs, ['M16A', 'M16B'])
  assert.deepEqual(matrix.models, ['CG6380', 'GT2000'])
  assert.deepEqual(matrix.counts, [[2, 0], [1, 1]])
  assert.deepEqual(matrix.fabTotals, [2, 2])
  assert.deepEqual(matrix.modelTotals, [3, 1])
  assert.equal(matrix.total, 4)
})

test('buildPendingToolMatrix sorts fabs naturally, not lexically', () => {
  const matrix = buildPendingToolMatrix([
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M9A'),
    tool('C', 'CG6380', 'M11A')
  ])

  assert.deepEqual(matrix.fabs, ['M9A', 'M11A', 'M16A'])
})

test('buildPendingToolMatrix buckets a blank fab as 미배정 and sorts it last', () => {
  const matrix = buildPendingToolMatrix([
    tool('A', 'CG6380', ''),
    tool('B', 'CG6380', 'M16A')
  ])

  assert.deepEqual(matrix.fabs, ['M16A', UNASSIGNED_FAB])
  assert.equal(matrix.total, 2)
})

test('buildPendingToolMatrix on no rows is empty, not a crash', () => {
  const matrix = buildPendingToolMatrix([])

  assert.deepEqual(matrix.fabs, [])
  assert.deepEqual(matrix.models, [])
  assert.deepEqual(matrix.counts, [])
  assert.equal(matrix.total, 0)
})

test('cellRows returns the tools behind one cell, including the 미배정 bucket', () => {
  const rows = [
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M16A'),
    tool('C', 'GT2000', 'M16A'),
    tool('D', 'CG6380', '')
  ]

  assert.deepEqual(cellRows(rows, 'M16A', 'CG6380').map(r => r.eqp_id), ['A', 'B'])
  assert.deepEqual(cellRows(rows, UNASSIGNED_FAB, 'CG6380').map(r => r.eqp_id), ['D'])
})

test('isStaleArrival is exclusive at the threshold', () => {
  const now = new Date('2026-07-30T00:00:00Z')
  const daysAgo = (n: number) =>
    new Date(now.getTime() - n * 86_400_000).toISOString()

  assert.equal(isStaleArrival(daysAgo(STALE_ARRIVAL_DAYS - 1), now), false)
  assert.equal(isStaleArrival(daysAgo(STALE_ARRIVAL_DAYS), now), false)
  assert.equal(isStaleArrival(daysAgo(STALE_ARRIVAL_DAYS + 1), now), true)
})

test('isStaleArrival treats an unparseable arrival as not stale', () => {
  // Never hide a row because its timestamp was malformed — the cost of a
  // missing new arrival is a tool nobody notices is unreachable.
  assert.equal(isStaleArrival('', new Date('2026-07-30T00:00:00Z')), false)
  assert.equal(isStaleArrival('not a date', new Date('2026-07-30T00:00:00Z')), false)
})

test('ipList is newline separated, deduped, and order-preserving', () => {
  const rows = [
    tool('A', 'CG6380', 'M16A', '177.1.1.1'),
    tool('B', 'CG6380', 'M16A', '177.1.1.2'),
    tool('C', 'CG6380', 'M16A', '177.1.1.1')
  ]

  assert.equal(ipList(rows), '177.1.1.1\n177.1.1.2')
})

test('ipList skips blank ips', () => {
  assert.equal(ipList([tool('A', 'CG6380', 'M16A', '')]), '')
})
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm --prefix front-dev-home test
```

Expected: FAIL — cannot resolve `./pendingToolMatrix.ts`.

- [ ] **Step 3: Implement the util**

Create `front-dev-home/app/utils/pendingToolMatrix.ts`:

```ts
import type { ToolType } from '~/stores/navigation'
import { classifyToolType } from '~/composables/useSemListApi'

// Mirrors PendingToolRow in back_dev_home/sem_list/contracts.py. No
// `available` or `version`: both come from Redis keys a pending tool is not
// in yet, so there is no value the office could supply.
export interface PendingToolRow {
  fac_id: string
  eqp_id: string
  eqp_model_cd: string
  eqp_grp_id: string
  vendor_nm: string
  eqp_ip: string
  fab_name: string
  // The tool's first arrival at the fab, NOT a roster-update time.
  updt_dt: string
}

// Displayed in place of an empty fab_name. A roster entry can precede its fab
// assignment, and dropping those rows would hide tools from the one screen
// meant to surface them.
export const UNASSIGNED_FAB = '미배정'

// classifyToolType returns null for any prefix it does not know. A model the
// company installs next year will not be in that list, so this bucket is what
// stands between a new tool type and silent invisibility here.
export const UNCLASSIFIED = 'unclassified'

// A tool that arrived more than this long ago and is still unreachable is more
// likely decommissioned than awaiting a firewall exception. Weakly grounded —
// revisit once the screen has real use. Rows past it are de-emphasized, never
// hidden and never dropped from the IP list.
export const STALE_ARRIVAL_DAYS = 180

const MS_PER_DAY = 86_400_000

export type PendingToolGroup = ToolType | typeof UNCLASSIFIED

export interface PendingToolMatrix {
  fabs: string[]
  models: string[]
  // counts[fabIndex][modelIndex], aligned to `fabs` and `models`.
  counts: number[][]
  fabTotals: number[]
  modelTotals: number[]
  total: number
}

// Numeric collation so M9A sorts before M11A. A plain sort puts "M11A" first
// because "1" < "9" lexically, which reads as a bug in a fab column.
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

export const fabLabel = (fabName: string): string => fabName.trim() || UNASSIGNED_FAB

export const groupOf = (row: PendingToolRow): PendingToolGroup =>
  classifyToolType(row.eqp_model_cd) ?? UNCLASSIFIED

export const countByGroup = (rows: PendingToolRow[]): Map<PendingToolGroup, number> => {
  const counts = new Map<PendingToolGroup, number>()
  for (const row of rows) {
    const group = groupOf(row)
    counts.set(group, (counts.get(group) ?? 0) + 1)
  }
  return counts
}

export const filterByGroup = (
  rows: PendingToolRow[],
  group: PendingToolGroup | 'all'
): PendingToolRow[] => (group === 'all' ? rows : rows.filter(row => groupOf(row) === group))

// 미배정 sorts last regardless of collation: it is a bucket, not a fab, and
// leaving it interleaved alphabetically makes it look like one.
const compareFabs = (left: string, right: string): number => {
  if (left === UNASSIGNED_FAB) return right === UNASSIGNED_FAB ? 0 : 1
  if (right === UNASSIGNED_FAB) return -1
  return collator.compare(left, right)
}

export const buildPendingToolMatrix = (rows: PendingToolRow[]): PendingToolMatrix => {
  const fabs = [...new Set(rows.map(row => fabLabel(row.fab_name)))].sort(compareFabs)
  const models = [...new Set(rows.map(row => row.eqp_model_cd))].sort((a, b) =>
    collator.compare(a, b)
  )

  const fabIndex = new Map(fabs.map((fab, index) => [fab, index]))
  const modelIndex = new Map(models.map((model, index) => [model, index]))

  const counts = fabs.map(() => models.map(() => 0))
  for (const row of rows) {
    const fabAt = fabIndex.get(fabLabel(row.fab_name))
    const modelAt = modelIndex.get(row.eqp_model_cd)
    if (fabAt === undefined || modelAt === undefined) continue
    counts[fabAt]![modelAt]! += 1
  }

  return {
    fabs,
    models,
    counts,
    fabTotals: counts.map(fabRow => fabRow.reduce((sum, n) => sum + n, 0)),
    modelTotals: models.map((_, at) => counts.reduce((sum, fabRow) => sum + fabRow[at]!, 0)),
    total: rows.length
  }
}

export const cellRows = (
  rows: PendingToolRow[],
  fab: string,
  model: string
): PendingToolRow[] =>
  rows.filter(row => fabLabel(row.fab_name) === fab && row.eqp_model_cd === model)

export const isStaleArrival = (updtDt: string, now: Date): boolean => {
  const arrived = Date.parse(updtDt)
  // An unparseable arrival is NOT stale. Marking it stale on a parse failure
  // would de-emphasize rows for a reason that has nothing to do with the tool.
  if (Number.isNaN(arrived)) return false
  return (now.getTime() - arrived) / MS_PER_DAY > STALE_ARRIVAL_DAYS
}

// Newline separated, which is the form a firewall request form takes. Deduped
// because two roster rows can share an ip, and IT should see each ip once.
export const ipList = (rows: PendingToolRow[]): string =>
  [...new Set(rows.map(row => row.eqp_ip.trim()).filter(ip => ip !== ''))].join('\n')
```

- [ ] **Step 4: Run tests, typecheck, lint**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run typecheck
npm --prefix front-dev-home run lint
```

Expected: 14 tests PASS; typecheck and lint clean.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/pendingToolMatrix.ts \
        front-dev-home/app/utils/pendingToolMatrix.test.ts
git commit -m "feat(tool-roster): pure aggregation for the pending-tool matrix

Cross-tabulates pending tools by fab_name x eqp_model_cd, groups by tool type
via the frontend classifier, and builds the newline-separated IP list the IT
firewall request is made of.

Three deliberate choices, each with a test: a blank fab_name becomes a 미배정
bucket sorted last rather than a dropped row; an unrecognized model becomes
'unclassified' rather than being filtered, so a tool type we adopt next year
cannot vanish off the arrivals screen; and an unparseable updt_dt counts as
NOT stale, since de-emphasizing a row over a bad timestamp hides a tool for a
reason unrelated to the tool. isStaleArrival takes `now` as a parameter so it
is testable without mocking the clock."
```

---

## Task 5: Composable, page, and header entry

**Files:**

- Create: `front-dev-home/app/composables/usePendingToolsApi.ts`
- Create: `front-dev-home/app/pages/tool-roster.vue`
- Modify: `front-dev-home/app/utils/headerNav.ts`

**Interfaces:**

- Consumes: everything exported by `~/utils/pendingToolMatrix` (Task 4);
  `GET /api/sem-list/pending` (Task 2); `joinApiPath` from `~/utils/apiPath`;
  `copyTextToClipboard` and `downloadCsv` from `~/utils/csvDownload`.
- Produces: `usePendingTools()` returning the `useAsyncData` handle
  (`data`, `status`, `error`, `execute`, `clear`) for cache key `'pending-tools'`.

- [ ] **Step 1: Write the composable**

Create `front-dev-home/app/composables/usePendingToolsApi.ts`:

```ts
import type { PendingToolRow } from '~/utils/pendingToolMatrix'
import { joinApiPath } from '~/utils/apiPath'

// Shared cache key, same convention as SEM_LIST_CACHE_KEY in useSemListApi.ts.
const PENDING_TOOLS_CACHE_KEY = 'pending-tools'

/**
 * The roster tools skewnono cannot reach yet — fetched ON DEMAND ONLY.
 *
 * `immediate: false` is the point, not an optimization. `v3_df_sem_list` is the
 * full company roster and is only wanted when someone is actually preparing a
 * firewall request, so navigating to the page must not touch it. Call
 * `execute()` from a user action; the result then stays cached for the session
 * and `execute()` again re-fetches.
 *
 * Deliberately unlike `useSemList()`, which fetches on mount because five other
 * features depend on the roster being warm.
 */
export const usePendingTools = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/sem-list/pending')

  return useAsyncData(
    PENDING_TOOLS_CACHE_KEY,
    () => $fetch<PendingToolRow[]>(url),
    { immediate: false, default: () => [] as PendingToolRow[] }
  )
}
```

- [ ] **Step 2: Add the header entry**

In `front-dev-home/app/utils/headerNav.ts`, insert into `HEADER_LINKS` after
the `/endpoints` entry:

```ts
  // network: 이 화면이 다루는 것이 장비의 네트워크 연결 상태 — 방화벽이 열려
  // skewnono 가 닿을 수 있는지 — 그 자체입니다.
  { to: '/tool-roster', icon: 'i-lucide-network', label: '미연결 장비' },
```

Adding it here is also what allows the page to keep its feature tabs:
`HEADER_INFO_PATHS` is derived from this array (see the file's own comment
about the three times a hand-maintained second list drifted).

- [ ] **Step 3: Write the page**

Create `front-dev-home/app/pages/tool-roster.vue`:

```vue
<template>
  <div class="flex flex-col gap-3 h-full min-h-0 p-4">
    <UCard
      class="dashboard-surface flex flex-col flex-1 min-h-0"
      :ui="{ body: 'p-0 sm:p-0 flex flex-1 flex-col min-h-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <h2 class="sk-heading">
              미연결 장비
            </h2>
            <UBadge
              v-if="status === 'success'"
              color="neutral"
              variant="subtle"
            >
              조회됨 {{ rows.length }} 대
            </UBadge>
          </div>
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            :icon="status === 'success' ? 'i-lucide-rotate-ccw' : 'i-lucide-search'"
            :label="status === 'success' ? '새로고침' : '조회'"
            :loading="status === 'pending'"
            @click="load"
          />
        </div>
      </template>

      <!-- Idle: nothing has been fetched, because this page never fetches on
           navigation. Say why, so the empty screen does not read as broken. -->
      <div
        v-if="status === 'idle'"
        class="flex flex-col items-center justify-center gap-2 flex-1 px-6 py-12 text-center"
      >
        <UIcon
          name="i-lucide-network"
          class="size-8 text-(--sk-ink-muted)"
        />
        <p class="sk-value">
          전사 장비 명부는 조회 시점에만 불러옵니다.
        </p>
        <p class="sk-label">
          조회를 누르면 방화벽 해제가 필요한 장비를 확인할 수 있습니다.
        </p>
      </div>

      <div
        v-else-if="status === 'error'"
        class="flex flex-col items-center justify-center gap-2 flex-1 px-6 py-12 text-center"
      >
        <UIcon
          name="i-lucide-triangle-alert"
          class="size-8 text-(--sk-bad)"
        />
        <p class="sk-value">
          명부를 불러오지 못했습니다.
        </p>
        <p class="sk-label">
          {{ error?.message }}
        </p>
      </div>

      <div
        v-else-if="status === 'success' && rows.length === 0"
        class="flex flex-col items-center justify-center gap-2 flex-1 px-6 py-12 text-center"
      >
        <UIcon
          name="i-lucide-check"
          class="size-8 text-(--sk-ok)"
        />
        <p class="sk-value">
          명부의 모든 장비가 연결되어 있습니다.
        </p>
      </div>

      <div
        v-else-if="status === 'success'"
        class="flex flex-col flex-1 min-h-0"
      >
        <!-- Tool-type filter. Scopes the matrix AND the IP list: an IT request
             is filed per tool type, not as one mixed list. -->
        <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-(--sk-border)">
          <UButton
            v-for="chip in groupChips"
            :key="chip.value"
            size="sm"
            :color="chip.value === activeGroup ? 'primary' : 'neutral'"
            :variant="chip.value === activeGroup ? 'solid' : 'subtle'"
            @click="selectGroup(chip.value)"
          >
            {{ chip.label }} {{ chip.count }}
          </UButton>

          <div class="flex-1" />

          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-clipboard"
            label="IP 목록 복사"
            :disabled="visibleRows.length === 0"
            @click="copyIpList"
          />
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-download"
            label="CSV 다운로드"
            :disabled="visibleRows.length === 0"
            @click="downloadPendingCsv"
          />
        </div>

        <div class="flex-1 min-h-0 overflow-auto">
          <!-- Matrix -->
          <table class="w-full text-left">
            <thead class="sticky top-0 bg-(--sk-surface)">
              <tr>
                <th class="sk-label py-2 px-3">
                  Fab
                </th>
                <th
                  v-for="model in matrix.models"
                  :key="model"
                  class="sk-label py-2 px-3 text-right"
                >
                  {{ model }}
                </th>
                <th class="sk-label py-2 px-3 text-right">
                  합계
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(fab, fabAt) in matrix.fabs"
                :key="fab"
                class="transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
              >
                <td class="sk-value py-1.5 px-3">
                  {{ fab }}
                </td>
                <td
                  v-for="(model, modelAt) in matrix.models"
                  :key="model"
                  class="py-1.5 px-3 text-right"
                >
                  <!-- Zero renders as · so occupied cells carry the eye. -->
                  <UButton
                    v-if="matrix.counts[fabAt]?.[modelAt]"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    :label="String(matrix.counts[fabAt]?.[modelAt])"
                    :aria-label="`${fab} ${model} 장비 ${matrix.counts[fabAt]?.[modelAt]}대 보기`"
                    @click="selectCell(fab, model)"
                  />
                  <span
                    v-else
                    class="sk-label"
                  >·</span>
                </td>
                <td class="sk-value-num py-1.5 px-3 text-right">
                  {{ matrix.fabTotals[fabAt] }}
                </td>
              </tr>
            </tbody>
            <tfoot class="border-t border-(--sk-border)">
              <tr>
                <td class="sk-label py-2 px-3">
                  합계
                </td>
                <td
                  v-for="(model, modelAt) in matrix.models"
                  :key="model"
                  class="sk-value-num py-2 px-3 text-right"
                >
                  {{ matrix.modelTotals[modelAt] }}
                </td>
                <td class="sk-value-num py-2 px-3 text-right">
                  {{ matrix.total }}
                </td>
              </tr>
            </tfoot>
          </table>

          <!-- Drill-down -->
          <div
            v-if="selectedCell"
            class="border-t border-(--sk-border)"
          >
            <div class="px-4 py-2.5 flex items-center justify-between gap-3">
              <h3 class="sk-heading">
                {{ selectedCell.fab }} / {{ selectedCell.model }}
                <span class="sk-label">{{ drilldownRows.length }}대</span>
              </h3>
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                aria-label="드릴다운 닫기"
                @click="selectedCell = null"
              />
            </div>
            <table class="w-full text-left">
              <thead>
                <tr>
                  <th class="sk-label py-2 px-3">
                    Equipment ID
                  </th>
                  <th class="sk-label py-2 px-3">
                    IP Address
                  </th>
                  <th class="sk-label py-2 px-3">
                    Vendor
                  </th>
                  <th class="sk-label py-2 px-3">
                    반입일
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in drilldownRows"
                  :key="row.eqp_id"
                  class="transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                >
                  <td class="sk-value-num py-1.5 px-3">
                    {{ row.eqp_id }}
                  </td>
                  <td class="sk-value-num py-1.5 px-3">
                    {{ row.eqp_ip }}
                  </td>
                  <td class="sk-value capitalize py-1.5 px-3">
                    {{ row.vendor_nm.toLowerCase() }}
                  </td>
                  <td class="py-1.5 px-3">
                    <span :class="isStale(row) ? 'sk-label' : 'sk-value-num'">
                      {{ arrivalDate(row.updt_dt) }}
                    </span>
                    <!-- De-emphasized, never hidden and never dropped from the
                         IP list: a stale row costs one reply from IT, while a
                         hidden new arrival costs an unreachable tool nobody
                         notices. -->
                    <UBadge
                      v-if="isStale(row)"
                      class="ml-2"
                      color="neutral"
                      variant="subtle"
                      size="sm"
                      label="오래됨"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { PendingToolGroup, PendingToolRow } from '~/utils/pendingToolMatrix'
import {
  buildPendingToolMatrix,
  cellRows,
  countByGroup,
  filterByGroup,
  ipList,
  isStaleArrival
} from '~/utils/pendingToolMatrix'
import { copyTextToClipboard, downloadCsv } from '~/utils/csvDownload'

const { data, status, error, execute } = usePendingTools()
const toast = useToast()

const rows = computed<PendingToolRow[]>(() => data.value ?? [])

const activeGroup = ref<PendingToolGroup | 'all'>('all')
const selectedCell = ref<{ fab: string, model: string } | null>(null)

const load = async () => {
  selectedCell.value = null
  await execute()
}

const GROUP_LABELS: Array<{ value: PendingToolGroup, label: string }> = [
  { value: 'cd-sem', label: 'CD-SEM' },
  { value: 'hv-sem', label: 'HV-SEM' },
  { value: 'verity-sem', label: 'VeritySEM' },
  { value: 'provision', label: 'Provision' },
  { value: 'unclassified', label: '미분류' }
]

// Only groups that actually have tools get a chip, so 미분류 stays invisible
// until an unrecognized model shows up — at which point it is the signal.
const groupChips = computed(() => {
  const counts = countByGroup(rows.value)
  return [
    { value: 'all' as const, label: '전체', count: rows.value.length },
    ...GROUP_LABELS
      .filter(group => counts.has(group.value))
      .map(group => ({ ...group, count: counts.get(group.value) ?? 0 }))
  ]
})

const visibleRows = computed(() => filterByGroup(rows.value, activeGroup.value))
const matrix = computed(() => buildPendingToolMatrix(visibleRows.value))

const selectGroup = (group: PendingToolGroup | 'all') => {
  activeGroup.value = group
  // The previous cell may not exist under the new filter.
  selectedCell.value = null
}

const selectCell = (fab: string, model: string) => {
  selectedCell.value = { fab, model }
}

const drilldownRows = computed(() => {
  const cell = selectedCell.value
  if (!cell) return []
  return [...cellRows(visibleRows.value, cell.fab, cell.model)]
    .sort((left, right) => Date.parse(right.updt_dt) - Date.parse(left.updt_dt))
})

// One `now` per render pass rather than per row, so every row in a table is
// judged against the same instant.
const now = computed(() => new Date())
const isStale = (row: PendingToolRow) => isStaleArrival(row.updt_dt, now.value)

const arrivalDate = (updtDt: string) => updtDt.slice(0, 10)

const copyIpList = async () => {
  const text = ipList(visibleRows.value)
  const ok = await copyTextToClipboard(text)
  toast.add(
    ok
      ? {
          title: `IP ${text.split('\n').length}건이 복사되었습니다`,
          icon: 'i-lucide-check',
          color: 'success'
        }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

const CSV_COLUMNS: Array<{ id: keyof PendingToolRow, header: string }> = [
  { id: 'fac_id', header: 'Fac' },
  { id: 'fab_name', header: 'Fab' },
  { id: 'eqp_id', header: 'Equipment ID' },
  { id: 'eqp_model_cd', header: 'Model' },
  { id: 'vendor_nm', header: 'Vendor' },
  { id: 'eqp_ip', header: 'IP Address' },
  { id: 'eqp_grp_id', header: 'Group' },
  { id: 'updt_dt', header: '반입일' }
]

const downloadPendingCsv = () => {
  downloadCsv(
    `pending-tools-${activeGroup.value}-${new Date().toISOString().slice(0, 10)}.csv`,
    CSV_COLUMNS.map(column => column.header),
    visibleRows.value.map(row => CSV_COLUMNS.map(column => row[column.id]))
  )
}
</script>
```

- [ ] **Step 4: Typecheck and lint**

```bash
npm --prefix front-dev-home run typecheck
npm --prefix front-dev-home run lint
npm --prefix front-dev-home test
```

Expected: all clean; 14 tests still pass.

- [ ] **Step 5: Verify in the running app**

Follow the `verify` skill. Start Flask and Nuxt:

```bash
.venv/bin/python index.py                  # :5050
npm --prefix front-dev-home run dev        # :3000
```

Then, driving Playwright MCP by hand (there is no E2E suite), confirm:

1. `/tool-roster` renders the idle state and the Network tab shows **no**
   request to `/api/sem-list/pending`. This is the requirement most easily
   broken by a stray `immediate: true`.
2. Clicking 조회 fetches once and renders the matrix; totals on both margins
   equal 14 under 전체.
3. The chip row shows CD-SEM, HV-SEM, VeritySEM and Provision. 미분류 is
   absent, because every mock model classifies.
4. `미배정` appears as the last fab row (the `PROVISION_10` tool).
5. The `VERITYSEM_4` tools show the 오래됨 badge; the others do not.
6. Selecting a cell opens the drill-down with IPs; `IP 목록 복사` toasts with
   the count matching the active filter, not the total.
7. Screenshots go to `.playwright-mcp/screenshots/`.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/composables/usePendingToolsApi.ts \
        front-dev-home/app/pages/tool-roster.vue \
        front-dev-home/app/utils/headerNav.ts
git commit -m "feat(tool-roster): 미연결 장비 screen for IT firewall requests

Fetches ON DEMAND only -- immediate: false, execute() on the 조회 button --
because v3_df_sem_list is the full company roster and is only wanted when
someone is actually preparing a request. The idle state says so, so an
un-fetched screen does not read as broken.

Tool-type chips scope both the matrix and IP 목록 복사, since an IT request is
filed per tool type rather than as one mixed list. A chip appears only for a
group that has tools, so 미분류 stays hidden until an unrecognized model shows
up -- at which point its presence is the signal."
```

---

## Task 6: Full verification and office handoff note

**Files:**

- Modify: `.remember/now.md` (session log; append, do not rewrite)

- [ ] **Step 1: Run every gate**

```bash
.venv/bin/python -m pytest -q
ruff check back_dev_home scripts
npm --prefix front-dev-home test
npm --prefix front-dev-home run typecheck
npm --prefix front-dev-home run lint
npm run lint:md
```

Expected: all green. `ruff check scripts` still reports the pre-existing
`F402` in `probe_recipe_ftp.py` — not introduced here.

- [ ] **Step 2: Confirm the office-provider path at least imports**

`office.py` does not exist at home, so the office branch cannot run. Confirm
the template imports cleanly and that mock mode is what actually resolves:

```bash
.venv/bin/python -c "from back_dev_home.sem_list.providers import office_example; print(office_example._ROSTER_KEY)"
curl -s -H 'Cookie: LASTUSER=local-dev' localhost:5050/api/health/providers | python -m json.tool | head -20
```

Expected: prints `v3_df_sem_list`; health output shows `sem_list` resolving to
`mock`.

- [ ] **Step 3: Note what the office session must do**

Append to `.remember/now.md`:

```markdown
## 미연결 장비 — office follow-up

1. `python -m scripts.inspect_redis_key v3_df_sem_list` — confirm the column
   list and clear the OFFICE-VERIFY marks in `docs/datatables/sem_list.txt`
   and `sem_list/MIGRATION.md`.
2. `python -m scripts.sync_office_adapters sem_list` — `office.py` is a
   gitignored copy and will be STALE (missing `get_pending_tools`), which
   fails the whole app factory on boot.
3. Check the real pending count. If it is dominated by tools that arrived
   years ago, the 180-day staleness threshold in
   `utils/pendingToolMatrix.ts` needs revisiting — it was a guess.
```

- [ ] **Step 4: Commit**

```bash
git add .remember/now.md
git commit -m "docs(remember): note office follow-up for 미연결 장비

office.py will be stale on the next office boot (no get_pending_tools), and
v3_df_sem_list's column list is still OFFICE-VERIFY."
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
| --- | --- |
| 별도 엔드포인트 | 2 |
| 계약 (`PendingToolRow`) | 1 |
| 차집합 기준 `eqp_id` | 3 |
| 백엔드 구성 표 (5 files) | 1, 2, 3 |
| mock 전략 (분할, 14대, 경계 조건) | 1 |
| `updt_dt` 분포 확대 | 1 |
| 프론트엔드 구성 표 (5 files) | 4, 5 |
| 온디맨드 조회 | 5 |
| tool type 필터 + 미분류 버킷 | 4, 5 |
| 미배정 버킷 | 4, 5 |
| 오래됨 표시 (180일) | 4, 5 |
| `·` for empty cells | 5 |
| `--sk-*` tokens only | 5 |
| 테스트 표 (5 rows) | 1, 2, 3, 4 |
| 문서 갱신 두 곳 | 1 (doc + mock together), 3 (MIGRATION) |

No gaps.

**Placeholder scan:** none — every code step carries the actual code, every
test step the actual assertions, and both threshold constants are concrete
(180 days, 14 tools, 300 tools).

**Type consistency:** `PendingToolRow`'s eight fields are identical across
`contracts.py` (Task 1), `office_example.py` (Task 3) and
`pendingToolMatrix.ts` (Task 4). `_select_pending` / `_normalize_pending` /
`_ROSTER_KEY` are named identically in Task 3's tests and implementation.
`get_pending_tools` is the same name in `mock.py`, `data.py`,
`office_example.py` and Task 2's route. The util's exports in Task 4's
Interfaces block match both its test imports and the page's imports in Task 5
(`buildPendingToolMatrix`, `cellRows`, `countByGroup`, `filterByGroup`,
`groupOf`, `ipList`, `isStaleArrival`, `UNASSIGNED_FAB`, `UNCLASSIFIED`,
`STALE_ARRIVAL_DAYS`, `fabLabel`).

One deliberate note: Task 1 Step 5 adds `get_pending_tools` to `data.py`,
which the file-structure table assigns to Task 2's territory. It lands in
Task 1 because Task 1's tests call `data.get_pending_tools()` and would
otherwise not run. Task 2 adds only the route.
