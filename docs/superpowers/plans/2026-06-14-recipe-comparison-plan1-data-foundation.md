# Recipe Comparison — Plan 1: Data + Logic Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data + pure-logic layer for recipe comparison — a batch backend endpoint, a fetch composable, and all comparison math (overlap, diff, grouping, Excel workbook shape) as tested pure functions. No UI.

**Architecture:** Flask `POST /<slug>/recipe-search/compare` returns one compact entry per recipe (only IDP + image filenames + AMP per parameter), reusing the existing seeded `get_recipe_open_data` so a recipe's compare payload matches its open payload. The frontend fetches via `useRecipeCompareApi`; all derivations (overlap/coverage, diff detection, value grouping, workbook builder) live in pure functions in `utils/recipeCompare.ts`, unit-tested with Node's test runner.

**Tech Stack:** Flask (mock backend), Nuxt 4 `$fetch`, TypeScript, `node --test`.

---

## Key decisions (confirm before coding)

- Comparison is scoped to one `(toolType, fab)`. The endpoint takes a recipe-name list + fab.
- Parameter identity is the `Parameter` string. Within one recipe, duplicate `Parameter` rows are deduped (first occurrence wins for IDP/images; its AMP rows, first-per-slot, win downstream). This is acceptable for the mock generator.
- Pure functions only in `utils/recipeCompare.ts` — no Vue, no `xlsx` (the library write lands in Plan 3). `buildCompareWorkbook` returns a plain `{ sheets: [{ name, rows }] }` shape that is fully testable.

---

### Task 1: Backend `get_recipe_compare_data`

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/data.py`

- [ ] **Step 1: Add the compare TypedDicts and projection function**

Add to `data.py`. Place the TypedDicts after `RecipeDetailResponse` (around line 135) and the function after `get_recipe_open_data`:

```python
COMPARE_IDP_FIELDS: tuple[str, ...] = (
    "Addressing", "Double_Addressing", "Mother_Para",
    "Region", "Meas_Counting", "dnumber_removed"
)


class CompareParameter(TypedDict):
    Parameter: str
    idp: dict[str, object]
    images: dict[str, str]
    amp: list[AmpRow]


class CompareRecipe(TypedDict):
    recipe_id: str
    fac_id: str
    parameters: list[CompareParameter]


class RecipeCompareResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    recipes: list[CompareRecipe]


def get_recipe_compare_data(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_names: list[str]
) -> RecipeCompareResponse:
    """Compact per-recipe comparison payload: IDP fields + slot image filenames +
    AMP rows per parameter. Reuses get_recipe_open_data so compare matches open."""
    recipes: list[CompareRecipe] = []
    for name in recipe_names:
        clean = (name or "").strip()
        if not clean:
            continue
        detail = get_recipe_open_data(
            recipe_id=clean, fac_id=fab_name, tool_category=tool_type
        )
        amp_by_param: dict[str, list[AmpRow]] = {}
        for amp in detail["amp_info"]:
            amp_by_param.setdefault(amp["parameter"], []).append(amp)

        seen: set[str] = set()
        parameters: list[CompareParameter] = []
        for idp in detail["idp_image_info"]:
            param = idp["Parameter"]
            if param in seen:
                continue
            seen.add(param)
            parameters.append({
                "Parameter": param,
                "idp": {field: idp[field] for field in COMPARE_IDP_FIELDS},
                "images": {slot["key"]: idp[slot["key"]] for slot in IMAGE_SLOTS},
                "amp": amp_by_param.get(param, [])
            })
        recipes.append({
            "recipe_id": detail["recipe_id"],
            "fac_id": detail["fac_id"],
            "parameters": parameters
        })

    return {"tool_type": tool_type, "fab_name": fab_name, "recipes": recipes}
```

- [ ] **Step 2: Export the new symbols**

In the `__all__` list at the top of `data.py`, add these entries (keep alphabetical-ish ordering with the existing ones):

```python
    "CompareParameter",
    "CompareRecipe",
    "RecipeCompareResponse",
    "get_recipe_compare_data",
```

- [ ] **Step 3: Verify with a `python -c` check**

Run from the repo root (uses the project venv on PATH):

```bash
python -c "from back_dev_home.ebeam.hitachi.recipe_search.data import get_recipe_compare_data; r = get_recipe_compare_data('cd-sem', 'R3', ['RACE/DEAE_ABC123_STD_00012', 'ABC/123_MAIN_ABC123_STD_00045']); assert len(r['recipes']) == 2; p = r['recipes'][0]['parameters'][0]; assert set(p) == {'Parameter','idp','images','amp'}; assert set(p['idp']) == {'Addressing','Double_Addressing','Mother_Para','Region','Meas_Counting','dnumber_removed'}; assert set(p['images']) == {'img_add1','img_add2','image_add3','img_meas1','img_meas2'}; assert all(a['parameter']==p['Parameter'] for a in p['amp']); print('OK', len(r['recipes'][0]['parameters']), 'params,', len(p['amp']), 'amp rows on first param')"
```

Expected: `OK <n> params, <m> amp rows on first param` (no AssertionError).

- [ ] **Step 4: Verify compare matches open for the same recipe**

```bash
python -c "from back_dev_home.ebeam.hitachi.recipe_search.data import get_recipe_compare_data, get_recipe_open_data; name='ABC/123_MAIN_ABC123_STD_00045'; o=get_recipe_open_data(recipe_id=name, fac_id='R3', tool_category='cd-sem'); c=get_recipe_compare_data('cd-sem','R3',[name]); op={r['Parameter'] for r in o['idp_image_info']}; cp={p['Parameter'] for p in c['recipes'][0]['parameters']}; assert cp==op, (cp, op); print('OK parameter sets match:', sorted(cp))"
```

Expected: `OK parameter sets match: [...]`.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/data.py
git commit -m "feat(recipe-compare): add get_recipe_compare_data projection"
```

---

### Task 2: Backend `POST /compare` route

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/routes.py`

- [ ] **Step 1: Import the new function**

Change the import line at the top of `routes.py` from:

```python
from back_dev_home.ebeam.hitachi.recipe_search.data import ToolType, get_recipe_catalog, get_recipe_open_data
```

to:

```python
from back_dev_home.ebeam.hitachi.recipe_search.data import (
    ToolType,
    get_recipe_catalog,
    get_recipe_compare_data,
    get_recipe_open_data,
)
```

- [ ] **Step 2: Add the route handler**

Append to `routes.py`:

```python
@bp.post("/<tool_slug>/recipe-search/compare")
def recipe_search_compare(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    payload = request.get_json(silent=True) or {}
    recipe_names = payload.get("recipe_names")
    if not isinstance(recipe_names, list) or not recipe_names:
        return jsonify({"error": "recipe_names must be a non-empty list"}), 400

    fab_name = (payload.get("fab_name") or "").strip().upper() or None
    return jsonify(
        get_recipe_compare_data(tool_type, fab_name, [str(name) for name in recipe_names])
    )
```

- [ ] **Step 3: Verify with curl against the running Flask server**

With Flask running on :5050 (the user runs it in PyCharm), run:

```bash
curl -s -X POST "http://localhost:5050/api/cdsem/recipe-search/compare" -H "Content-Type: application/json" -d "{\"fab_name\":\"R3\",\"recipe_names\":[\"ABC/123_MAIN_ABC123_STD_00045\",\"RACE/DEAE_ABC123_STD_00012\"]}" | head -c 400
```

Expected: JSON beginning `{"fab_name":"R3","recipes":[{"fac_id":"R3","parameters":[...`. If the server is not running, ask the user to start it (`! python index.py` or via PyCharm) and re-run.

- [ ] **Step 4: Verify the error path**

```bash
curl -s -X POST "http://localhost:5050/api/cdsem/recipe-search/compare" -H "Content-Type: application/json" -d "{\"fab_name\":\"R3\",\"recipe_names\":[]}"
```

Expected: `{"error":"recipe_names must be a non-empty list"}` with HTTP 400.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/routes.py
git commit -m "feat(recipe-compare): add POST compare endpoint"
```

---

### Task 3: Frontend compare types + `useRecipeCompareApi`

**Files:**
- Create: `front-dev-home/app/composables/useRecipeCompareApi.ts`

- [ ] **Step 1: Write the composable**

Mirror `useRecipeSearchApi`'s in-flight dedup and `joinApiPath`/`apiBase` usage. `ImageSlotKey` is imported from `~/utils/recipeView`.

```typescript
import { joinApiPath } from '~/utils/apiPath'
import type { AmpRow, RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import type { ImageSlotKey } from '~/utils/recipeView'

export interface CompareIdpFields {
  Addressing: string
  Double_Addressing: boolean
  Mother_Para: string
  Region: number
  Meas_Counting: number
  dnumber_removed: number
}

export interface CompareParameter {
  Parameter: string
  idp: CompareIdpFields
  images: Record<ImageSlotKey, string>
  amp: AmpRow[]
}

export interface CompareRecipe {
  recipe_id: string
  fac_id: string
  parameters: CompareParameter[]
}

export interface RecipeCompareResponse {
  tool_type: RecipeSearchToolType
  fab_name: string | null
  recipes: CompareRecipe[]
}

export interface RecipeCompareParams {
  toolType: RecipeSearchToolType
  fabName?: string
  recipeNames: string[]
}

const TOOL_TO_BACKEND_SLUG: Record<RecipeSearchToolType, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem'
}

const inFlightCompares = new Map<string, Promise<RecipeCompareResponse>>()

export const useRecipeCompareApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchCompare = async (params: RecipeCompareParams): Promise<RecipeCompareResponse> => {
    const slug = TOOL_TO_BACKEND_SLUG[params.toolType]
    const fabName = params.fabName?.trim().toUpperCase()
    const names = params.recipeNames.map(name => name.trim()).filter(Boolean)
    const cacheKey = `${params.toolType}:${fabName || 'ALL'}:${[...names].sort().join('|')}`
    const existing = inFlightCompares.get(cacheKey)

    if (existing) {
      return await existing
    }

    const request = $fetch<RecipeCompareResponse>(
      joinApiPath(base, `/${slug}/recipe-search/compare`),
      {
        method: 'POST',
        body: { recipe_names: names, ...(fabName ? { fab_name: fabName } : {}) }
      }
    ).finally(() => {
      inFlightCompares.delete(cacheKey)
    })

    inFlightCompares.set(cacheKey, request)
    return await request
  }

  return { fetchCompare }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no errors referencing `useRecipeCompareApi.ts`.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/useRecipeCompareApi.ts
git commit -m "feat(recipe-compare): add useRecipeCompareApi composable"
```

---

### Task 4: Pure util — overlap + coverage

**Files:**
- Create: `front-dev-home/app/utils/recipeCompare.ts`
- Test: `front-dev-home/app/utils/recipeCompare.test.ts`

- [ ] **Step 1: Write the failing test**

Create `recipeCompare.test.ts`:

```typescript
// Pure-logic tests for recipeCompare. Run: node --test app/utils/recipeCompare.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildOverlap,
  classifyCoverage,
  filterOverlap,
  commonParameters
} from './recipeCompare.ts'
import type { CompareRecipe, CompareParameter } from '../composables/useRecipeCompareApi.ts'

const param = (name: string): CompareParameter => ({
  Parameter: name,
  idp: {
    Addressing: 'Yes', Double_Addressing: false, Mother_Para: 'Para_1',
    Region: 1, Meas_Counting: 1, dnumber_removed: 0
  },
  images: { img_add1: 'a1', img_add2: 'a2', image_add3: 'a3', img_meas1: 'm1', img_meas2: 'm2' },
  amp: []
})

const recipe = (id: string, params: string[]): CompareRecipe => ({
  recipe_id: id, fac_id: 'R3', parameters: params.map(param)
})

test('classifyCoverage: all / unique / partial', () => {
  assert.equal(classifyCoverage(3, 3), 'all')
  assert.equal(classifyCoverage(1, 3), 'unique')
  assert.equal(classifyCoverage(2, 3), 'partial')
})

test('buildOverlap marks shared, partial, unique parameters', () => {
  const rows = buildOverlap([
    recipe('A', ['WAFER', 'P5', 'P8']),
    recipe('B', ['WAFER', 'P5']),
    recipe('C', ['WAFER', 'P12'])
  ])
  const byName = Object.fromEntries(rows.map(r => [r.parameter, r]))
  assert.equal(byName.WAFER.coverage, 'all')
  assert.deepEqual(byName.WAFER.presentIn, ['A', 'B', 'C'])
  assert.equal(byName.P5.coverage, 'partial')
  assert.equal(byName.P8.coverage, 'unique')
  assert.equal(byName.P12.coverage, 'unique')
})

test('buildOverlap dedupes a repeated parameter within one recipe', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'WAFER'])])
  assert.equal(rows.length, 1)
  assert.equal(rows[0]?.count, 1)
})

test('filterOverlap + commonParameters', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'P5']), recipe('B', ['WAFER'])])
  assert.deepEqual(filterOverlap(rows, 'common').map(r => r.parameter), ['WAFER'])
  assert.deepEqual(filterOverlap(rows, 'unique').map(r => r.parameter), ['P5'])
  assert.deepEqual(filterOverlap(rows, 'all').map(r => r.parameter), ['WAFER', 'P5'])
  assert.deepEqual(commonParameters(rows), ['WAFER'])
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: FAIL — cannot find module `./recipeCompare.ts` / exports undefined.

- [ ] **Step 3: Write minimal implementation**

Create `recipeCompare.ts`:

```typescript
import type { CompareRecipe } from '~/composables/useRecipeCompareApi'

export const GROUPING_DEFAULT_THRESHOLD = 8
export const OUTLIER_SHARE = 0.25

export type Coverage = 'all' | 'partial' | 'unique'
export type CoverageFilter = 'all' | 'common' | 'partial' | 'unique'

export interface OverlapRow {
  parameter: string
  presentIn: string[]
  count: number
  total: number
  coverage: Coverage
}

export function classifyCoverage(count: number, total: number): Coverage {
  if (total > 0 && count === total) return 'all'
  if (count <= 1) return 'unique'
  return 'partial'
}

export function buildOverlap(recipes: CompareRecipe[]): OverlapRow[] {
  const total = recipes.length
  const order: string[] = []
  const present = new Map<string, Set<string>>()

  for (const recipe of recipes) {
    const seenInRecipe = new Set<string>()
    for (const p of recipe.parameters) {
      if (seenInRecipe.has(p.Parameter)) continue
      seenInRecipe.add(p.Parameter)
      if (!present.has(p.Parameter)) {
        present.set(p.Parameter, new Set())
        order.push(p.Parameter)
      }
      present.get(p.Parameter)!.add(recipe.recipe_id)
    }
  }

  return order.map((parameter) => {
    const ids = present.get(parameter)!
    return {
      parameter,
      presentIn: recipes.filter(r => ids.has(r.recipe_id)).map(r => r.recipe_id),
      count: ids.size,
      total,
      coverage: classifyCoverage(ids.size, total)
    }
  })
}

export function filterOverlap(rows: OverlapRow[], filter: CoverageFilter): OverlapRow[] {
  if (filter === 'all') return rows
  const want: Coverage = filter === 'common' ? 'all' : filter
  return rows.filter(r => r.coverage === want)
}

export function commonParameters(rows: OverlapRow[]): string[] {
  return rows.filter(r => r.coverage === 'all').map(r => r.parameter)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/recipeCompare.ts front-dev-home/app/utils/recipeCompare.test.ts
git commit -m "feat(recipe-compare): overlap + coverage classification util"
```

---

### Task 5: Pure util — matrix rows + diff

**Files:**
- Modify: `front-dev-home/app/utils/recipeCompare.ts`
- Modify: `front-dev-home/app/utils/recipeCompare.test.ts`

- [ ] **Step 1: Add the failing tests**

Append to `recipeCompare.test.ts` (and extend the import at the top to add `buildIdpRows, buildAmpRows, cellsDiffer, imageFilenames`):

```typescript
import {
  buildIdpRows, buildAmpRows, cellsDiffer, imageFilenames
} from './recipeCompare.ts'
import type { AmpRow } from '../composables/useRecipeSearchApi.ts'

const measAmp = (over: Partial<AmpRow>): AmpRow => ({
  parameter: 'WAFER', slot: 'img_meas1', role: 'measure', stage: 'Measure 1',
  Mag: '50.0K', Vacc: '800', I_probe: '200', Frame: '8', Scan: 'TV', WD: '5.0', Det: 'SE',
  Template: null, MatchScore: null, SearchArea: null, Rotation: null,
  Algo: 'Linear', ROI: '512', EdgeThr: '50', EdgeDir: 'L->R', Smooth: 'Off', ...over
})

const recipeWithAmp = (id: string, amp: AmpRow[]): CompareRecipe => ({
  recipe_id: id, fac_id: 'R3',
  parameters: [{
    Parameter: 'WAFER',
    idp: { Addressing: 'Yes', Double_Addressing: false, Mother_Para: 'P1', Region: 5, Meas_Counting: 3, dnumber_removed: 0 },
    images: { img_add1: 'a1', img_add2: 'a2', image_add3: 'a3', img_meas1: `${id}_m1`, img_meas2: 'm2' },
    amp
  }]
})

test('cellsDiffer: equal values agree, one different differs', () => {
  assert.equal(cellsDiffer(['50K', '50K', '50K']), false)
  assert.equal(cellsDiffer(['50K', '80K', '50K']), true)
  assert.equal(cellsDiffer(['x']), false)
})

test('buildAmpRows aligns values per recipe and flags differing rows', () => {
  const rows = buildAmpRows([
    recipeWithAmp('A', [measAmp({ Mag: '50.0K', Algo: 'Linear' })]),
    recipeWithAmp('B', [measAmp({ Mag: '80.0K', Algo: 'Linear' })])
  ], 'WAFER', 'img_meas1')
  const mag = rows.find(r => r.key === 'Mag')!
  const algo = rows.find(r => r.key === 'Algo')!
  assert.deepEqual(mag.values, ['50.0K', '80.0K'])
  assert.equal(mag.differs, true)
  assert.equal(algo.differs, false)
})

test('buildAmpRows shows 없음 when a recipe lacks the parameter', () => {
  const withWafer = recipeWithAmp('A', [measAmp({})])
  const without: CompareRecipe = { recipe_id: 'B', fac_id: 'R3', parameters: [] }
  const rows = buildAmpRows([withWafer, without], 'WAFER', 'img_meas1')
  assert.equal(rows.find(r => r.key === 'Mag')!.values[1], '없음')
})

test('buildIdpRows compares per-parameter fields', () => {
  const rows = buildIdpRows([
    recipeWithAmp('A', []),
    { recipe_id: 'B', fac_id: 'R3', parameters: [{
      Parameter: 'WAFER',
      idp: { Addressing: 'Yes', Double_Addressing: false, Mother_Para: 'P1', Region: 8, Meas_Counting: 3, dnumber_removed: 0 },
      images: { img_add1: '', img_add2: '', image_add3: '', img_meas1: '', img_meas2: '' },
      amp: []
    }] }
  ], 'WAFER')
  assert.equal(rows.find(r => r.key === 'Region')!.differs, true)
  assert.equal(rows.find(r => r.key === 'Addressing')!.differs, false)
})

test('imageFilenames returns per-recipe slot filename or null', () => {
  const files = imageFilenames([
    recipeWithAmp('A', []),
    { recipe_id: 'B', fac_id: 'R3', parameters: [] }
  ], 'WAFER', 'img_meas1')
  assert.deepEqual(files, ['A_m1', null])
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: FAIL — `buildIdpRows`/`buildAmpRows`/`cellsDiffer`/`imageFilenames` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `recipeCompare.ts` (and add the imports shown at the top):

```typescript
import type { CompareIdpFields, CompareParameter } from '~/composables/useRecipeCompareApi'
import {
  IMAGE_SLOTS,
  ampFieldsForRole,
  formatAmpValue,
  type ImageSlotKey
} from '~/utils/recipeView'

const MISSING = '없음'

export interface MatrixRow {
  key: string
  label: string
  unit?: string
  values: string[]
  differs: boolean
}

interface IdpFieldDescriptor {
  key: keyof CompareIdpFields
  label: string
}

export const IDP_COMPARE_FIELDS: readonly IdpFieldDescriptor[] = [
  { key: 'Addressing', label: 'Addressing' },
  { key: 'Double_Addressing', label: 'Double_Addressing' },
  { key: 'Mother_Para', label: 'Mother_Para' },
  { key: 'Region', label: 'Region' },
  { key: 'Meas_Counting', label: 'Meas_Counting' },
  { key: 'dnumber_removed', label: 'dnumber_removed' }
]

export function cellsDiffer(values: string[]): boolean {
  if (values.length < 2) return false
  return values.some(v => v !== values[0])
}

export function findParameter(recipe: CompareRecipe, parameter: string): CompareParameter | null {
  return recipe.parameters.find(p => p.Parameter === parameter) ?? null
}

export function buildIdpRows(recipes: CompareRecipe[], parameter: string): MatrixRow[] {
  return IDP_COMPARE_FIELDS.map((field) => {
    const values = recipes.map((recipe) => {
      const p = findParameter(recipe, parameter)
      if (!p) return MISSING
      const v = p.idp[field.key]
      return v === null || v === undefined || v === '' ? '—' : String(v)
    })
    return { key: String(field.key), label: field.label, values, differs: cellsDiffer(values) }
  })
}

export function buildAmpRows(
  recipes: CompareRecipe[],
  parameter: string,
  slot: ImageSlotKey
): MatrixRow[] {
  const descriptor = IMAGE_SLOTS.find(s => s.key === slot)
  if (!descriptor) return []
  return ampFieldsForRole(descriptor.role).map((field) => {
    const values = recipes.map((recipe) => {
      const p = findParameter(recipe, parameter)
      if (!p) return MISSING
      const amp = p.amp.find(a => a.slot === slot) ?? null
      if (!amp) return MISSING
      return formatAmpValue(amp[field.key])
    })
    return { key: String(field.key), label: field.label, unit: field.unit, values, differs: cellsDiffer(values) }
  })
}

export function imageFilenames(
  recipes: CompareRecipe[],
  parameter: string,
  slot: ImageSlotKey
): (string | null)[] {
  return recipes.map((recipe) => {
    const p = findParameter(recipe, parameter)
    return p ? (p.images[slot] ?? null) : null
  })
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/recipeCompare.ts front-dev-home/app/utils/recipeCompare.test.ts
git commit -m "feat(recipe-compare): matrix rows + diff detection util"
```

---

### Task 6: Pure util — value grouping / outlier

**Files:**
- Modify: `front-dev-home/app/utils/recipeCompare.ts`
- Modify: `front-dev-home/app/utils/recipeCompare.test.ts`

- [ ] **Step 1: Add the failing tests**

Append to `recipeCompare.test.ts` (extend the import to add `groupFieldValues`):

```typescript
import { groupFieldValues } from './recipeCompare.ts'

test('groupFieldValues sorts buckets by count desc', () => {
  const buckets = groupFieldValues([
    { recipeId: 'A', value: '50K' }, { recipeId: 'B', value: '80K' },
    { recipeId: 'C', value: '50K' }, { recipeId: 'D', value: '50K' }
  ])
  assert.deepEqual(buckets.map(b => b.value), ['50K', '80K'])
  assert.deepEqual(buckets[0]?.recipeIds, ['A', 'C', 'D'])
})

test('groupFieldValues flags a small minority as outlier', () => {
  const pairs = [
    ...Array.from({ length: 62 }, (_, i) => ({ recipeId: `a${i}`, value: '50K' })),
    ...Array.from({ length: 31 }, (_, i) => ({ recipeId: `b${i}`, value: '80K' })),
    ...Array.from({ length: 7 }, (_, i) => ({ recipeId: `c${i}`, value: '100K' }))
  ]
  const buckets = groupFieldValues(pairs)
  const byValue = Object.fromEntries(buckets.map(b => [b.value, b]))
  assert.equal(byValue['50K'].isOutlier, false) // largest
  assert.equal(byValue['80K'].isOutlier, false) // 0.31 share > 0.25
  assert.equal(byValue['100K'].isOutlier, true)  // 0.07 share <= 0.25
})

test('groupFieldValues flags nothing on a tie for largest', () => {
  const buckets = groupFieldValues([
    { recipeId: 'A', value: 'x' }, { recipeId: 'B', value: 'y' }
  ])
  assert.equal(buckets.every(b => !b.isOutlier), true)
})

test('groupFieldValues: single value is never an outlier', () => {
  const buckets = groupFieldValues([{ recipeId: 'A', value: 'x' }, { recipeId: 'B', value: 'x' }])
  assert.equal(buckets[0]?.isOutlier, false)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: FAIL — `groupFieldValues` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `recipeCompare.ts`:

```typescript
export interface ValueBucket {
  value: string
  count: number
  recipeIds: string[]
  isOutlier: boolean
}

export function groupFieldValues(pairs: { recipeId: string, value: string }[]): ValueBucket[] {
  const map = new Map<string, string[]>()
  const order: string[] = []
  for (const { recipeId, value } of pairs) {
    if (!map.has(value)) {
      map.set(value, [])
      order.push(value)
    }
    map.get(value)!.push(recipeId)
  }

  const buckets: ValueBucket[] = order.map(value => ({
    value,
    count: map.get(value)!.length,
    recipeIds: map.get(value)!,
    isOutlier: false
  }))
  buckets.sort((a, b) => b.count - a.count)

  const total = pairs.length
  const maxCount = buckets[0]?.count ?? 0
  const largestBuckets = buckets.filter(b => b.count === maxCount).length

  for (const bucket of buckets) {
    const isLargest = bucket.count === maxCount
    const share = total > 0 ? bucket.count / total : 0
    bucket.isOutlier = !isLargest && largestBuckets === 1 && share <= OUTLIER_SHARE
  }

  return buckets
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/recipeCompare.ts front-dev-home/app/utils/recipeCompare.test.ts
git commit -m "feat(recipe-compare): value grouping + outlier flagging util"
```

---

### Task 7: Pure util — Excel workbook builder

**Files:**
- Modify: `front-dev-home/app/utils/recipeCompare.ts`
- Modify: `front-dev-home/app/utils/recipeCompare.test.ts`

- [ ] **Step 1: Add the failing test**

Append to `recipeCompare.test.ts` (extend the import to add `buildCompareWorkbook`):

```typescript
import { buildCompareWorkbook } from './recipeCompare.ts'

test('buildCompareWorkbook emits Overlap + IDP + one sheet per slot', () => {
  const wb = buildCompareWorkbook([
    recipeWithAmp('A', [measAmp({ Mag: '50.0K' })]),
    recipeWithAmp('B', [measAmp({ Mag: '80.0K' })])
  ], ['WAFER'])

  const names = wb.sheets.map(s => s.name)
  assert.deepEqual(names, ['Overlap', 'IDP', 'Addressing 1', 'Addressing 2', 'Addressing 3', 'Measure 1', 'Measure 2'])

  const overlap = wb.sheets.find(s => s.name === 'Overlap')!
  assert.deepEqual(overlap.rows[0], ['parameter', 'coverage', 'A', 'B'])
  assert.deepEqual(overlap.rows[1], ['WAFER', 'all', '✓', '✓'])

  const meas1 = wb.sheets.find(s => s.name === 'Measure 1')!
  assert.deepEqual(meas1.rows[0], ['parameter', 'attr', 'A', 'B'])
  const magRow = meas1.rows.find(r => r[1] === 'Mag')!
  assert.deepEqual(magRow, ['WAFER', 'Mag', '50.0K', '80.0K'])
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: FAIL — `buildCompareWorkbook` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `recipeCompare.ts`:

```typescript
export interface WorkbookSheet {
  name: string
  rows: (string | number)[][]
}

export interface CompareWorkbook {
  sheets: WorkbookSheet[]
}

export function buildCompareWorkbook(
  recipes: CompareRecipe[],
  parameters: string[]
): CompareWorkbook {
  const recipeIds = recipes.map(r => r.recipe_id)
  const sheets: WorkbookSheet[] = []

  const overlap = buildOverlap(recipes)
  const overlapRows: (string | number)[][] = [['parameter', 'coverage', ...recipeIds]]
  for (const row of overlap) {
    overlapRows.push([
      row.parameter,
      row.coverage,
      ...recipes.map(r => (row.presentIn.includes(r.recipe_id) ? '✓' : '—'))
    ])
  }
  sheets.push({ name: 'Overlap', rows: overlapRows })

  const idpRows: (string | number)[][] = [['parameter', 'attr', ...recipeIds]]
  for (const parameter of parameters) {
    for (const r of buildIdpRows(recipes, parameter)) {
      idpRows.push([parameter, r.label, ...r.values])
    }
  }
  sheets.push({ name: 'IDP', rows: idpRows })

  for (const slot of IMAGE_SLOTS) {
    const rows: (string | number)[][] = [['parameter', 'attr', ...recipeIds]]
    for (const parameter of parameters) {
      for (const r of buildAmpRows(recipes, parameter, slot.key)) {
        rows.push([parameter, r.label, ...r.values])
      }
    }
    sheets.push({ name: slot.stage, rows })
  }

  return { sheets }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/recipeCompare.test.ts`
Expected: PASS (all tests across the file).

- [ ] **Step 5: Typecheck + lint + commit**

```bash
cd front-dev-home && npm run typecheck && npm run lint
git add front-dev-home/app/utils/recipeCompare.ts front-dev-home/app/utils/recipeCompare.test.ts
git commit -m "feat(recipe-compare): Excel workbook builder util"
```

Expected: typecheck + lint clean, then commit succeeds.

---

## Done when

- `cd front-dev-home && npm run test` passes including all `recipeCompare` tests.
- `python -c` checks in Tasks 1–2 succeed; the `POST /compare` curl returns recipes.
- `npm run typecheck` and `npm run lint` are clean.
- No UI yet — Plans 2 and 3 build on this.
