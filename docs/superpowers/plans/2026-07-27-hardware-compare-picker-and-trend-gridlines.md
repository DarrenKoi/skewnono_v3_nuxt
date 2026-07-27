# Hardware Compare Picker + Trend Gridlines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the hardware 장비 ID 검색 dropdown search-scoped 전체 선택/해제 buttons, and remove the horizontal gridlines from every hardware time-series chart.

**Architecture:** Filtering moves out of `USelectMenu`'s internal matcher into the parent component (`ignore-filter` + pre-filtered `:items` + `v-model:search-term`), so the visible list and the select-all target set are the same array by construction. The filter itself is a pure function in the existing `hardwareCompare.ts` helper module and is unit-tested. Gridline removal is five inline `splitLine: { show: false }` additions on y-axes of time-axis charts — no shared wrapper.

**Tech Stack:** Nuxt 4 SPA, Vue 3 `<script setup>`, Nuxt UI 4.10 (`USelectMenu`), ECharts via the local `useEchart` composable, `node --test` for pure-function tests.

## Global Constraints

- Spec of record: `docs/superpowers/specs/2026-07-27-hardware-compare-picker-and-trend-gridlines-design.md`.
- Colors come from `--sk-*` tokens only, never inline hex (`DESIGN.md`). No new hex values in any template.
- No Pinia. The picked-tool set stays the existing `useState('hw-compare-tools')` owned by the panels; `CompareToolPicker` stays a controlled component that reads `modelValue` and emits, never mutating.
- Frontend commands run from `front-dev-home/`: `npm test`, `npm run lint`, `npm run typecheck`.
- There is no component-test harness in this repo. Only pure functions get automated tests; component changes are verified by `typecheck` + `lint` + browser.
- Work directly on `main`. Commit at coherent stopping points.
- Gridline scope is time-axis charts ONLY. Do not touch scatter, boxplot, profile, or radar charts.

---

### Task 1: `filterToolIds` pure filter helper

The picker needs to compute its own visible list. That match logic is the one
piece with real edge cases (blank input, whitespace, case), so it is extracted
and tested before any component changes.

**Files:**

- Modify: `front-dev-home/app/utils/hardwareCompare.ts` (append; file currently ends at line 66)
- Test: `front-dev-home/app/utils/hardwareCompare.test.ts` (append; file currently ends at line 50)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `filterToolIds(ids: readonly string[], term: string): string[]` — used by Task 2.

- [ ] **Step 1: Write the failing tests**

Append to `front-dev-home/app/utils/hardwareCompare.test.ts`:

```ts
test('filterToolIds: blank or whitespace term → every id, order preserved', () => {
  const ids = ['TP0302', 'TP0301', 'CD1101']
  assert.deepEqual(filterToolIds(ids, ''), ids)
  assert.deepEqual(filterToolIds(ids, '   '), ids)
})

test('filterToolIds: case-insensitive substring match', () => {
  const ids = ['TP0301', 'TP0302', 'CD1101']
  assert.deepEqual(filterToolIds(ids, 'tp03'), ['TP0301', 'TP0302'])
  assert.deepEqual(filterToolIds(ids, 'TP03'), ['TP0301', 'TP0302'])
  // Matches anywhere in the id, not just the prefix.
  assert.deepEqual(filterToolIds(ids, '1101'), ['CD1101'])
})

test('filterToolIds: surrounding whitespace on the term is ignored', () => {
  assert.deepEqual(filterToolIds(['TP0301', 'CD1101'], '  tp  '), ['TP0301'])
})

test('filterToolIds: no match → empty array', () => {
  assert.deepEqual(filterToolIds(['TP0301'], 'zzz'), [])
})
```

Also extend the import on line 4 of that file to include the new symbol:

```ts
import { assignCompareColors, assignSeriesColors, compareBoxPoints, filterToolIds } from './hardwareCompare.ts'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `filterToolIds is not a function` (or an import/export error naming `filterToolIds`).

- [ ] **Step 3: Write the implementation**

Append to `front-dev-home/app/utils/hardwareCompare.ts`:

```ts
// The picker filters its own list rather than letting USelectMenu do it, so
// that 전체 선택/해제 act on exactly the rows on screen -- one filter means the
// visible set and the selected-all set cannot drift apart. Nuxt UI's own
// matcher is not a public composable, so mirroring it would mean importing
// from dist/runtime; a substring match is equivalent for ASCII tool ids.
export const filterToolIds = (ids: readonly string[], term: string): string[] => {
  const needle = term.trim().toLowerCase()
  if (!needle) return [...ids]
  return ids.filter(id => id.toLowerCase().includes(needle))
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm --prefix front-dev-home test`
Expected: PASS — all existing tests plus the four new `filterToolIds` tests.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/hardwareCompare.ts front-dev-home/app/utils/hardwareCompare.test.ts
git commit -m "feat(hardware): add filterToolIds for the compare picker's own search

The picker is about to filter its own list instead of delegating to
USelectMenu, so 전체 선택/해제 can act on exactly the visible rows."
```

---

### Task 2: Search-scoped 전체 선택 / 해제 inside the dropdown

**Files:**

- Modify: `front-dev-home/app/components/ebeam/hardware/CompareToolPicker.vue` (whole file)

**Interfaces:**

- Consumes: `filterToolIds(ids: readonly string[], term: string): string[]` from Task 1.
- Produces: no new exports. Props and the `update:modelValue` emit are unchanged, so `MdcPanel.vue:4` and `ScePanel.vue:208` need no edits.

- [ ] **Step 1: Replace the file contents**

Write `front-dev-home/app/components/ebeam/hardware/CompareToolPicker.vue`:

```vue
<template>
  <div class="flex flex-wrap items-center gap-2 rounded-xl bg-(--sk-surface) px-3 py-2 ring-1 ring-(--sk-border-soft)">
    <span class="inline-flex items-center gap-1.5 sk-eyebrow">
      <UIcon
        name="i-lucide-git-compare"
        class="h-3.5 w-3.5"
      />
      비교 장비
    </span>

    <!-- ◆ = the selected (primary) tool, always shown as the comparison anchor. -->
    <span class="font-mono text-[11px] font-bold text-(--sk-ink)">◆ {{ selectedEqp || '—' }}</span>

    <USelectMenu
      v-model:open="menuOpen"
      v-model:search-term="searchTerm"
      :model-value="modelValue"
      multiple
      ignore-filter
      :reset-search-term-on-select="false"
      value-key="value"
      :items="items"
      :search-input="{ placeholder: '장비 ID 검색…' }"
      placeholder="비교할 장비 선택"
      icon="i-lucide-plus"
      size="xs"
      class="min-w-[16rem] flex-1"
      :disabled="siblingIds.length === 0"
      :ui="{ itemTrailingIcon: 'hidden' }"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <!-- Leading checkbox sits right before the tool name (no far-right gap);
           the default trailing check is hidden via :ui above. -->
      <template #item-leading="{ item }">
        <span
          class="flex h-4 w-4 items-center justify-center rounded border"
          :class="modelValue.includes(item.value)
            ? 'border-(--sk-ink) bg-(--sk-ink) text-white dark:text-zinc-900'
            : 'border-(--sk-border)'"
        >
          <UIcon
            v-if="modelValue.includes(item.value)"
            name="i-lucide-check"
            class="h-3 w-3"
          />
        </span>
      </template>
      <!-- Bulk actions act on the matches, so they belong below the list they
           describe -- #content-top renders above the search input. 닫기 is an
           explicit close affordance (click-outside / Esc also close the menu). -->
      <template #content-bottom>
        <div class="flex items-center gap-1 border-t border-(--sk-border-soft) p-1">
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-list-checks"
            :disabled="unpicked.length === 0"
            @click="selectMatches"
          >
            {{ isSearching ? `검색 결과 ${matches.length}대 선택` : `전체 선택 ${matches.length}` }}
          </UButton>
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-eraser"
            :disabled="pickedMatches.length === 0"
            @click="clearMatches"
          >
            해제
          </UButton>
          <UButton
            class="ml-auto"
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-check"
            @click="menuOpen = false"
          >
            닫기
          </UButton>
        </div>
      </template>
    </USelectMenu>

    <span class="font-mono text-[11px] text-(--sk-ink-muted) tabular-nums">
      동일 fab 장비 {{ siblingIds.length }}대 · 비교 {{ modelValue.length }}대
    </span>
  </div>
</template>

<script setup lang="ts">
// Shared multi-tool selector for the MDC/SCE comparison views. The picked set
// is owned by the parent (page-scoped state), so this component is a controlled
// input: it reads `modelValue` and emits changes, never mutating anything.
import { filterToolIds } from '~/utils/hardwareCompare'

const props = defineProps<{
  siblingIds: string[]
  selectedEqp: string
  modelValue: string[]
}>()

const emit = defineEmits<{ 'update:modelValue': [ids: string[]] }>()

// Controlled open state so the 닫기 button can close the menu; outside-click and
// Esc still close it because Reka emits update:open through this binding.
const menuOpen = ref(false)

// Filtering is ours (`ignore-filter`), not USelectMenu's. The bulk buttons must
// act on exactly the rows on screen, and the only way those two sets cannot
// disagree is for one array to be both. `reset-search-term-on-select` is off
// for the same reason: the default wipes the search after every click, which
// would drop the filter mid-way through picking a family of tools.
const searchTerm = ref('')
const isSearching = computed(() => searchTerm.value.trim().length > 0)

const matches = computed(() => filterToolIds(props.siblingIds, searchTerm.value))
const items = computed(() => matches.value.map(id => ({ label: id, value: id })))

// Both bulk actions are scoped to the matches: 전체 선택 unions them into the
// existing picks so tools chosen under an earlier search survive, and 해제
// subtracts only them. With an empty box the matches are every sibling, so
// 해제 still reads as a plain "clear all".
const unpicked = computed(() => matches.value.filter(id => !props.modelValue.includes(id)))
const pickedMatches = computed(() => matches.value.filter(id => props.modelValue.includes(id)))

const selectMatches = () => emit('update:modelValue', [...props.modelValue, ...unpicked.value])
const clearMatches = () => emit('update:modelValue', props.modelValue.filter(id => !matches.value.includes(id)))
</script>
```

- [ ] **Step 2: Verify types and lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: both PASS. If `vue/attributes-order` complains, reorder attributes as
eslint reports — do not disable the rule.

- [ ] **Step 3: Verify the existing tests still pass**

Run: `npm --prefix front-dev-home test`
Expected: PASS. (No component tests exist; this guards the Task 1 helper.)

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/hardware/CompareToolPicker.vue
git commit -m "feat(hardware): search-scoped 전체 선택/해제 in the 장비 ID 검색 dropdown

Bulk actions move into the dropdown footer and act on the current search
matches: 전체 선택 unions matches into the existing picks, 해제 subtracts
them. Filtering moves to the parent (ignore-filter + pre-filtered items) so
the visible list and the bulk target are the same array. The bar-level
전체/해제 pair is removed -- two identical-looking controls behaving
differently is worse than one. reset-search-term-on-select is disabled so
the filter survives each click."
```

---

### Task 3: Remove horizontal gridlines from hardware time-series charts

Five y-axes across four files. Each is a time-axis (`xAxis: { type: 'time' }`)
chart, so the horizontal splitLines sit behind a near-flat series on a tight
y-range and read as data.

**Files:**

- Modify: `front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue:83-89`
- Modify: `front-dev-home/app/components/ebeam/hardware/FdcPanel.vue:320`, `:349`, `:459`
- Modify: `front-dev-home/app/components/ebeam/hardware/ResoCenterPanel.vue:147`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: `BsmTrendChart.vue` — the shared BSM / MDC 시계열 / Sharpness trend**

Replace the `yAxis` block (currently lines 83-89):

```ts
  yAxis: {
    type: 'value',
    ...(props.yMode === 'tight'
      ? (tightYRange(yValues.value) ?? { scale: true })
      : (stableYRange(yValues.value, props.yOptions) ?? { scale: true })),
    axisLabel: { fontSize: 10 },
    // Hardware parameters are mostly flat, and a tight y-range packs straight
    // horizontal lines right behind the series -- they read as data. The time
    // axis keeps its vertical lines, which anchor timestamps instead.
    splitLine: { show: false }
  },
```

- [ ] **Step 2: `FdcPanel.vue` — ratio axis on grid 0 (line 320)**

The two grid-1 axes on lines 321-322 already hide theirs. Replace line 320:

```ts
      { type: 'value', gridIndex: 0, name: 'ratio', nameTextStyle: { fontSize: 10 }, ...ratioAxis, axisLabel: { fontSize: 10 }, splitLine: { show: false } },
```

The comment on line 318 currently explains only why the dual count axes hide
their splitLines. Replace it so it covers all three:

```ts
    // Horizontal splitLines are off on every time-series axis here: the counts'
    // independent intervals never align, and on the ratio axis the flat series
    // sits so close to the lines that they read as data.
```

- [ ] **Step 3: `FdcPanel.vue` — % vs baseline (line 349)**

```ts
    yAxis: { type: 'value', name: '% vs baseline', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10, formatter: '{value}%' }, scale: true, splitLine: { show: false } },
```

- [ ] **Step 4: `FdcPanel.vue` — temperature (line 459)**

```ts
    yAxis: { type: 'value', name: '°C', ...tempAxis, axisLabel: { fontSize: 10 }, splitLine: { show: false } },
```

- [ ] **Step 5: `ResoCenterPanel.vue` — reso drift in nm (line 147)**

```ts
    yAxis: { type: 'value', name: 'nm', ...yRange, axisLabel: { fontSize: 10 }, splitLine: { show: false } },
```

- [ ] **Step 6: Confirm nothing else was touched**

Run: `git diff --stat`
Expected: exactly three files changed — `BsmTrendChart.vue`, `FdcPanel.vue`,
`ResoCenterPanel.vue`.

Run: `grep -n "type: 'time'" front-dev-home/app/components/ebeam/hardware/*.vue`
Expected: six hits across `BsmTrendChart.vue`, `ResoCenterPanel.vue`,
`FdcPanel.vue` (x2 in one dual-grid chart, plus two more charts), `ScePanel.vue`.
`ScePanel.vue`'s axis helper already sets `splitLine: { show: false }` — leave it.

Confirm the non-time charts were NOT changed: `MdcPanel.vue` (boxplot,
trajectory), `SharpnessProfileChart.vue`, `BsmRadarChart.vue`, `ScePanel.vue`
profile axes, `ResoCenterPanel.vue:105-106` (CenterX/CenterY scatter),
`FdcPanel.vue:392-398` (pair scatter) and `:419-420` (SPM index profile).

- [ ] **Step 7: Verify types and lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint && npm --prefix front-dev-home test`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue \
        front-dev-home/app/components/ebeam/hardware/FdcPanel.vue \
        front-dev-home/app/components/ebeam/hardware/ResoCenterPanel.vue
git commit -m "fix(hardware): drop horizontal gridlines from time-series charts

Hardware parameters are mostly stable, so the y-range is tight and the
theme's horizontal splitLines end up packed behind a near-flat series where
they read as data. Applied to the time-axis charts only -- BSM/MDC/Sharpness
trends, FDC ratio + %-baseline + temperature, and the reso drift. Scatter,
boxplot and profile charts keep theirs, since reading a value off those
leans on the grid. Vertical (time) lines stay: they anchor timestamps."
```

---

### Task 4: Verify in the running app

**Files:** none — verification only.

**Interfaces:**

- Consumes: the finished behavior from Tasks 1-3.
- Produces: screenshots under `.playwright-mcp/screenshots/`.

- [ ] **Step 1: Start both servers**

Follow the `verify` skill. In short, from the repo root:

```bash
.venv/bin/python index.py            # Flask on :5050
npm --prefix front-dev-home run dev  # Nuxt on :3000
```

A blank SPA rendering `<!---->` with no console errors means Flask is down —
check :5050 before blaming a component.

- [ ] **Step 2: Drive the MDC tab**

Open a hardware page (e.g. `/ebeam/hv-sem/<fab>/hardware`), pick a tool, open
the MDC tab, then the 장비 ID 검색 dropdown. Check, in order:

1. The bar no longer shows 전체/해제 on the right.
2. The dropdown footer shows `전체 선택 N` · `해제` · `닫기`.
3. Typing a partial id filters the list AND the button becomes
   `검색 결과 M대 선택` with M = the visible row count.
4. Clicking a row does NOT clear the search box.
5. `검색 결과 M대 선택` adds only the matches; clearing the box shows the
   earlier picks are still selected.
6. With a term typed, `해제` removes only the matching picks.
7. `해제` with an empty box clears everything.

- [ ] **Step 3: Check the charts**

On the MDC 시계열 tab and the FDC tab, confirm the trend charts show no
horizontal gridlines while vertical time gridlines remain. Confirm the MDC 비교
boxplot and the FDC pair scatter still HAVE their gridlines.

Screenshot both to `.playwright-mcp/screenshots/`.

- [ ] **Step 4: Run the full checks**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run lint
npm --prefix front-dev-home run typecheck
npm run lint:md
```

Expected: all PASS.
