# Device-Statistics D22 — Plan 1: Data + Logic Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `recipe-params` mock dataset (per-recipe parameters with names + point-counts) and a pure within-device point-count outlier detector — the data and logic both UI surfaces in D22 consume.

**Architecture:** The backend ships RAW per-recipe parameter rows in the `RecipeInput` shape `ruleEngine.ts` already defines. The frontend computes everything client-side: R3 compliance reuses the existing `evaluateLot`; the new descriptive view uses a new pure `detectDeviceOutliers`. This plan builds the dataset + the one missing pure function. No UI yet (Plans 2–3).

**Tech Stack:** Flask blueprint mock (`back_dev_home`), deterministic-seeded Python generators, Nuxt 4 composable (`$fetch` + `joinApiPath`), pure TS utils tested with `node --test`.

---

## Context: where this sits in D22

Decision record: `docs/issues/ground_rules/grilling-log.md` **D22** (supersedes D15/D14/D16).

Three-plan split:

- **Plan 1 (this doc) — data + logic foundation.** `recipe-params` endpoint + composable + `detectDeviceOutliers` util. Testable on its own (endpoint returns data; util is unit-tested).
- **Plan 2 — descriptive view (all fabs).** Shared `device → recipe → parameter` drill-down component + device-statistics outlier integration. Consumes Plan 1.
- **Plan 3 — R3 rule page (prescriptive).** `measurement-rules` compliance device-table via `evaluateLot` + remove `_mfab_cells()` from `rules.py`. Consumes Plan 1.

## Existing pieces this plan relies on (do NOT rebuild)

- `front-dev-home/app/utils/ruleEngine.ts` — `RecipeInput`, `Parameter`, `evaluateLot`, `evaluateRecipe`. The `recipe-params` payload must match `RecipeInput` exactly (lines 39–51).
- `back_dev_home/ebeam/cdsem/device_statistics/statistics.py` — `_lot_index()` (lot_cd → fac_id), `_seed_for(lot_cd, idx)`, `_lot_ctn_desc()`. Reuse these for determinism + lot resolution.
- `back_dev_home/ebeam/cdsem/device_statistics/data.py` — the public surface that re-exports `statistics.py`. Routers import only from `data`.
- `back_dev_home/ebeam/cdsem/device_statistics/routes.py` — blueprint; mirror the `recipe_statistics` handler for the new endpoint.

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `back_dev_home/ebeam/cdsem/device_statistics/recipe_params.py` | Generate per-recipe parameter rows (RecipeInput shape) + `__main__` preview | Create |
| `back_dev_home/ebeam/cdsem/device_statistics/data.py` | Re-export `get_recipe_params`, `RecipeParamsRow` | Modify |
| `back_dev_home/ebeam/cdsem/device_statistics/routes.py` | `GET /recipe-params` handler | Modify |
| `docs/api-contracts/cdsem-device-statistics.yaml` | `RecipeParamsRow` type + endpoint entry | Modify |
| `docs/datatables/recipe_params.txt` | Korean datatable doc for the new dataset | Create |
| `front-dev-home/app/composables/useDeviceStatisticsApi.ts` | `fetchRecipeParams(lotCds)` | Modify |
| `front-dev-home/app/utils/outlierDetect.ts` | Pure `detectDeviceOutliers` | Create |
| `front-dev-home/app/utils/outlierDetect.test.ts` | Unit tests | Create |

> **Backend testing note:** there is no pytest in this repo. Backend modules self-verify via a `if __name__ == "__main__"` preview block run with `python -m ...` (the `statistics.py` convention). Frontend pure logic uses `node --test` (`npm run test`).

---

## Task 1: Backend — `recipe_params.py` generator

**Files:**
- Create: `back_dev_home/ebeam/cdsem/device_statistics/recipe_params.py`

- [ ] **Step 1: Write the generator module**

```python
"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

recipe-params 데이터 표면 (D22). device(lot_cd) 1개 = recipe 100~200개,
recipe 1개 = 파라미터 다수, 파라미터마다 측정 point 수가 다름. 프론트
ruleEngine.ts 의 RecipeInput 형태와 1:1 로 맞춥니다 (lot_cd, recipe_id,
fac_id, ctn_desc, prod_catg_cd, recipe_class, family, phase,
memory_class_auto, parameters[{name, point_count}]).

설계:  docs/issues/ground_rules/grilling-log.md (D22), rule-editor-structure.md §8-bis(B)
소비:  front-dev-home/app/utils/ruleEngine.ts (evaluateLot) · outlierDetect.ts (detectDeviceOutliers)

Phase 1 mock: lot 당 결정론적 seed 로 recipe·parameter 생성. 일부 recipe 에
의도적으로 (a) point-count outlier 와 (b) cap 위반 파라미터를 심어 두 소비처
(outlier 뷰 · R3 compliance)가 모두 실데이터로 검증되게 합니다.
"""

import random
from typing import Literal, TypedDict


class ParameterRow(TypedDict):
    name: str
    point_count: int


class RecipeParamsRow(TypedDict):
    lot_cd: str
    recipe_id: str
    fac_id: str
    ctn_desc: str
    prod_catg_cd: str
    recipe_class: Literal["Main", "Sample"]
    family: Literal["Core", "Pool", "VG_RTC_Cubic"]
    phase: Literal["t-EV", "EV", "TV", "PV"] | None
    memory_class_auto: Literal["DRAM", "NAND", "unknown"]
    parameters: list[ParameterRow]


# Recipes per device. Domain: 100~200 (D22).
RECIPE_COUNT_RANGE = (100, 200)

FAMILIES: tuple[str, ...] = ("Core", "Pool", "VG_RTC_Cubic")
PHASES: tuple[str, ...] = ("t-EV", "EV", "TV", "PV")

# Parameter-name templates per type, chosen to exercise ruleEngine.deriveType
# (longest-prefix EDGE_EX > EDGE > WAFER > LEVEL; everything else = OTHER).
WAFER_NAMES = ("WAFER_CD", "WAFER_2", "WAFER_OVL")
LEVEL_NAMES = ("LEVEL_1", "LEVEL_2", "LEVEL_3", "LEVEL_4")
EDGE_NAMES = ("EDGE_L", "EDGE_R", "EDGE_T", "EDGE_B")
EDGE_EX_NAMES = ("EDGE_EX_L", "EDGE_EX_R")
# OTHER bucket — the bag that balloons (D10). Includes a WAFER-companion
# (OVL_WF) so the Main DSPT/WF/WAFER name-override path is exercised.
OTHER_NAMES = ("OVL_X", "OVL_Y", "DSPT_1", "CD_BAR", "PITCH_A", "OVL_WF", "SPACE_1")

# Typical point counts per type (cap-respecting baseline so most recipes pass).
TYPICAL_POINTS = {
    "WAFER": (9, 13),
    "LEVEL": (1, 4),
    "EDGE": (6, 14),
    "EDGE_EX": (0, 0),
    "OTHER": (1, 8),
}


def _memory_class_auto(prod_catg_cd: str) -> str:
    c = prod_catg_cd.upper()
    if c == "DRAM":
        return "DRAM"
    if c in ("NAND", "FLASH"):
        return "NAND"
    return "unknown"  # Tech / Advanced / absent → 수동 (D7)


def _build_parameters(rng: random.Random, bloated: bool, over_measured: bool) -> list[ParameterRow]:
    params: list[ParameterRow] = []

    def add(name: str, lo: int, hi: int) -> None:
        params.append({"name": name, "point_count": rng.randint(lo, hi)})

    add(rng.choice(WAFER_NAMES), *TYPICAL_POINTS["WAFER"])
    for name in rng.sample(LEVEL_NAMES, rng.randint(1, 4)):
        add(name, *TYPICAL_POINTS["LEVEL"])
    for name in rng.sample(EDGE_NAMES, rng.randint(1, 4)):
        add(name, *TYPICAL_POINTS["EDGE"])

    # OTHER bag: normally a few; a "bloated" recipe carries many (D10 signal).
    other_pool = list(OTHER_NAMES)
    other_count = rng.randint(5, len(other_pool)) if bloated else rng.randint(1, 3)
    for i, name in enumerate(other_pool[:other_count]):
        suffix = f"_{i}" if i >= len(other_pool) else ""
        add(f"{name}{suffix}", *TYPICAL_POINTS["OTHER"])

    # over_measured recipe: push ONE EDGE param far above its peers so both the
    # within-device outlier detector and the R3 EDGE cap flag it.
    if over_measured and params:
        params[-1] = {"name": "EDGE_R", "point_count": rng.randint(40, 60)}

    return params


def _build_recipe(rng: random.Random, lot_cd: str, fac_id: str, prod_catg_cd: str, idx: int) -> RecipeParamsRow:
    recipe_class = "Sample" if rng.random() < 0.2 else "Main"
    family = rng.choice(FAMILIES)
    phase = rng.choice(PHASES)
    bloated = rng.random() < 0.08       # ~8% of recipes over-parameterized
    over_measured = rng.random() < 0.05  # ~5% with a point-count outlier
    parameters = _build_parameters(rng, bloated, over_measured)

    return {
        "lot_cd": lot_cd,
        "recipe_id": f"RCP-{lot_cd}-{idx:03d}",
        "fac_id": fac_id,
        "ctn_desc": f"{phase} {prod_catg_cd} {family} recipe {idx} lot {lot_cd}",
        "prod_catg_cd": prod_catg_cd,
        "recipe_class": recipe_class,
        "family": family,
        "phase": phase,
        "memory_class_auto": _memory_class_auto(prod_catg_cd),
        "parameters": parameters,
    }


def _prod_catg_for(lot_cd: str, fac_id: str) -> str:
    """Reuse the device's own prod_catg_cd when it is an R3 lot; M-fab device-desc
    rows carry no prod_catg_cd, so fall back to a deterministic pick."""
    from .data import get_r3_device_grp  # 지연 import — 순환 로드 방지
    for row in get_r3_device_grp():
        if row["lot_cd"] == lot_cd:
            return row["prod_catg_cd"]
    rng = random.Random(_recipe_seed(lot_cd, 9991))
    return rng.choice(["DRAM", "NAND", "FLASH", "Tech", "Advanced"])


def _recipe_seed(lot_cd: str, salt: int) -> int:
    from .statistics import _seed_for  # 지연 import
    return _seed_for(lot_cd, salt)


def get_recipe_params(lot_cds: list[str] | None = None) -> list[RecipeParamsRow]:
    """Flat list of recipe rows (RecipeInput shape) for the requested lots.

    Empty / None lot_cds → every known lot (can be large; callers should pass a
    selection). Deterministic per lot_cd via _seed_for."""
    from .statistics import _lot_index, _resolve_lots  # 지연 import
    index = _lot_index()
    selected = _resolve_lots(lot_cds)

    rows: list[RecipeParamsRow] = []
    for lot_cd in selected:
        fac_id = index[lot_cd]
        prod_catg_cd = _prod_catg_for(lot_cd, fac_id)
        rng = random.Random(_recipe_seed(lot_cd, 4242))
        count = rng.randint(*RECIPE_COUNT_RANGE)
        for idx in range(count):
            rows.append(_build_recipe(rng, lot_cd, fac_id, prod_catg_cd, idx))
    return rows


if __name__ == "__main__":
    # 미리보기:  python -m back_dev_home.ebeam.cdsem.device_statistics.recipe_params
    import pprint
    rows = get_recipe_params(["R000"])
    print(f"R000 recipes: {len(rows)}  (expect 100~200)")
    print("\n--- first recipe ---")
    pprint.pprint(rows[0])
    edge_outliers = [
        (r["recipe_id"], p["name"], p["point_count"])
        for r in rows for p in r["parameters"] if p["point_count"] >= 40
    ]
    print(f"\npoint-count outliers (>=40): {len(edge_outliers)}")
    for o in edge_outliers[:5]:
        print(" ", o)
    classes = {}
    for r in rows:
        classes[r["recipe_class"]] = classes.get(r["recipe_class"], 0) + 1
    print(f"\nrecipe_class split: {classes}")
```

- [ ] **Step 2: Run the preview to verify shape and seeded outliers**

Run: `python -m back_dev_home.ebeam.cdsem.device_statistics.recipe_params`
Expected: `R000 recipes:` a number between 100–200; first recipe prints all `RecipeInput` keys (`lot_cd … parameters`); `point-count outliers (>=40):` ≥ 1; `recipe_class split:` shows both `Main` and `Sample`.

- [ ] **Step 3: Re-run to confirm determinism**

Run the same command again. Expected: identical recipe count and identical first-recipe output (per-lot seeding is stable).

- [ ] **Step 4: Commit**

```bash
git add back_dev_home/ebeam/cdsem/device_statistics/recipe_params.py
git commit -m "feat(device-statistics): add recipe-params mock generator (D22)"
```

---

## Task 2: Backend — re-export + endpoint

**Files:**
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/data.py`
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/routes.py`

- [ ] **Step 1: Re-export from `data.py`**

In `data.py`, extend the trailing re-export block (currently importing from `.statistics`) with a sibling import from `.recipe_params`, and add the symbols to `__all__`:

```python
from .recipe_params import (  # noqa: E402  (의도된 후위 import)
    ParameterRow,
    RecipeParamsRow,
    get_recipe_params,
)
```

Add to the `__all__` list:

```python
    "RecipeParamsRow",
    "ParameterRow",
    "get_recipe_params",
```

- [ ] **Step 2: Add the route handler in `routes.py`**

Add `get_recipe_params` to the existing import from `...data`:

```python
from back_dev_home.ebeam.cdsem.device_statistics.data import (
    get_device_desc,
    get_r3_device_grp,
    get_recipe_params,
    get_weekly_trend_data,
)
```

Add the handler (mirror the `recipe_statistics` lot_cds parsing):

```python
@bp.get("/cdsem/device-statistics/recipe-params")
def recipe_params():
    lot_cds_param = request.args.get("lot_cds", "")
    lot_cds = [value.strip() for value in lot_cds_param.split(",") if value.strip()]
    return jsonify(get_recipe_params(lot_cds or None))
```

- [ ] **Step 3: Verify the endpoint serves**

Start the backend (user runs Flask on :5050 in PyCharm — if not already up, ask them to start it), then:

Run: `curl "http://localhost:5050/api/cdsem/device-statistics/recipe-params?lot_cds=R000" | python -m json.tool | head -40`
Expected: a JSON array; first element has keys `lot_cd, recipe_id, fac_id, ctn_desc, prod_catg_cd, recipe_class, family, phase, memory_class_auto, parameters`; `parameters[0]` has `name` + `point_count`.

- [ ] **Step 4: Commit**

```bash
git add back_dev_home/ebeam/cdsem/device_statistics/data.py back_dev_home/ebeam/cdsem/device_statistics/routes.py
git commit -m "feat(device-statistics): expose GET /recipe-params endpoint (D22)"
```

---

## Task 3: Docs — contract + datatable

**Files:**
- Modify: `docs/api-contracts/cdsem-device-statistics.yaml`
- Create: `docs/datatables/recipe_params.txt`

- [ ] **Step 1: Add the `RecipeParamsRow` type to the contract**

Under `types:` in `cdsem-device-statistics.yaml` (after `RuleCell`), add:

```yaml
  ParameterRow:
    name:
      type: string
      description: "Parameter name. Type derived by longest-prefix (EDGE_EX>EDGE>WAFER>LEVEL); else OTHER."
    point_count:
      type: integer

  RecipeParamsRow:
    description: One recipe with its measured parameters (D22). Matches ruleEngine.ts RecipeInput; consumed client-side by evaluateLot (R3 compliance) and detectDeviceOutliers (descriptive view).
    lot_cd:
      type: string
    recipe_id:
      type: string
      format: "RCP-<lot_cd>-NNN"
    fac_id:
      type: string
    ctn_desc:
      type: string
    prod_catg_cd:
      type: string
    recipe_class:
      type: string
      enum: ["Main", "Sample"]
    family:
      type: string
      enum: ["Core", "Pool", "VG_RTC_Cubic"]
    phase:
      type: string
      enum: ["t-EV", "EV", "TV", "PV", null]
    memory_class_auto:
      type: string
      enum: ["DRAM", "NAND", "unknown"]
    parameters:
      type: array
      items: ParameterRow
```

- [ ] **Step 2: Add the endpoint entry to the contract**

Under `endpoints:` (after the `rules` entry), add:

```yaml
  - path: /api/cdsem/device-statistics/recipe-params
    method: GET
    description: >
      Per-recipe parameter rows (name + point_count) for the selected lots (D22).
      Ships raw data only; violation/outlier judgement is client-side
      (ruleEngine.evaluateLot for R3, outlierDetect.detectDeviceOutliers for the descriptive view).
    query_params:
      lot_cds:
        type: string
        required: false
        description: Comma-separated lot codes (e.g. "R000,R001"). Empty = all lots (large).
    response:
      status: 200
      body:
        type: array
        items: RecipeParamsRow
```

- [ ] **Step 3: Write the datatable doc** (Korean, formal endings, per CLAUDE.md)

Create `docs/datatables/recipe_params.txt`:

```text
device-statistics 의 recipe-params mock data 입니다.

device(lot_cd) 1개는 recipe 100~200개를 가지며, recipe 1개는 파라미터 다수를
측정합니다. 파라미터마다 측정 point 수가 다릅니다. 프론트엔드 ruleEngine.ts 의
RecipeInput 형태와 1:1 로 맞춰 raw 로 내려보냅니다. 위반(R3 cap)·outlier 판정은
프론트엔드가 client-side 로 수행합니다 (백엔드는 raw 만 제공).

GET /api/cdsem/device-statistics/recipe-params?lot_cds=R000,R001

응답: RecipeParamsRow 배열 (recipe 당 1행)

컬럼 -> 타입: 설명

lot_cd -> string: device 식별자. r3-device-grp / device-desc 의 lot_cd 와 조인됩니다.
recipe_id -> string: recipe 식별자. 형식은 RCP-<lot_cd>-NNN 입니다.
fac_id -> string: fab 코드. R3 또는 M11~M16 입니다.
ctn_desc -> string: recipe 설명 문자열입니다.
prod_catg_cd -> string: 제품 카테고리. DRAM, NAND, FLASH, Tech, Advanced 중 하나입니다.
recipe_class -> string: Main 또는 Sample 입니다 (D2).
family -> string: Core, Pool, VG_RTC_Cubic 중 하나입니다 (D3).
phase -> string|null: t-EV, EV, TV, PV 또는 null 입니다 (D3).
memory_class_auto -> string: DRAM, NAND, unknown 중 하나입니다. Tech/Advanced 는 unknown(수동) 입니다 (D7).
parameters -> records: 측정 파라미터 배열입니다. 각 원소는 {name, point_count} 입니다.

parameters 원소
name -> string: 파라미터 이름. 타입은 longest-prefix(EDGE_EX > EDGE > WAFER > LEVEL)로 파생되며, 그 외는 OTHER 입니다.
point_count -> int: 해당 파라미터의 측정 point 수입니다.

Mock 생성 규칙
1. lot_cd 별 결정론적 seed(statistics._seed_for)로 recipe·parameter 를 생성합니다.
2. 약 8% recipe 는 기타(OTHER) 파라미터가 많은 bloated recipe 입니다 (D10 신호 검증용).
3. 약 5% recipe 는 EDGE point 수가 또래 대비 큰 outlier 를 포함합니다 (outlier 뷰·R3 cap 검증용).
```

- [ ] **Step 4: Lint the markdown is not required for `.txt`, but commit**

```bash
git add docs/api-contracts/cdsem-device-statistics.yaml docs/datatables/recipe_params.txt
git commit -m "docs(device-statistics): contract + datatable for recipe-params (D22)"
```

---

## Task 4: Frontend — `fetchRecipeParams` composable

**Files:**
- Modify: `front-dev-home/app/composables/useDeviceStatisticsApi.ts`

- [ ] **Step 1: Add the fetch function**

Import the `RecipeInput` type and add `fetchRecipeParams`. At the top of the file:

```ts
import { joinApiPath } from '~/utils/apiPath'
import type { RecipeInput } from '~/utils/ruleEngine'
```

Inside `useDeviceStatisticsApi`, add (and return) the function:

```ts
  const fetchRecipeParams = async (lotCds: string[] = []): Promise<RecipeInput[]> => {
    const query = lotCds.length > 0 ? { lot_cds: lotCds.join(',') } : undefined

    return await $fetch<RecipeInput[]>(
      joinApiPath(base, '/cdsem/device-statistics/recipe-params'),
      { query }
    )
  }
```

Add `fetchRecipeParams` to the returned object:

```ts
  return {
    fetchR3DeviceGrp,
    fetchDeviceDesc,
    fetchRecipeParams
  }
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: PASS — no errors. (`RecipeInput` resolves from `ruleEngine.ts`; the payload shape matches.)

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/useDeviceStatisticsApi.ts
git commit -m "feat(device-statistics): fetchRecipeParams composable (D22)"
```

---

## Task 5: Frontend — `detectDeviceOutliers` pure util (TDD)

Within-device, point-count, multiplier baseline (D22 / Q3): a parameter is an outlier when its `point_count` exceeds `multiplier × median(all point_counts in the device)`.

**Files:**
- Create: `front-dev-home/app/utils/outlierDetect.test.ts`
- Create: `front-dev-home/app/utils/outlierDetect.ts`

- [ ] **Step 1: Write the failing tests**

Create `front-dev-home/app/utils/outlierDetect.test.ts`:

```ts
// Pure-logic tests for outlierDetect. Run: node --test app/utils/outlierDetect.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { detectDeviceOutliers, DEFAULT_OUTLIER_MULTIPLIER } from './outlierDetect.ts'
import type { RecipeInput } from './ruleEngine.ts'

const recipe = (recipe_id: string, points: number[]): RecipeInput => ({
  lot_cd: 'R000',
  recipe_id,
  fac_id: 'R3',
  ctn_desc: '',
  prod_catg_cd: 'DRAM',
  recipe_class: 'Main',
  family: 'Core',
  phase: 'EV',
  memory_class_auto: 'DRAM',
  parameters: points.map((point_count, i) => ({ name: `P_${i}`, point_count }))
})

test('empty device → median 0, no outliers', () => {
  const r = detectDeviceOutliers([])
  assert.equal(r.median, 0)
  assert.equal(r.outlier_count, 0)
  assert.deepEqual(r.outliers, [])
})

test('uniform point counts → no outliers', () => {
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10]), recipe('B', [10, 10])])
  assert.equal(r.median, 10)
  assert.equal(r.outlier_count, 0)
})

test('a single high value is flagged with its recipe_id and name', () => {
  // medians of [10,10,10,10,50] = 10; threshold = 2*10 = 20; 50 > 20.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [50])])
  assert.equal(r.median, 10)
  assert.equal(r.threshold, 20)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.recipe_id, 'B')
  assert.equal(r.outliers[0]?.point_count, 50)
  assert.equal(r.outliers[0]?.name, 'P_0')
})

test('value exactly at threshold is NOT an outlier (strictly greater)', () => {
  // median 10, threshold 20, a 20 must not flag.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [20])])
  assert.equal(r.outlier_count, 0)
})

test('multiplier is configurable', () => {
  // median 10, multiplier 4 → threshold 40; 30 does not flag, 50 does.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [30, 50])], 4)
  assert.equal(r.threshold, 40)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.point_count, 50)
})

test('default multiplier is 2', () => {
  assert.equal(DEFAULT_OUTLIER_MULTIPLIER, 2)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd front-dev-home && node --test app/utils/outlierDetect.test.ts`
Expected: FAIL — `Cannot find module './outlierDetect.ts'`.

- [ ] **Step 3: Write the implementation**

Create `front-dev-home/app/utils/outlierDetect.ts`:

```ts
// Within-device point-count outlier detection (D22 / grilling Q3).
// Baseline = all parameter point_counts across one device's recipes.
// A parameter is an outlier when point_count > multiplier × median.
// Pure + framework-free (mirrors ruleEngine.ts), unit-tested with node --test.
import type { RecipeInput } from './ruleEngine'

export const DEFAULT_OUTLIER_MULTIPLIER = 2

export interface PointOutlier {
  recipe_id: string
  name: string
  point_count: number
}

export interface DeviceOutlierResult {
  median: number
  threshold: number
  outliers: PointOutlier[]
  outlier_count: number
}

const median = (values: number[]): number => {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1]! + sorted[mid]!) / 2
    : sorted[mid]!
}

export const detectDeviceOutliers = (
  recipes: RecipeInput[],
  multiplier: number = DEFAULT_OUTLIER_MULTIPLIER
): DeviceOutlierResult => {
  const allPoints = recipes.flatMap(r => r.parameters.map(p => p.point_count))
  const med = median(allPoints)
  const threshold = med * multiplier

  const outliers: PointOutlier[] = []
  for (const r of recipes) {
    for (const p of r.parameters) {
      if (p.point_count > threshold) {
        outliers.push({ recipe_id: r.recipe_id, name: p.name, point_count: p.point_count })
      }
    }
  }
  return { median: med, threshold, outliers, outlier_count: outliers.length }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/outlierDetect.test.ts`
Expected: PASS — all 6 tests green.

- [ ] **Step 5: Typecheck + full test suite**

Run: `cd front-dev-home && npm run typecheck && npm run test`
Expected: PASS (existing `ruleEngine.test.ts` still green; new tests included via the `app/**/*.test.ts` glob).

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/outlierDetect.ts front-dev-home/app/utils/outlierDetect.test.ts
git commit -m "feat(device-statistics): within-device point-count outlier detector (D22)"
```

---

## Self-Review

- **Spec coverage:** D22's data prerequisite (`recipe-params`, §8-bis B) → Tasks 1–4. The new pure logic (within-device, point-count, multiplier outlier — Q3) → Task 5. R3 compliance needs no new logic (`evaluateLot` exists) — deferred to Plan 3. `_mfab_cells()` removal → Plan 3 (coupled to the rule-page rework). UI surfaces → Plans 2–3.
- **Type consistency:** `RecipeParamsRow` (Python TypedDict) mirrors `RecipeInput` (TS) field-for-field; `parameters` items `{name, point_count}` == `Parameter`. `detectDeviceOutliers` consumes `RecipeInput[]` (the composable's return type), so the chain composable → util typechecks.
- **No placeholders:** every step has runnable code/commands and concrete expected output. Backend "tests" are preview-block + curl runs (no pytest in repo, stated up front).

---

## Roadmap — Plans 2 & 3 (to be written after Plan 1 lands)

**Plan 2 — Descriptive view (all fabs).**
- `components/ebeam/devstat/DrillDown.vue` (or similar) — shared `device → recipe → parameter` cascade; a `highlight` prop swaps the per-parameter emphasis (outlier vs cap-violation) so Plan 3 reuses it.
- Device-statistics integration: per selected device, call `fetchRecipeParams`, run `detectDeviceOutliers`, surface the device-row outlier count + drill-down. 기타(OTHER) params expanded in the parameter level.
- Decide at build: device-row unit (outlier params vs outlier-containing recipes) — D22 open item ②.

**Plan 3 — R3 rule page (prescriptive).**
- `measurement-rules.vue`: keep the static cap matrix (D21); add an R3 compliance device-table driven by `evaluateLot(lot, recipes, cells)` → violated-recipe **count** (D22, not ratio). Reuse the Plan 2 drill-down with `highlight="violation"`.
- Remove `_mfab_cells()` + M-fab seed from `rules.py`; `get_rules` / `list_rule_fabs` → R3 only. Update `MeasurementRulesView.vue` (drop the M-fab branch + `mfabNote`) and the `rules` contract note.
- Decide at build: whether the compliance row keeps a health color (D16 ratio thresholds are void — D22 open item ③).
```
