# Device-Statistics D22 — Plan 3: R3 Rule Page (prescriptive)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `measurement-rules` the R3-only rule page: keep the static cap matrix (D21), add an R3 compliance device-table that applies the rule **per recipe** and shows the **count** of violated recipes per device, drillable to the offending parameters. Remove the placeholder M-fab caps.

**Architecture:** Reuse the existing `evaluateLot` (ruleEngine.ts) — no new judging logic. A new pure `toViolationDrill` adapter turns `LotHealth` into the shared `DrillDevice` (Plan 2), rendered by the same `DrillSlideover`. The compliance table operates on the selected device cart (same scope decision as Plan 2). `rules.py` drops `_mfab_cells()` so the rule API is R3-only.

**Tech Stack:** Nuxt 4 + NuxtUI, `useAsyncData` + `$fetch`, pure TS adapter tested with `node --test`, Flask mock.

**Depends on:** Plan 1 (`fetchRecipeParams`), Plan 2 (`DrillDevice`, `DrillSlideover`, `deviceDrill.ts`).

---

## ⚠️ Key decisions baked into this plan (confirm before executing)

1. **Compliance scope = the selected device cart (R3 lots), not all 2000 R3 devices** — same rationale as Plan 2 (computing `evaluateLot` per device needs that device's 100–200 recipes). The compliance table reads `useDeviceCart` and filters to R3 (`lot_cd` starting with `R`). *(Phase 2/3 office alternative: a summary endpoint precomputing violated-recipe counts for the full table.)*
2. **Device row = count of violated recipes (NOT ratio)** — D22 supersedes D14. `evaluateLot` returns `violation_recipes` (a count); the row shows that integer directly. `violation_ratio` is ignored.
3. **No health color on the compliance row (for now)** — D16 ratio thresholds are void under a count model (D22 open item ③). The row shows the bare count with a rose emphasis only when `> 0`. Revisit if you want a count-based color band.

If you'd rather the compliance table live on the full index table (summary endpoint) or keep a health color, redirect here first.

## 🎨 UI consistency requirement (user directive)

Same as Plan 2: `dashboard-surface` cards, `Matrix.vue` table-header style, `RecipeDetailSlideover.vue` slideover, `--sk-*` semantic tokens (no raw `text-zinc-*` for muted text), `MeasurementRulesView.vue` loading/error blocks. The compliance table must look like a sibling of the cap matrix already on the page.

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `back_dev_home/ebeam/cdsem/device_statistics/rules.py` | Remove `_mfab_cells()` + M-fab seed; R3-only | Modify |
| `front-dev-home/app/utils/deviceDrill.ts` | Add `toViolationDrill` adapter | Modify |
| `front-dev-home/app/utils/deviceDrill.test.ts` | Tests for `toViolationDrill` | Modify |
| `front-dev-home/app/components/ebeam/rules/ComplianceTable.vue` | R3 compliance device-table + drill (`EbeamRulesComplianceTable`) | Create |
| `front-dev-home/app/components/ebeam/MeasurementRulesView.vue` | Drop M-fab branch; embed compliance table | Modify |
| `docs/api-contracts/cdsem-device-statistics.yaml` | `rules` endpoint note → R3-only | Modify |

---

## Task 1: Backend — make `rules.py` R3-only

**Files:**
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/rules.py`

- [ ] **Step 1: Remove the M-fab cell builder + seed**

Delete the `_mfab_cells(fab)` function (lines ~148-160) and the `M_FAB_IDS` constant (line ~163). Replace the `_SEED` dict (lines ~166-178) so only R3 remains:

```python
# 현재 버전 seed. R3 전용 (D22 — M-fab 룰 폐기, D15 supersede).
_SEED: dict[str, RuleVersion] = {
    "R3": {
        "fab": "R3", "version": 1, "edited_by": "seed", "edited_at": "2026-05-20T10:00:00Z",
        "cells": _r3_cells(), "thresholds": dict(_SEED_THRESHOLDS),
    },
}


def list_rule_fabs() -> list[str]:
    return ["R3"]
```

`get_rules(fab)` is unchanged — it already returns `None` for unknown fabs (now including every M-fab), which the route turns into 404.

- [ ] **Step 2: Verify R3 still resolves and M-fab 404s**

Run: `python -c "from back_dev_home.ebeam.cdsem.device_statistics.rules import get_rules, list_rule_fabs; print(list_rule_fabs()); print(get_rules('R3') is not None); print(get_rules('M14'))"`
Expected:
```
['R3']
True
None
```

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/cdsem/device_statistics/rules.py
git commit -m "refactor(rules): drop placeholder M-fab caps, R3-only rule API (D22)"
```

---

## Task 2: `toViolationDrill` adapter (TDD)

Turn `evaluateLot`'s `LotHealth` into the shared `DrillDevice`, with cap violations as the flag and `cap N` as the note.

**Files:**
- Modify: `front-dev-home/app/utils/deviceDrill.test.ts`
- Modify: `front-dev-home/app/utils/deviceDrill.ts`

- [ ] **Step 1: Add failing tests**

Append to `front-dev-home/app/utils/deviceDrill.test.ts`:

```ts
import { toViolationDrill } from './deviceDrill.ts'
import { evaluateLot, type RuleCell } from './ruleEngine.ts'

const coreEarlyDram: RuleCell = {
  id: 'r3-core-tev-dram',
  selector: { fab: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [{ patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains', cap: 13 }]
}

const dramRecipe = (recipe_id: string, edgePoints: number): RecipeInput => ({
  lot_cd: 'R000', recipe_id, fac_id: 'R3', ctn_desc: 't-EV DRAM Core', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 't-EV', memory_class_auto: 'DRAM',
  parameters: [{ name: 'WAFER_CD', point_count: 13 }, { name: 'EDGE_L', point_count: edgePoints }]
})

test('violation drill flags recipes whose param exceeds its cap, with cap note', () => {
  // EDGE cap is 10. Recipe B measures 16 → violation; A measures 8 → pass.
  const recipes = [dramRecipe('A', 8), dramRecipe('B', 16)]
  const health = evaluateLot('R000', recipes, [coreEarlyDram])
  const drill = toViolationDrill('R000', 'R000 dev', health)

  assert.equal(drill.flagged_recipe_count, 1) // count, not ratio (D22)
  const recB = drill.recipes.find(r => r.recipe_id === 'B')!
  assert.equal(recB.flagged, true)
  const edge = recB.parameters.find(p => p.name === 'EDGE_L')!
  assert.equal(edge.flagged, true)
  assert.equal(edge.note, 'cap 10')
  const recA = drill.recipes.find(r => r.recipe_id === 'A')!
  assert.equal(recA.flagged, false)
})

test('violation drill: gray (unruled) recipes are unflagged', () => {
  // No matching cell for an M-class fab → gray, conservative pass (D14).
  const recipes = [dramRecipe('A', 99)]
  const health = evaluateLot('R000', recipes, []) // empty rules → gray A
  const drill = toViolationDrill('R000', '', health)
  assert.equal(drill.flagged_recipe_count, 0)
  assert.ok(drill.recipes.every(r => !r.flagged))
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd front-dev-home && node --test app/utils/deviceDrill.test.ts`
Expected: FAIL — `toViolationDrill` is not exported.

- [ ] **Step 3: Implement the adapter**

Append to `front-dev-home/app/utils/deviceDrill.ts` (add `LotHealth` to the import):

```ts
import type { LotHealth } from './ruleEngine'

/** Prescriptive adapter — cap violations from evaluateLot (D22, count not ratio). */
export const toViolationDrill = (
  lot_cd: string,
  ctn_desc: string,
  health: LotHealth
): DrillDevice => {
  const drillRecipes: DrillRecipe[] = health.recipes.map((r) => {
    const parameters: DrillParameter[] = r.results.map(p => ({
      name: p.name,
      point_count: p.point_count,
      flagged: p.violation,
      note: p.violation && typeof p.cap === 'number' ? `cap ${p.cap}` : undefined
    }))
    return {
      recipe_id: r.recipe_id,
      flagged: !r.pass && r.gray == null,
      total_params: r.total_params,
      flagged_count: r.violation_params.length,
      parameters
    }
  })
  return {
    lot_cd,
    ctn_desc,
    recipes: drillRecipes,
    flagged_recipe_count: health.violation_recipes, // count (D22)
    flagged_param_count: drillRecipes.reduce((sum, r) => sum + r.flagged_count, 0)
  }
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd front-dev-home && node --test app/utils/deviceDrill.test.ts`
Expected: PASS — all tests (Plan 2 outlier + Plan 3 violation) green.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/deviceDrill.ts front-dev-home/app/utils/deviceDrill.test.ts
git commit -m "feat(device-statistics): cap-violation drill adapter (D22)"
```

---

## Task 3: `rules/ComplianceTable.vue` — R3 compliance device-table

**Files:**
- Create: `front-dev-home/app/components/ebeam/rules/ComplianceTable.vue`

Reads the device cart (R3 lots only), fetches `recipe-params`, runs `evaluateLot` per device against the passed-in cells, shows violated-recipe counts, and drills via the shared slideover.

- [ ] **Step 1: Write the component**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-4">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h3 class="text-[12.5px] font-semibold text-(--sk-ink)">
        {{ text.title }}
      </h3>
      <span class="text-[11px] text-(--sk-ink-muted)">
        {{ text.legend }}
      </span>
    </div>

    <div
      v-if="r3Lots.length === 0"
      class="px-4 py-12 text-center text-sm text-(--sk-ink-muted)"
    >
      {{ text.empty }}
    </div>
    <div v-else-if="pending" class="flex items-center justify-center gap-2 py-12 text-sm text-(--sk-ink-muted)">
      <UIcon name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
      {{ text.loading }}
    </div>
    <div v-else-if="error" class="py-12 text-center text-sm text-rose-600 dark:text-rose-300">
      {{ text.loadError }}
    </div>
    <table v-else class="w-full border-collapse">
      <thead>
        <tr class="border-b border-(--sk-border)">
          <th class="px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
            디바이스
          </th>
          <th class="px-2 py-2 text-right font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
            recipe
          </th>
          <th class="px-2 py-2 text-right font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
            위반 recipe
          </th>
          <th class="px-2 py-2" />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="dev in deviceRows"
          :key="dev.lot_cd"
          class="border-t border-(--sk-border) transition-colors hover:bg-(--sk-accent-tint)/40"
        >
          <td class="px-3 py-1.5 font-mono text-[12.5px] text-(--sk-ink)">
            {{ dev.lot_cd }}
          </td>
          <td class="px-2 py-1.5 text-right font-mono text-[12.5px] tabular-nums text-(--sk-ink-muted)">
            {{ dev.recipe_count }}
          </td>
          <td class="px-2 py-1.5 text-right">
            <span
              class="inline-flex h-5 min-w-7 items-center justify-center rounded px-1.5 font-mono text-[11px] font-semibold tabular-nums"
              :class="dev.violation_count > 0
                ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                : 'bg-(--sk-surface) text-(--sk-ink-subtle)'"
            >{{ dev.violation_count }}</span>
          </td>
          <td class="px-2 py-1.5 text-right">
            <UButton size="xs" color="neutral" variant="outline" :label="text.details" @click="openDrill(dev.lot_cd)" />
          </td>
        </tr>
      </tbody>
    </table>

    <EbeamDevstatDrillSlideover
      v-model:open="drillOpen"
      :device="activeDrill"
      highlight-label="위반"
    />
  </div>
</template>

<script setup lang="ts">
import type { RecipeInput, RuleCell } from '~/utils/ruleEngine'
import { evaluateLot } from '~/utils/ruleEngine'
import { toViolationDrill, type DrillDevice } from '~/utils/deviceDrill'

const props = defineProps<{ cells: RuleCell[] }>()

const { fetchRecipeParams } = useDeviceStatisticsApi()
const { selectedDeviceLots } = useDeviceCart()

// Compliance is R3-only (D22). Filter the cart to R3 lots (lot_cd starts with 'R').
const r3Lots = computed(() => selectedDeviceLots.value.filter(lot => lot.startsWith('R')))

const text = {
  title: 'R3 룰 준수',
  legend: '선택한 R3 디바이스의 recipe 별 cap 준수 결과 · 위반 recipe 수',
  details: '자세히',
  empty: '디바이스 통계에서 R3 디바이스를 선택하면 룰 준수 결과가 표시됩니다.',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.'
} as const

const { data, pending, error } = await useAsyncData<RecipeInput[]>(
  'r3-compliance',
  () => r3Lots.value.length ? fetchRecipeParams(r3Lots.value) : Promise.resolve([]),
  { watch: [r3Lots] }
)

const recipesByLot = computed(() => {
  const map = new Map<string, RecipeInput[]>()
  for (const r of data.value ?? []) {
    const bucket = map.get(r.lot_cd)
    if (bucket) bucket.push(r)
    else map.set(r.lot_cd, [r])
  }
  return map
})

interface ComplianceRow { lot_cd: string, recipe_count: number, violation_count: number }

const deviceRows = computed<ComplianceRow[]>(() => {
  const rows: ComplianceRow[] = []
  for (const lot_cd of r3Lots.value) {
    const recipes = recipesByLot.value.get(lot_cd) ?? []
    const health = evaluateLot(lot_cd, recipes, props.cells)
    rows.push({ lot_cd, recipe_count: recipes.length, violation_count: health.violation_recipes })
  }
  return rows.sort((a, b) => b.violation_count - a.violation_count)
})

const drillOpen = ref(false)
const activeDrill = ref<DrillDevice | null>(null)

const openDrill = (lot_cd: string) => {
  const recipes = recipesByLot.value.get(lot_cd) ?? []
  const health = evaluateLot(lot_cd, recipes, props.cells)
  activeDrill.value = toViolationDrill(lot_cd, recipes[0]?.ctn_desc ?? '', health)
  drillOpen.value = true
}
</script>
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/rules/ComplianceTable.vue
git commit -m "feat(rules): R3 compliance device-table component (D22)"
```

---

## Task 4: `MeasurementRulesView.vue` — R3-only + embed compliance

**Files:**
- Modify: `front-dev-home/app/components/ebeam/MeasurementRulesView.vue`

- [ ] **Step 1: Drop the M-fab branch and fab selector**

In the template, remove the `<template #toggle>` block holding `<EbeamRulesFabSelector>` (lines ~9-14) and remove the `isMfab` note paragraph (lines ~56-62). After the `<EbeamRulesMatrix>` block, add the compliance table:

```vue
      <template v-else-if="version">
        <EbeamRulesMatrix
          :cells="version.cells"
          :mfab="false"
        />
      </template>
    </div>

    <EbeamRulesComplianceTable
      v-if="version"
      :cells="version.cells"
    />
```

In the script, replace the fab plumbing. Remove `fabs`, `DEFAULT_FAB`, `STORAGE_KEY`, `readSavedFab`, `selectedFab`, `isMfab`, the `selectedFab` watch, and the `mfabNote`/`legend*` M-fab copy. Hardcode R3:

```ts
const RULE_FAB = 'R3'

const { data: version, pending, error } = await useAsyncData<RuleVersion>(
  'measurement-rules',
  () => fetchRules(RULE_FAB)
)
```

Update `metaStats` to drop any fab reference (it already reads `version.value` fields — keep `cells`/`version`/`editor`). Remove the `EbeamRulesFabSelector` import if explicitly imported (it is auto-imported, so just remove template usage).

- [ ] **Step 2: Update copy**

Set the subtitle to reflect R3-only and add nothing M-fab-specific:

```ts
const text = {
  title: '계측 룰',
  subtitle: 'R3 계측 파라미터 cap 정책과 준수 결과를 확인합니다.',
  legendLead: '행 = 룰 셀 · 열 = 파라미터 타입 · 칸 = 최대 측정 포인트 수(cap, ≤).',
  legendCap: '상한',
  legendZero: '측정 금지',
  legendNA: '해당 없음',
  loading: '로딩 중',
  loadError: '룰을 불러오지 못했습니다.'
} as const
```

- [ ] **Step 3: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: PASS. (If `EbeamRulesFabSelector.vue` is now unused, it can stay in place — leaving an unused component does not fail typecheck; remove it only if you also drop any other references.)

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/MeasurementRulesView.vue
git commit -m "feat(rules): R3-only rule page with compliance table (D22)"
```

---

## Task 5: Contract note + verification

**Files:**
- Modify: `docs/api-contracts/cdsem-device-statistics.yaml`

- [ ] **Step 1: Update the `rules` endpoint note to R3-only**

In the `rules` endpoint `description` (line ~237-240), replace the D15 mention:

```yaml
    description: >
      Current measurement-rule version for R3 (D8 cap matrix). R3-only since D22
      (M-fab has no agreed rule — placeholder caps removed). Ships raw rule cells
      only; the frontend ruleEngine computes violations client-side.
```

In `query_params.fab.description`, note non-R3 returns 404:

```yaml
        description: 'Fab id — only "R3" is served (D22). 400 if missing, 404 for any other fab.'
```

- [ ] **Step 2: Commit the doc**

```bash
git add docs/api-contracts/cdsem-device-statistics.yaml
git commit -m "docs(rules): mark rules endpoint R3-only (D22)"
```

- [ ] **Step 3: Full verification**

Run: `cd front-dev-home && npm run typecheck && npm run test && npm run lint`
Expected: PASS — `deviceDrill.test.ts` (outlier + violation), `outlierDetect.test.ts`, `ruleEngine.test.ts` green.

- [ ] **Step 4: Manual smoke (user runs Nuxt :3000 + Flask :5050)**

Navigate to measurement-rules. Expect: the R3 cap matrix (no fab selector, no M-fab note), then below it the compliance table. Select R3 devices on the device-statistics page first, return to measurement-rules → the table lists them with violated-recipe counts; "자세히" opens the slideover highlighting cap-violating parameters with `cap N` notes. Confirm M-fab caps no longer appear anywhere.

---

## Self-Review

- **Spec coverage:** R3 prescriptive page → `MeasurementRulesView` keeps the cap matrix + adds `ComplianceTable` (Tasks 3–4). Rule applied per recipe, device row = violated-recipe **count** → `evaluateLot().violation_recipes` surfaced directly (Task 3); `toViolationDrill` tested for count semantics (Task 2). Drill highlights cap violations → shared `DrillSlideover` with `highlight-label="위반"`. M-fab rule removed → `rules.py` R3-only (Task 1) + contract note (Task 5).
- **Type consistency:** `toViolationDrill` returns the same `DrillDevice` as `toOutlierDrill`; `DrillSlideover` (Plan 2) renders both. `evaluateLot(lot, recipes, cells)` signature matches ruleEngine.ts:259. `ComplianceTable` prop `cells: RuleCell[]` matches `version.cells` from `fetchRules`.
- **UI consistency:** compliance table reuses `Matrix.vue` header style + `dashboard-surface`; slideover shared with Plan 2; `--sk-*` tokens throughout; loading/error mirror the existing `MeasurementRulesView` blocks.
- **No placeholders:** every step has runnable code/commands + expected output. Backend change verified via inline `python -c`.

---

## Execution Handoff

Implement with **superpowers:subagent-driven-development** (recommended) or **superpowers:executing-plans**. **Order: Plan 1 → Plan 2 → Plan 3** (Plan 3 Task 2–3 import `DrillDevice`/`DrillSlideover` from Plan 2, and `fetchRecipeParams` from Plan 1).
