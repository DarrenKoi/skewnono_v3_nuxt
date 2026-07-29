# Skewvoir FDC Graph View Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skewvoir 단일 MSR FDC 분석에서 파라미터 매트릭스와 사용자가 고른 개별 그래프를 전환해 보고, 측정 순서·이벤트 색상·CD matrix cell 폭을 확정된 UX에 맞춥니다.

**Architecture:** `graphSelection.ts`가 그래프 식별자와 선택 집합 변경을 순수 함수로 소유하고, `SequenceWorkbench.vue`는 그 함수를 Vue local state와 연결합니다. 비활성 보기는 `v-if`로 ECharts 인스턴스를 해제하며, 기존 sequence model·상관 계산·URL 상태는 그대로 유지합니다.

**Tech Stack:** Nuxt 4, Vue 3 `<script setup lang="ts">`, TypeScript 5.9, Nuxt UI, Tailwind CSS 4, ECharts 6.1, Node built-in test runner.

## Global Constraints

- 구현은 `docs/superpowers/specs/2026-07-29-skewvoir-fdc-graph-view-toggle-design.md`의 확정 계약을 따릅니다.
- 여러 파일을 수정하므로 실행 시작 시 `superpowers:using-git-worktrees`를 사용해 `main`에서 격리된 worktree를 만듭니다.
- shared tree의 `.remember/today-2026-07-29.md`와 다른 세션 변경은 stage, commit 또는 worktree로 복사하지 않습니다.
- frontend API, backend API, sequence model, correlation 계산, URL query, local storage 및 Nuxt `useState` 계약을 변경하지 않습니다.
- 보기 모드는 page-local `ref<'matrix' | 'individual'>`이며 기본값은 `matrix`입니다.
- focus MSR 또는 활성 CD parameter가 바뀌면 그래프 선택을 전체로 초기화하되 보기 모드는 유지합니다.
- FDC axis만 바뀌면 이전 전체 선택은 새 집합 전체로, 이전 부분 선택은 새 집합과의 교집합으로 조정합니다.
- Dynamic FDC가 없으면 selector와 전체 해제 상태를 숨기고 CD와 `FDC 없음` 안내를 두 보기에서 유지합니다.
- 이미지 이벤트는 정확히 `bg-sky-600 dark:bg-sky-400`, 실패는 `--sk-bad`, 정렬은 `--sk-ok`을 사용합니다.
- CD matrix grid는 첫 열 한 칸만 차지하며 모든 축 제목에 `nameTruncate: { maxWidth: 112, ellipsis: '…' }`를 적용합니다.
- tab은 roving tabindex와 `ArrowLeft`, `ArrowRight`, `Home`, `End`를 지원하고 각 active panel과 ARIA id로 연결합니다.
- matrix drill은 선택을 보존하면서 클릭한 FDC만 추가하고, 개별 그래프 보기로 전환한 뒤 대상 panel로 focus와 scroll을 이동합니다.
- inactive ECharts를 unmount하므로 matrix로 돌아올 때 dataZoom이 전체 범위로 초기화되는 동작을 수용합니다.
- Vue component mounting test harness를 새로 도입하지 않습니다. 선택 계산은 pure util로 검증하고 DOM·ECharts 동작은 실행 중인 앱에서 확인합니다.
- frontend 변경은 2-space indentation, no trailing comma, 1tbs brace style를 따릅니다.
- 각 commit은 명시된 파일만 exact path로 stage하며 `git add -A`, `git add .`, `git commit -a`를 사용하지 않습니다.

## File Map

| File | Responsibility |
| --- | --- |
| `front-dev-home/app/utils/skewvoirAnalysis/graphSelection.ts` | CD/FDC graph id와 선택·toggle·reconcile·drill 추가 규칙을 순수 함수로 제공합니다. |
| `front-dev-home/app/utils/skewvoirAnalysis/graphSelection.test.ts` | 선택 규칙과 CD/FDC 동명 충돌 방지를 Node test runner로 검증합니다. |
| `front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceWorkbench.vue` | 보기 tab, selector, 선택된 graph 렌더링, no-FDC 상태, sequence 위치, drill focus를 통합합니다. |
| `front-dev-home/app/components/ebeam/skewvoir/fdc/ParamMatrix.vue` | CD grid span을 제거하고 축 제목 truncate를 설정합니다. |
| `front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue` | 이미지 event legend와 point를 명확한 파랑으로 변경합니다. |

---

## Execution Setup

- [ ] **Step 1: Create an isolated worktree**

Read and follow `superpowers:using-git-worktrees`. Create a worktree from the
current committed `main` with branch name `work/fdc-graph-views`. Do not copy the
untracked `.remember/today-2026-07-29.md` file into it.

- [ ] **Step 2: Confirm the isolated baseline**

Run inside the worktree:

```bash
git status --short --branch
git log -3 --oneline
git diff --check
```

Expected: a clean `work/fdc-graph-views` branch containing the approved design
and this implementation plan, with no `.remember` file in its status.

---

### Task 1: Pure graph-selection contract

**Files:**

- Create: `front-dev-home/app/utils/skewvoirAnalysis/graphSelection.test.ts`
- Create: `front-dev-home/app/utils/skewvoirAnalysis/graphSelection.ts`

**Interfaces:**

- Consumes: CD parameter name and ordered Dynamic FDC parameter names from `SequenceModel`.
- Produces:
  - `GraphSelectionId = \`cd:${string}\` | \`fdc:${string}\``
  - `cdGraphId(parameter: string): GraphSelectionId`
  - `fdcGraphId(parameter: string): GraphSelectionId`
  - `graphSelectionIds(cdParameter: string, fdcParameters: readonly string[]): GraphSelectionId[]`
  - `selectCdOnly(cdParameter: string): GraphSelectionId[]`
  - `toggleGraphSelection(selected: readonly GraphSelectionId[], id: GraphSelectionId): GraphSelectionId[]`
  - `reconcileGraphSelection(selected: readonly GraphSelectionId[], previousAvailable: readonly GraphSelectionId[], nextAvailable: readonly GraphSelectionId[]): GraphSelectionId[]`
  - `addGraphSelection(selected: readonly GraphSelectionId[], id: GraphSelectionId): GraphSelectionId[]`

- [ ] **Step 1: Write the failing selection tests**

Create `front-dev-home/app/utils/skewvoirAnalysis/graphSelection.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  addGraphSelection,
  cdGraphId,
  fdcGraphId,
  graphSelectionIds,
  reconcileGraphSelection,
  selectCdOnly,
  toggleGraphSelection
} from './graphSelection.ts'

test('CD and same-named FDC parameters use different ids', () => {
  assert.deepEqual(
    graphSelectionIds('StigmaX', ['StigmaX']),
    ['cd:StigmaX', 'fdc:StigmaX']
  )
})

test('the default graph selection contains CD and every FDC in model order', () => {
  assert.deepEqual(
    graphSelectionIds('CD_TOP', ['StigmaX', 'Brightness']),
    ['cd:CD_TOP', 'fdc:StigmaX', 'fdc:Brightness']
  )
})

test('CD-only selection contains only the active CD graph', () => {
  assert.deepEqual(selectCdOnly('CD_TOP'), ['cd:CD_TOP'])
})

test('toggle removes a selected graph and adds an unselected graph', () => {
  const selected = [cdGraphId('CD_TOP'), fdcGraphId('StigmaX')]
  assert.deepEqual(
    toggleGraphSelection(selected, fdcGraphId('StigmaX')),
    ['cd:CD_TOP']
  )
  assert.deepEqual(
    toggleGraphSelection(selected, fdcGraphId('Brightness')),
    ['cd:CD_TOP', 'fdc:StigmaX', 'fdc:Brightness']
  )
})

test('axis reconciliation selects the full next set when the previous set was fully selected', () => {
  const previous = graphSelectionIds('CD_TOP', ['StigmaX'])
  const next = graphSelectionIds('CD_TOP', ['StigmaX', 'Brightness'])
  assert.deepEqual(
    reconcileGraphSelection(previous, previous, next),
    next
  )
})

test('axis reconciliation preserves only the intersection for a custom selection', () => {
  const previous = graphSelectionIds('CD_TOP', ['StigmaX'])
  const selected = [cdGraphId('CD_TOP')]
  const next = graphSelectionIds('CD_TOP', ['Brightness'])
  assert.deepEqual(
    reconcileGraphSelection(selected, previous, next),
    ['cd:CD_TOP']
  )
})

test('axis reconciliation preserves an intentionally empty selection', () => {
  const previous = graphSelectionIds('CD_TOP', ['StigmaX'])
  const next = graphSelectionIds('CD_TOP', ['Brightness'])
  assert.deepEqual(reconcileGraphSelection([], previous, next), [])
})

test('drill adds only the clicked FDC and preserves existing choices', () => {
  assert.deepEqual(
    addGraphSelection(
      [cdGraphId('CD_TOP'), fdcGraphId('StigmaX')],
      fdcGraphId('Brightness')
    ),
    ['cd:CD_TOP', 'fdc:StigmaX', 'fdc:Brightness']
  )
})

test('drill does not duplicate an already-selected FDC', () => {
  const selected = [cdGraphId('CD_TOP'), fdcGraphId('StigmaX')]
  assert.deepEqual(
    addGraphSelection(selected, fdcGraphId('StigmaX')),
    selected
  )
})
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/graphSelection.test.ts
```

Expected: FAIL because `graphSelection.ts` does not exist.

- [ ] **Step 3: Implement the minimal pure selection module**

Create `front-dev-home/app/utils/skewvoirAnalysis/graphSelection.ts`:

```ts
export type GraphSelectionId = `cd:${string}` | `fdc:${string}`

export const cdGraphId = (parameter: string): GraphSelectionId =>
  `cd:${parameter}`

export const fdcGraphId = (parameter: string): GraphSelectionId =>
  `fdc:${parameter}`

export const graphSelectionIds = (
  cdParameter: string,
  fdcParameters: readonly string[]
): GraphSelectionId[] => [
  cdGraphId(cdParameter),
  ...fdcParameters.map(fdcGraphId)
]

export const selectCdOnly = (cdParameter: string): GraphSelectionId[] => [
  cdGraphId(cdParameter)
]

export const toggleGraphSelection = (
  selected: readonly GraphSelectionId[],
  id: GraphSelectionId
): GraphSelectionId[] =>
  selected.includes(id)
    ? selected.filter(candidate => candidate !== id)
    : [...selected, id]

export const reconcileGraphSelection = (
  selected: readonly GraphSelectionId[],
  previousAvailable: readonly GraphSelectionId[],
  nextAvailable: readonly GraphSelectionId[]
): GraphSelectionId[] => {
  const previousWasFullySelected = previousAvailable.length > 0
    && previousAvailable.every(id => selected.includes(id))

  if (previousWasFullySelected) return [...nextAvailable]

  return nextAvailable.filter(id => selected.includes(id))
}

export const addGraphSelection = (
  selected: readonly GraphSelectionId[],
  id: GraphSelectionId
): GraphSelectionId[] =>
  selected.includes(id) ? [...selected] : [...selected, id]
```

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run:

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/graphSelection.test.ts
```

Expected: 9 tests pass.

- [ ] **Step 5: Run frontend typecheck for the new contract**

Run:

```bash
cd front-dev-home
npm run typecheck
```

Expected: exit 0.

- [ ] **Step 6: Commit only the pure selection seam**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/graphSelection.ts front-dev-home/app/utils/skewvoirAnalysis/graphSelection.test.ts
git diff --cached --check
git commit -m "feat(skewvoir): model FDC graph selection"
```

---

### Task 2: Tabbed workbench and selectable individual graphs

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceWorkbench.vue:39-157`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceWorkbench.vue:161-275`

**Interfaces:**

- Consumes: every function and `GraphSelectionId` from Task 1.
- Consumes: `analysis.focusMsr`, `analysis.activeParam`, `analysis.fdcAxis`, `model.fdc`, `model.hasFdc`, existing `onSelect`.
- Produces: accessible `matrix`/`individual` tab state, graph selector state, `selectedFdc`, no-FDC rendering, and drill focus transfer.

- [ ] **Step 1: Import the Task 1 contract and declare view state**

Add after the existing `paramMatrix` import:

```ts
import {
  addGraphSelection,
  cdGraphId,
  fdcGraphId,
  graphSelectionIds,
  reconcileGraphSelection,
  selectCdOnly,
  toggleGraphSelection,
  type GraphSelectionId
} from '~/utils/skewvoirAnalysis/graphSelection'
```

Add after `const props`:

```ts
type FdcViewMode = 'matrix' | 'individual'

const viewMode = ref<FdcViewMode>('matrix')
const selectedGraphs = ref<GraphSelectionId[]>([])
const previousAvailableGraphs = ref<GraphSelectionId[]>([])
```

- [ ] **Step 2: Add ordered graph ids and reset/reconcile watchers**

Add immediately after the existing `model` computed. Declare the reset watcher
before the available-set watcher so an MSR/parameter change wins over an axis
reconciliation in the same flush:

```ts
const availableGraphIds = computed(() =>
  graphSelectionIds(
    props.analysis.activeParam.value,
    model.value.fdc.map(series => series.param)
  )
)

const graphResetKey = computed(() =>
  `${props.analysis.focusMsr.value ?? ''}\u0000${props.analysis.activeParam.value}`
)

watch(graphResetKey, () => {
  const next = availableGraphIds.value
  selectedGraphs.value = [...next]
  previousAvailableGraphs.value = [...next]
}, { immediate: true })

watch(availableGraphIds, (next) => {
  selectedGraphs.value = reconcileGraphSelection(
    selectedGraphs.value,
    previousAvailableGraphs.value,
    next
  )
  previousAvailableGraphs.value = [...next]
})

const selectedGraphSet = computed(() => new Set(selectedGraphs.value))
const showCdGraph = computed(() =>
  !model.value.hasFdc
  || selectedGraphSet.value.has(cdGraphId(props.analysis.activeParam.value))
)
const selectedFdc = computed(() =>
  model.value.fdc.filter(series =>
    selectedGraphSet.value.has(fdcGraphId(series.param))
  )
)
const noGraphsSelected = computed(() =>
  model.value.hasFdc
  && !showCdGraph.value
  && selectedFdc.value.length === 0
)

const selectAllGraphs = (): void => {
  selectedGraphs.value = [...availableGraphIds.value]
}

const selectOnlyCd = (): void => {
  selectedGraphs.value = selectCdOnly(props.analysis.activeParam.value)
}

const onGraphToggle = (id: GraphSelectionId): void => {
  selectedGraphs.value = toggleGraphSelection(selectedGraphs.value, id)
}
```

- [ ] **Step 3: Add accessible tab state and keyboard navigation**

Add after the graph selection handlers:

```ts
const tabOrder: FdcViewMode[] = ['matrix', 'individual']
const activeTabId = computed(() => `fdc-${viewMode.value}-tab`)
const activePanelId = computed(() => `fdc-${viewMode.value}-panel`)

const selectView = (mode: FdcViewMode): void => {
  viewMode.value = mode
}

const onTabKeydown = (event: KeyboardEvent): void => {
  const current = tabOrder.indexOf(viewMode.value)
  let next = current

  if (event.key === 'ArrowLeft') next = (current - 1 + tabOrder.length) % tabOrder.length
  else if (event.key === 'ArrowRight') next = (current + 1) % tabOrder.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = tabOrder.length - 1
  else return

  event.preventDefault()
  viewMode.value = tabOrder[next] ?? 'matrix'
  nextTick(() => {
    rootEl.value
      ?.querySelector<HTMLButtonElement>(`#fdc-${viewMode.value}-tab`)
      ?.focus()
  })
}
```

- [ ] **Step 4: Replace `drillTo` with selection-preserving tab transition**

Replace the existing `drillTo` body:

```ts
const drillTo = (param: string): void => {
  selectedGraphs.value = addGraphSelection(
    selectedGraphs.value,
    fdcGraphId(param)
  )
  viewMode.value = 'individual'

  nextTick(() => {
    requestAnimationFrame(() => {
      const target = rootEl.value
        ?.querySelector<HTMLElement>(`[data-fdc-param="${CSS.escape(param)}"]`)
      target?.focus({ preventScroll: true })
      target?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  })
}
```

- [ ] **Step 5: Add the tablist at the start of the normal-data branch**

Immediately inside `<template v-else>`, before either visualization:

```vue
<div
  role="tablist"
  aria-label="FDC 그래프 보기"
  class="inline-flex w-fit items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
  @keydown="onTabKeydown"
>
  <button
    id="fdc-matrix-tab"
    type="button"
    role="tab"
    :tabindex="viewMode === 'matrix' ? 0 : -1"
    :aria-selected="viewMode === 'matrix'"
    aria-controls="fdc-matrix-panel"
    class="rounded-[6px] px-3 py-1.5 text-xs font-medium transition-colors"
    :class="viewMode === 'matrix'
      ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
      : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
    @click="selectView('matrix')"
  >
    파라미터 매트릭스
  </button>
  <button
    id="fdc-individual-tab"
    type="button"
    role="tab"
    :tabindex="viewMode === 'individual' ? 0 : -1"
    :aria-selected="viewMode === 'individual'"
    aria-controls="fdc-individual-panel"
    class="rounded-[6px] px-3 py-1.5 text-xs font-medium transition-colors"
    :class="viewMode === 'individual'
      ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
      : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
    @click="selectView('individual')"
  >
    개별 그래프
  </button>
</div>
```

- [ ] **Step 6: Wrap active content in one conditional tabpanel and move matrix before sequence**

After the tablist, add:

```vue
<div
  :id="activePanelId"
  role="tabpanel"
  :aria-labelledby="activeTabId"
  class="space-y-3"
>
```

Move the existing `파라미터 매트릭스` `PanelFrame` to the first position
inside this wrapper and add `v-if="viewMode === 'matrix'"`. The existing
`측정 순서 (Sequence)` `PanelFrame` follows it with no condition. This yields
matrix → sequence in matrix mode.

Before the sequence panel, add the individual selector:

```vue
<section
  v-if="viewMode === 'individual' && model.hasFdc"
  class="dashboard-surface rounded-(--sk-r-card) p-3"
  aria-labelledby="fdc-graph-selector-title"
>
  <div class="flex flex-wrap items-center justify-between gap-2">
    <h2
      id="fdc-graph-selector-title"
      class="sk-title"
    >
      표시할 그래프
    </h2>
    <div class="flex items-center gap-1.5">
      <UButton
        size="xs"
        color="neutral"
        variant="soft"
        label="CD만 선택"
        @click="selectOnlyCd"
      />
      <UButton
        size="xs"
        color="neutral"
        variant="soft"
        label="전체 선택"
        @click="selectAllGraphs"
      />
    </div>
  </div>
  <div
    class="mt-2 flex flex-wrap gap-1.5"
    role="group"
    aria-label="개별 그래프 선택"
  >
    <button
      type="button"
      :aria-pressed="selectedGraphSet.has(cdGraphId(analysis.activeParam.value))"
      class="rounded-(--sk-r-chip) px-2.5 py-1 font-mono text-[11px] transition-colors"
      :class="selectedGraphSet.has(cdGraphId(analysis.activeParam.value))
        ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
        : 'bg-(--sk-chip-bg) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      @click="onGraphToggle(cdGraphId(analysis.activeParam.value))"
    >
      CD · {{ analysis.activeParamLabel.value }}
    </button>
    <button
      v-for="series in model.fdc"
      :key="series.param"
      type="button"
      :aria-pressed="selectedGraphSet.has(fdcGraphId(series.param))"
      class="rounded-(--sk-r-chip) px-2.5 py-1 font-mono text-[11px] transition-colors"
      :class="selectedGraphSet.has(fdcGraphId(series.param))
        ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
        : 'bg-(--sk-chip-bg) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      @click="onGraphToggle(fdcGraphId(series.param))"
    >
      {{ series.param }}
    </button>
  </div>
</section>
```

- [ ] **Step 7: Render only selected individual graphs**

Add `v-if="viewMode === 'individual' && showCdGraph"` to the CD `PanelFrame`.

Change the Dynamic FDC loop to:

```vue
<template v-if="viewMode === 'individual' && model.hasFdc">
  <EbeamSkewvoirPanelFrame
    v-for="series in selectedFdc"
    :key="series.param"
    :data-fdc-param="series.param"
    tabindex="-1"
    :title="`Dynamic FDC · ${series.param}`"
    :meta="fdcMeta(series)"
    icon="i-lucide-waves"
  >
    <template #actions>
      <span class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2 py-0.5 font-mono text-[10px] text-(--sk-warn)">
        데모 데이터 · 방법 검증 불가
      </span>
    </template>
    <EbeamSkewvoirFdcSequenceTrend
      :points="series.points"
      :sequences="model.sequences"
      :name="series.param"
      :unit="series.unit"
      :nominal="series.nominal"
      :focused="analysis.focusedSequence.value"
      :color="fdcColorByParam[series.param] ?? cdColor"
      @select="onSelect"
    />
  </EbeamSkewvoirPanelFrame>
</template>
```

After that loop, add the selected-empty state:

```vue
<div
  v-if="viewMode === 'individual' && noGraphsSelected"
  class="dashboard-surface flex flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 py-6 text-center"
>
  <p class="sk-title">
    선택된 그래프가 없습니다
  </p>
  <p class="sk-body">
    위 버튼에서 확인할 CD 또는 FDC 그래프를 선택하세요.
  </p>
</div>
```

Keep one `FDC 없음` block after the conditional individual graphs. Change its
condition to `v-if="!model.hasFdc"` so it appears in both tabs. Close the active
tabpanel wrapper after this block.

- [ ] **Step 8: Run the focused logic tests**

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/graphSelection.test.ts app/utils/skewvoirAnalysis/sequence.test.ts
```

Expected: all tests pass.

- [ ] **Step 9: Run typecheck and lint the changed component**

```bash
cd front-dev-home
npm run typecheck
npx eslint app/components/ebeam/skewvoir/fdc/SequenceWorkbench.vue app/utils/skewvoirAnalysis/graphSelection.ts app/utils/skewvoirAnalysis/graphSelection.test.ts
```

Expected: both commands exit 0. If whole-tree lint is run later, distinguish
pre-existing untouched-file failures from errors in these exact paths.

- [ ] **Step 10: Commit the complete workbench interaction**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceWorkbench.vue
git diff --cached --check
git commit -m "feat(skewvoir): switch between selectable FDC graph views"
```

---

### Task 3: Equal-width CD matrix cell

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/fdc/ParamMatrix.vue:95-142`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts:64-71` (existing invariant)

**Interfaces:**

- Consumes: the existing invariant that the CD row contains exactly one cell at `colIdx = 0`.
- Produces: every matrix grid uses one column coordinate; every axis title truncates at 112 px.

- [ ] **Step 1: Re-run the CD-row invariant before changing presentation**

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts
```

Expected: PASS, including `row 0 is the CD reference row carrying the active CD parameter`.

- [ ] **Step 2: Remove the CD range coordinate**

In `ParamMatrix.vue`, delete `const cols = props.model.columns` and replace:

```ts
coord: row.kind === 'cd' ? [[colKey(0), colKey(cols - 1)], row.label] : [colKey(colIdx), row.label],
```

with:

```ts
coord: [colKey(colIdx), row.label],
```

Update the adjacent comment to:

```ts
// Every cell occupies one matrix column. The model guarantees that the CD row
// has exactly one cell at colIdx 0, so CD keeps the same width as each FDC cell.
```

- [ ] **Step 3: Apply one title truncation rule to CD and FDC axes**

Add between `nameGap` and `nameTextStyle`:

```ts
nameTruncate: {
  maxWidth: 112,
  ellipsis: '…'
},
```

Do not change the `row.kind === 'cd'` symbol branch, line data, click mapping,
shared dataZoom, row height, or matrix column cap.

- [ ] **Step 4: Run matrix tests and typecheck**

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts
npm run typecheck
npx eslint app/components/ebeam/skewvoir/fdc/ParamMatrix.vue
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit the matrix presentation change**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/fdc/ParamMatrix.vue
git diff --cached --check
git commit -m "fix(skewvoir): align the CD matrix cell width"
```

---

### Task 4: Distinct image-event color

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue:3-13`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue:29-39`

**Interfaces:**

- Consumes: existing failure/image/alignment booleans from `SeqEvent`.
- Produces: failure red, image sky blue, alignment green in legend and cells.

- [ ] **Step 1: Change the image legend marker**

Replace:

```vue
<span class="inline-block h-2 w-2 rounded-full bg-(--sk-brand)" /> 이미지
```

with:

```vue
<span class="inline-block h-2 w-2 rounded-full bg-sky-600 dark:bg-sky-400" /> 이미지
```

- [ ] **Step 2: Change the per-sequence image marker**

Replace:

```vue
:class="cell.image ? 'bg-(--sk-brand)' : 'bg-transparent'"
```

with:

```vue
:class="cell.image ? 'bg-sky-600 dark:bg-sky-400' : 'bg-transparent'"
```

Do not change the selected-sequence brand ring, failure `--sk-bad`, alignment
`--sk-ok`, event order, tooltip copy, or event derivation.

- [ ] **Step 3: Run scoped static verification**

```bash
cd front-dev-home
npx eslint app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue
rg -n "bg-sky-600 dark:bg-sky-400|cell\\.failure|cell\\.alignment" app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue
```

Expected: ESLint exits 0; `rg` shows the sky class in the legend and image cell,
with failure and alignment branches still present.

- [ ] **Step 4: Commit the event-lane color**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue
git diff --cached --check
git commit -m "fix(skewvoir): distinguish image events in the FDC lane"
```

---

### Task 5: Integrated verification and main publication

**Files:**

- Verify only: all files from Tasks 1-4

**Interfaces:**

- Consumes: the complete feature from Tasks 1-4.
- Produces: evidence that logic, types, scoped lint, source cleanliness, and browser behavior match the spec.

- [ ] **Step 1: Run all frontend automated gates**

```bash
cd front-dev-home
npm test
npm run typecheck
npx eslint app/utils/skewvoirAnalysis/graphSelection.ts app/utils/skewvoirAnalysis/graphSelection.test.ts app/components/ebeam/skewvoir/fdc/SequenceWorkbench.vue app/components/ebeam/skewvoir/fdc/ParamMatrix.vue app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue
```

Expected: all commands exit 0.

- [ ] **Step 2: Run source and secret hygiene checks**

From the worktree root:

```bash
git diff --check main...HEAD
git status --short
git diff --stat main...HEAD
git diff main...HEAD -- front-dev-home/app/utils/skewvoirAnalysis/graphSelection.ts front-dev-home/app/utils/skewvoirAnalysis/graphSelection.test.ts front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceWorkbench.vue front-dev-home/app/components/ebeam/skewvoir/fdc/ParamMatrix.vue front-dev-home/app/components/ebeam/skewvoir/fdc/SequenceEventLane.vue
```

Expected: clean worktree; diff contains only the five intended implementation
paths and no credentials, environment values, `.remember`, or generated files.

- [ ] **Step 3: Start the existing frontend/backend and verify the running app**

Use the repository's existing commands:

```bash
.venv/bin/python index.py
```

and, in a second terminal:

```bash
cd front-dev-home
npm run dev
```

Open the CD-SEM Skewvoir analysis route, select one MSR, and enter `FDC 분석`.
Use the browser-control skill for interactive verification.

- [ ] **Step 4: Verify matrix mode**

Confirm in light and dark mode:

- `파라미터 매트릭스` is selected by default.
- DOM order is tab switch → parameter matrix → measurement sequence.
- CD occupies exactly one matrix column and matches FDC cell width.
- CD/FDC captions truncate instead of overflowing.
- failure is red, image is sky blue, and alignment is green.
- switching to individual and back resets matrix dataZoom to the full range.

- [ ] **Step 5: Verify individual mode and selection rules**

Confirm:

- initial individual mode shows CD and all FDC graphs.
- `CD만 선택`, `전체 선택`, and each parameter toggle work.
- selected graphs remain in model order and render vertically.
- all-off shows only the selected-empty message after measurement sequence.
- changing focus MSR or active CD parameter resets selection to all without changing the active view.
- changing FDC axis from an all-selected state selects the full new set.
- changing FDC axis from a custom state preserves only the intersection.

- [ ] **Step 6: Verify keyboard, drill, and no-FDC states**

Confirm:

- only the active tab is in the Tab order.
- `ArrowLeft`, `ArrowRight`, `Home`, and `End` move focus and activate the correct view.
- each tab's `aria-controls` and the active panel's `aria-labelledby` match.
- clicking a matrix FDC cell moves the shared sequence cursor, preserves existing graph choices, adds the clicked FDC, opens individual mode, focuses its panel, and scrolls it into view.
- a no-FDC MSR hides graph selectors, always shows CD in individual mode, and shows `FDC 없음` with `fdcReason` in both views.
- loading, error, and no-measurement states do not show the view tabs.

- [ ] **Step 7: Re-run final cleanliness checks after browser verification**

```bash
git status --short --branch
git diff --check main...HEAD
git log --oneline main..HEAD
```

Expected: clean worktree with four scoped implementation commits.

- [ ] **Step 8: Fast-forward main, push, and remove the worktree only when the user authorizes publication**

Back in the main tree, first verify that no other session advanced `main`.
Then follow the repository workflow:

```bash
git merge --ff-only work/fdc-graph-views
git push origin main
git worktree remove ../skewnono-fdc-graph-views
git branch -d work/fdc-graph-views
git worktree list
```

Expected: `origin/main` contains the four implementation commits and the
temporary worktree/branch are removed. If the actual worktree path chosen by
`using-git-worktrees` differs, use that exact validated path in the remove
command. Do not publish or remove the worktree without explicit user
authorization.

---

## Plan Self-Review Checklist

- Spec coverage: view tabs, selection defaults/reconciliation, no-FDC, event color, CD width, drill focus, accessibility, dataZoom tradeoff, tests, browser verification, and publication isolation are each assigned to a task.
- Type consistency: every Task 2 function name and `GraphSelectionId` matches Task 1 exactly.
- State consistency: MSR/parameter reset and axis-only reconciliation are separate watchers with explicit order.
- Empty-state consistency: all-off is possible only when `model.hasFdc`; no-FDC always renders CD and one reason panel.
- Interaction consistency: matrix click still calls existing `onSelect` before `drillTo`, and `drillTo` adds only the clicked FDC.
- Scope consistency: no backend, API, URL, persisted store, dependency, or ECharts wrapper change is included.
