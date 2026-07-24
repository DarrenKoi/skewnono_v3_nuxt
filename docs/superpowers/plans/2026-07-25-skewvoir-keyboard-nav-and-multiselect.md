# Skewvoir Keyboard Navigation + Measurement-Point Multi-Select — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add up/down keyboard navigation to the two skewvoir analysis dashboard tables (Measurement Points, 파라미터 요약) and add checkbox multi-selection to Measurement Points that highlights the chosen sites on the wafer map / radius plot and scopes the copy/Excel export.

**Architecture:** Pure cursor + selection logic lives in `app/utils/` (unit-testable under `node --test`); the two table components attach keyboard handlers and a checkbox column that call existing/new composable APIs. A new `selectedSequences` shared state in `useSkewvoirAnalysis.ts` is threaded to the wafer/radius charts as a `selected-seqs` prop, rendered as an extra scatter series alongside the existing `outlier-seqs` / focus rings.

**Tech Stack:** Nuxt 4 SPA (`ssr: false`), Vue 3 `<script setup>`, Nuxt UI 4 (`UCheckbox`), ECharts, `node:test` + `node:assert/strict` for pure-logic tests.

## Global Constraints

- **Test harness:** `npm test` runs `node --test "app/**/*.test.ts"`. The Nuxt runtime (`useState`/`computed`/`watch`) is UNDEFINED there, so the composable cannot be imported and driven directly. Only **pure functions in `app/utils/*.ts`** get unit tests; component + composable-wiring behavior is verified via `/verify` and `npm run lint`. (See `app/composables/useSkewvoirAnalysis.focusCache.test.ts:4-9`.)
- **Lint:** `npm run lint` (eslint) must pass. Run `npm run lint:md` after editing Markdown.
- **No new deps.** Use `UCheckbox` (already used across the app; supports `indeterminate`).
- **Reactivity, not debounce:** cursor/selection state updates immediately. Only add `requestAnimationFrame` coalescing for chart redraws IF `/verify` shows key-repeat stutter (do not add pre-emptively).
- **Reset rules (Part B):** `selectedSequences` clears on focus-MSR change; it is KEPT across `activeParam` change.
- **Commit style:** `type(scope): summary` with a body. End messages with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- `app/utils/tableCursor.ts` — **new.** Pure cursor math shared by both tables (`nextCursorIndex`).
- `app/utils/tableCursor.test.ts` — **new.** Unit tests for the cursor math.
- `app/utils/mpSelection.ts` — **new.** Pure selection helpers (`toggleSeq`, `headerState`, `pickExportRows`).
- `app/utils/mpSelection.test.ts` — **new.** Unit tests for the selection helpers.
- `app/composables/useSkewvoirAnalysis.ts` — **modify.** Add `selectedSequences` state + API + reset; export them.
- `app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue` — **modify.** Keyboard nav + checkbox column + Space toggle + export scoping.
- `app/components/ebeam/skewvoir/dashboard/ParamSummary.vue` — **modify.** Keyboard nav (move `activeParam`) + Space/Enter toggle.
- `app/components/ebeam/skewvoir/dashboard/WaferMap.vue` — **modify.** Pass `:selected-seqs`.
- `app/components/ebeam/skewvoir/WaferMap.vue` — **modify.** Accept `selectedSeqs`, render a selected-points scatter series.
- `app/components/ebeam/skewvoir/WaferDetailModal.vue` — **modify.** Pass `:selected-seqs` through (it already forwards `focused-sequence`/`outlier-seqs`).
- `app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue` — **modify.** Pass `:selected-seqs`.
- `app/components/ebeam/skewvoir/RadiusChart.vue` — **modify.** Accept `selectedSeqs`, render a selected-points scatter series.

---

## Task 1: Cursor math utility (`tableCursor.ts`)

**Files:**
- Create: `app/utils/tableCursor.ts`
- Test: `app/utils/tableCursor.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `type CursorKey = 'ArrowDown' | 'ArrowUp' | 'Home' | 'End'`
  - `nextCursorIndex(key: CursorKey, current: number, len: number): number | null` — new index, or `null` for no-op (empty list). `current < 0` or out of range means "no row focused yet": ArrowDown → 0, ArrowUp → last. (A shrinking list is handled by callers deriving `current` from a stable row key via `findIndex`, which returns -1 when the row is gone — so no separate clamp helper is needed.)

- [ ] **Step 1: Write the failing test**

Create `app/utils/tableCursor.test.ts`:

```ts
// Pure-logic tests for tableCursor. Run: node --test app/utils/tableCursor.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nextCursorIndex } from './tableCursor.ts'

test('empty list is a no-op for every key', () => {
  for (const k of ['ArrowDown', 'ArrowUp', 'Home', 'End'] as const) {
    assert.equal(nextCursorIndex(k, 0, 0), null)
    assert.equal(nextCursorIndex(k, -1, 0), null)
  }
})

test('no row focused yet: Down → first, Up → last', () => {
  assert.equal(nextCursorIndex('ArrowDown', -1, 5), 0)
  assert.equal(nextCursorIndex('ArrowUp', -1, 5), 4)
})

test('arrows step by one and clamp at the edges (no wrap)', () => {
  assert.equal(nextCursorIndex('ArrowDown', 2, 5), 3)
  assert.equal(nextCursorIndex('ArrowDown', 4, 5), 4) // clamped at last
  assert.equal(nextCursorIndex('ArrowUp', 2, 5), 1)
  assert.equal(nextCursorIndex('ArrowUp', 0, 5), 0) // clamped at first
})

test('Home/End jump to the ends', () => {
  assert.equal(nextCursorIndex('Home', 3, 5), 0)
  assert.equal(nextCursorIndex('End', 1, 5), 4)
})

test('an out-of-range current index is treated as unfocused', () => {
  assert.equal(nextCursorIndex('ArrowDown', 9, 5), 0)
  assert.equal(nextCursorIndex('ArrowUp', 9, 5), 4)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/tableCursor.test.ts`
Expected: FAIL — cannot find module `./tableCursor.ts`.

- [ ] **Step 3: Write minimal implementation**

Create `app/utils/tableCursor.ts`:

```ts
// Shared keyboard-cursor math for the analysis dashboard tables. Pure so it can
// be unit-tested under `node --test` (the Nuxt runtime is unavailable there).
export type CursorKey = 'ArrowDown' | 'ArrowUp' | 'Home' | 'End'

/**
 * Next cursor index for a keypress over a list of `len` rows.
 * Returns null for an empty list (no-op). A `current` that is negative or out
 * of range means "nothing focused yet": ArrowDown starts at the first row,
 * ArrowUp at the last. Edges clamp (no wraparound).
 */
export function nextCursorIndex(key: CursorKey, current: number, len: number): number | null {
  if (len <= 0) return null
  const cur = current < 0 || current >= len ? -1 : current
  switch (key) {
    case 'ArrowDown': return cur < 0 ? 0 : Math.min(cur + 1, len - 1)
    case 'ArrowUp': return cur < 0 ? len - 1 : Math.max(cur - 1, 0)
    case 'Home': return 0
    case 'End': return len - 1
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/tableCursor.test.ts`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/tableCursor.ts front-dev-home/app/utils/tableCursor.test.ts
git commit -m "feat(skewvoir): add pure table-cursor math for keyboard nav

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Measurement Points keyboard navigation

**Files:**
- Modify: `app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue`

**Interfaces:**
- Consumes: `nextCursorIndex` (Task 1); existing `analysis.setFocusedSequence`, `analysis.focusedSequence` (`useSkewvoirAnalysis.ts:251-254`).
- Produces: a focusable scroll container + arrow/Home/End navigation that drives `focusedSequence`. (Space handling is added in Task 5.)

This is a component edit; the pure logic it relies on is already tested in Task 1. Verify via lint + `/verify`.

- [ ] **Step 1: Add imports + cursor state (script)**

In `MeasurementPoints.vue`, add to the imports near the top of `<script setup>` (after the existing `import ... csvDownload` line):

```ts
import { nextCursorIndex, type CursorKey } from '~/utils/tableCursor'
```

Then, after the `rows` computed (around `MeasurementPoints.vue:250`), add:

```ts
// Keyboard cursor: identify the focused row by its stable `key` so sort/filter
// changes don't desync it. Current index is re-derived from the visible rows.
const scrollEl = ref<HTMLElement | null>(null)
const cursorKey = ref<string | null>(null)

const cursorIndex = computed(() => {
  if (cursorKey.value) {
    const i = rows.value.findIndex(r => r.key === cursorKey.value)
    if (i >= 0) return i
  }
  // Fall back to the first row matching the shared focused sequence.
  const fseq = props.analysis.focusedSequence.value
  return fseq == null ? -1 : rows.value.findIndex(r => r.seq === fseq)
})

const focusRowAt = (index: number) => {
  const row = rows.value[index]
  if (!row) return
  cursorKey.value = row.key
  props.analysis.setFocusedSequence(row.seq)
  nextTick(() => {
    scrollEl.value
      ?.querySelector(`[data-row-key="${CSS.escape(row.key)}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  })
}

const onRowClick = (p: Point) => {
  cursorKey.value = p.key
  props.analysis.setFocusedSequence(p.seq)
  scrollEl.value?.focus()
}

const onKeydown = (e: KeyboardEvent) => {
  const nav = ['ArrowDown', 'ArrowUp', 'Home', 'End']
  if (!nav.includes(e.key)) return
  e.preventDefault()
  const next = nextCursorIndex(e.key as CursorKey, cursorIndex.value, rows.value.length)
  if (next != null) focusRowAt(next)
}
```

- [ ] **Step 2: Wire the scroll container + rows (template)**

Change the results container (`MeasurementPoints.vue:44-47`) from:

```html
    <div
      v-else-if="rows.length"
      class="min-h-0 flex-1 overflow-auto"
    >
```

to:

```html
    <div
      v-else-if="rows.length"
      ref="scrollEl"
      tabindex="0"
      role="grid"
      class="min-h-0 flex-1 overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-(--sk-brand)/40"
      @keydown="onKeydown"
    >
```

Change the row `<tr>` (`MeasurementPoints.vue:81-90`) so it carries a data key, an aria-selected flag, and routes the click through `onRowClick`:

```html
          <tr
            v-for="p in rows"
            :key="p.key"
            :data-row-key="p.key"
            :aria-selected="p.seq === analysis.focusedSequence.value"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-200 last:border-0"
            :class="[
              p.kind === 'failed' ? 'text-(--sk-ink-muted)' : 'text-(--sk-ink)',
              p.seq === analysis.focusedSequence.value ? 'bg-(--sk-brand)/15' : 'hover:bg-(--sk-chip-bg)'
            ]"
            @click="onRowClick(p)"
          >
```

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: PASS (no errors in `MeasurementPoints.vue`).

- [ ] **Step 4: Verify in the app**

Follow `/verify` to launch Flask + Nuxt, open a CD-SEM skewvoir analysis with data, click a Measurement Points row, then press ↑/↓/Home/End. Expected: the highlighted row moves, the SEM image updates, the row scrolls into view when it leaves the viewport.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue
git commit -m "feat(skewvoir): keyboard up/down navigation in Measurement Points

Arrow/Home/End move the focused measurement point (focusedSequence), driving
the SEM image; the container is focusable and scrolls the active row into view.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 파라미터 요약 keyboard navigation

**Files:**
- Modify: `app/components/ebeam/skewvoir/dashboard/ParamSummary.vue`

**Interfaces:**
- Consumes: `nextCursorIndex` (Task 1); existing `analysis.setParam` (`useSkewvoirAnalysis.ts:553`), `analysis.activeParam`, `analysis.toggleParam` (`:216`), `analysis.paramSummaries`.
- Produces: arrows move `activeParam` over the visible summary rows (extras preserved); Space/Enter toggle the active row's comparison membership.

- [ ] **Step 1: Add imports + handlers (script)**

In `ParamSummary.vue`, add after the existing `defineProps` block (around `ParamSummary.vue:92`):

```ts
import { nextCursorIndex, type CursorKey } from '~/utils/tableCursor'

const scrollEl = ref<HTMLElement | null>(null)

const cursorIndex = computed(() =>
  summaries.value.findIndex(s => s.parameter === activeParam.value))

const focusRowAt = (index: number) => {
  const s = summaries.value[index]
  if (!s) return
  props.analysis.setParam(s.parameter) // move primary; extras (비교셋) preserved
  nextTick(() => {
    scrollEl.value
      ?.querySelector(`[data-row-key="${CSS.escape(s.parameter)}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  })
}

const onRowClick = (parameter: string, additive: boolean) => {
  props.analysis.toggleParam(parameter, additive)
  scrollEl.value?.focus()
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault()
    props.analysis.toggleParam(activeParam.value, true) // toggle comparison membership
    return
  }
  const nav = ['ArrowDown', 'ArrowUp', 'Home', 'End']
  if (!nav.includes(e.key)) return
  e.preventDefault()
  const next = nextCursorIndex(e.key as CursorKey, cursorIndex.value, summaries.value.length)
  if (next != null) focusRowAt(next)
}
```

Note: `import` statements must sit at the top of `<script setup>`, above the `const props = defineProps(...)` line — move the `import` line there and keep the handler `const`s after `activeParam`/`summaries` are declared.

- [ ] **Step 2: Wire the scroll container + rows (template)**

Change the results container (`ParamSummary.vue:8-11`) from:

```html
    <div
      v-if="summaries.length"
      class="min-h-0 flex-1 overflow-auto"
    >
```

to:

```html
    <div
      v-if="summaries.length"
      ref="scrollEl"
      tabindex="0"
      role="grid"
      class="min-h-0 flex-1 overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-(--sk-brand)/40"
      @keydown="onKeydown"
    >
```

Change the row `<tr>` (`ParamSummary.vue:41-49`) to carry a data key, aria flag, and route the click through `onRowClick`:

```html
          <tr
            v-for="s in summaries"
            :key="s.parameter"
            :data-row-key="s.parameter"
            :aria-selected="selectedSet.has(s.parameter)"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-150 hover:bg-(--sk-chip-bg)"
            :class="s.parameter === activeParam
              ? 'bg-(--sk-chip-bg)'
              : selectedSet.has(s.parameter) ? 'bg-(--sk-brand)/10' : ''"
            @click="onRowClick(s.parameter, $event.metaKey || $event.ctrlKey || $event.shiftKey)"
          >
```

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: PASS.

- [ ] **Step 4: Verify in the app**

Via `/verify`: click a 파라미터 요약 row, press ↑/↓ — the active parameter moves and the wafer map / distribution / SEM update; press Space/Enter — the active row toggles into/out of the comparison set (extras). Confirm arrow navigation does NOT clear an existing comparison set.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/ParamSummary.vue
git commit -m "feat(skewvoir): keyboard navigation in 파라미터 요약

Arrow/Home/End move the active parameter over the visible rows (comparison set
preserved); Space/Enter toggle the active row's comparison membership.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `selectedSequences` state + selection helpers

**Files:**
- Create: `app/utils/mpSelection.ts`
- Test: `app/utils/mpSelection.test.ts`
- Modify: `app/composables/useSkewvoirAnalysis.ts`

**Interfaces:**
- Consumes: nothing new for the utils; the composable uses existing `ws.selection`, `ws.toolType`, `useState`, `watch`.
- Produces:
  - Utils: `toggleSeq(list: number[], seq: number): number[]`; `headerState(visibleSeqs: number[], selected: ReadonlySet<number>): 'none' | 'some' | 'all'`; `pickExportRows<T extends { seq: number }>(rows: T[], selected: ReadonlySet<number>): T[]`.
  - Composable exports: `selectedSequences: Ref<number[]>`, `toggleSelectedSequence(seq: number): void`, `setSelectedSequences(list: number[]): void`, `clearSelectedSequences(): void`.

- [ ] **Step 1: Write the failing test**

Create `app/utils/mpSelection.test.ts`:

```ts
// Pure-logic tests for mpSelection. Run: node --test app/utils/mpSelection.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toggleSeq, headerState, pickExportRows } from './mpSelection.ts'

test('toggleSeq adds a missing seq and removes a present one', () => {
  assert.deepEqual(toggleSeq([1, 2], 3), [1, 2, 3])
  assert.deepEqual(toggleSeq([1, 2, 3], 2), [1, 3])
})

test('toggleSeq returns a new array (no mutation)', () => {
  const src = [1, 2]
  const out = toggleSeq(src, 3)
  assert.deepEqual(src, [1, 2])
  assert.notEqual(out, src)
})

test('headerState reflects the visible rows only', () => {
  assert.equal(headerState([], new Set([1])), 'none')
  assert.equal(headerState([1, 2, 3], new Set()), 'none')
  assert.equal(headerState([1, 2, 3], new Set([2])), 'some')
  assert.equal(headerState([1, 2, 3], new Set([1, 2, 3, 9])), 'all')
})

test('pickExportRows: empty selection → all rows; otherwise checked ∩ visible', () => {
  const rows = [{ seq: 1 }, { seq: 2 }, { seq: 3 }]
  assert.deepEqual(pickExportRows(rows, new Set()), rows)
  assert.deepEqual(pickExportRows(rows, new Set([2, 9])), [{ seq: 2 }])
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/mpSelection.test.ts`
Expected: FAIL — cannot find module `./mpSelection.ts`.

- [ ] **Step 3: Write minimal implementation**

Create `app/utils/mpSelection.ts`:

```ts
// Pure helpers for Measurement-Points multi-selection. Kept out of the
// composable so they can be unit-tested under `node --test`.

/** Toggle `seq` in a selection list, returning a new array. */
export function toggleSeq(list: number[], seq: number): number[] {
  return list.includes(seq) ? list.filter(s => s !== seq) : [...list, seq]
}

/**
 * Tri-state for a select-all header checkbox, computed over the VISIBLE rows
 * only: 'none' (nothing visible selected), 'some' (partial → indeterminate),
 * 'all' (every visible row selected). An empty visible set is 'none'.
 */
export function headerState(
  visibleSeqs: number[],
  selected: ReadonlySet<number>
): 'none' | 'some' | 'all' {
  if (visibleSeqs.length === 0) return 'none'
  let hit = 0
  for (const s of visibleSeqs) if (selected.has(s)) hit++
  if (hit === 0) return 'none'
  return hit === visibleSeqs.length ? 'all' : 'some'
}

/** Export target: all rows when nothing is selected, else checked ∩ visible. */
export function pickExportRows<T extends { seq: number }>(
  rows: T[],
  selected: ReadonlySet<number>
): T[] {
  if (selected.size === 0) return rows
  return rows.filter(r => selected.has(r.seq))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/mpSelection.test.ts`
Expected: PASS.

- [ ] **Step 5: Add `selectedSequences` to the composable**

In `useSkewvoirAnalysis.ts`, right after the `focusedSequence` block (`useSkewvoirAnalysis.ts:251-257`), add:

```ts
  // Measurement-point multi-selection (checkboxes in the points table). A set
  // of measurement sequences the user has checked to highlight on the wafer map
  // / radius plot and to scope the copy/Excel export. Independent of
  // focusedSequence (the single keyboard/SEM cursor). useState so it survives
  // remounts; cleared when the focus MSR (wafer) changes, KEPT across
  // activeParam changes since a selection may span parameters.
  const selectedSequences = useState<number[]>(`skewvoir-selected-seqs-${ws.toolType}`, () => [])
  const toggleSelectedSequence = (seq: number) => {
    selectedSequences.value = toggleSeq(selectedSequences.value, seq)
  }
  const setSelectedSequences = (list: number[]) => {
    selectedSequences.value = list
  }
  const clearSelectedSequences = () => {
    selectedSequences.value = []
  }
  watch(() => ws.selection.value?.msr, () => {
    selectedSequences.value = []
  })
```

Add the import near the top of `useSkewvoirAnalysis.ts` (with the other `~/utils` imports):

```ts
import { toggleSeq } from '~/utils/mpSelection'
```

Add to the `return { ... }` object (near `focusedSequence`/`setFocusedSequence`, around `useSkewvoirAnalysis.ts:561-562`):

```ts
    selectedSequences,
    toggleSelectedSequence,
    setSelectedSequences,
    clearSelectedSequences,
```

- [ ] **Step 6: Lint + full test run**

Run: `cd front-dev-home && npm run lint && npm test`
Expected: lint PASS; all `node --test` tests PASS (including the two new util files).

- [ ] **Step 7: Commit**

```bash
git add front-dev-home/app/utils/mpSelection.ts front-dev-home/app/utils/mpSelection.test.ts front-dev-home/app/composables/useSkewvoirAnalysis.ts
git commit -m "feat(skewvoir): add selectedSequences multi-select state

Shared set of checked measurement sequences with toggle/set/clear API and pure
selection helpers (toggleSeq/headerState/pickExportRows). Clears on MSR change,
kept across parameter change. Independent of the single focusedSequence cursor.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Measurement Points checkbox column + export scoping + Space toggle

**Files:**
- Modify: `app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue`

**Interfaces:**
- Consumes: `analysis.selectedSequences`, `analysis.toggleSelectedSequence`, `analysis.setSelectedSequences` (Task 4); `headerState`, `pickExportRows` (Task 4); the `onKeydown`/`cursorIndex` added in Task 2.
- Produces: a checkbox column right of MP, a header select-all, Space toggling the focused row, and export scoped to the selection.

- [ ] **Step 1: Add selection imports + derived state (script)**

Add to imports:

```ts
import { headerState, pickExportRows } from '~/utils/mpSelection'
```

After the cursor state added in Task 2, add:

```ts
const selectedSet = computed(() => new Set(props.analysis.selectedSequences.value))
const visibleSeqs = computed(() => rows.value.map(r => r.seq))
const headerCheck = computed(() => headerState(visibleSeqs.value, selectedSet.value))

const toggleAllVisible = () => {
  if (headerCheck.value === 'all') {
    // Clear only the visible rows from the selection (keep off-screen picks).
    const visible = new Set(visibleSeqs.value)
    props.analysis.setSelectedSequences(
      props.analysis.selectedSequences.value.filter(s => !visible.has(s)))
  } else {
    // Add every visible seq (union with any off-screen picks).
    const union = new Set(props.analysis.selectedSequences.value)
    for (const s of visibleSeqs.value) union.add(s)
    props.analysis.setSelectedSequences([...union])
  }
}
```

- [ ] **Step 2: Extend `onKeydown` with Space (script)**

In the `onKeydown` added in Task 2, add a Space branch at the top of the function body (before the `nav` array):

```ts
  if (e.key === ' ') {
    e.preventDefault()
    const row = rows.value[cursorIndex.value]
    if (row) props.analysis.toggleSelectedSequence(row.seq)
    return
  }
```

- [ ] **Step 3: Scope the export to the selection (script)**

Change `pointsTable()` (`MeasurementPoints.vue:256`) so its row source respects the selection. Replace `rows.value.map(...)` with a scoped source:

```ts
const pointsTable = () => ({
  headers: ['PARAM', 'MP', 'SEQ', 'X', 'Y', 'DATA', 'RADIUS_mm', 'STATUS'],
  rows: pickExportRows(rows.value, selectedSet.value).map(p => [
    p.param,
    p.mp,
    p.seq,
    p.x ?? '',
    p.y ?? '',
    p.cd ?? '',
    p.radius.toFixed(2),
    badgeLabel(p.kind)
  ])
})
```

- [ ] **Step 4: Reflect the selection count in `meta` (script)**

Update the `meta` computed (`MeasurementPoints.vue:291-296`) to append a selected count:

```ts
const meta = computed(() => {
  const paramNote = multiParam.value ? `${selectedParams.value.length} params · ` : ''
  const selNote = selectedSet.value.size ? ` · ${selectedSet.value.size} 선택` : ''
  return (filter.value === '전체'
    ? `${paramNote}${allPoints.value.length} sites · ${flaggedCount.value} 이상·실패`
    : `${paramNote}${flaggedCount.value} 이상·실패`) + selNote
})
```

- [ ] **Step 5: Add the checkbox column (template)**

In the `<thead>`, replace the columns `v-for` th block (`MeasurementPoints.vue:51-71`) so the checkbox header sits immediately after the MP column. Wrap the loop in a `<template>` and emit an extra th after `col.key === 'mp'`:

```html
            <template
              v-for="col in columns"
              :key="col.key"
            >
              <th
                scope="col"
                :aria-sort="ariaSort(col.key)"
                class="cursor-pointer select-none px-1.5 py-1.5 font-semibold whitespace-nowrap hover:text-(--sk-ink)"
                :class="col.align === 'right' ? 'text-right' : 'text-left'"
                @click="sortBy(col.key)"
              >
                <span
                  class="inline-flex items-center gap-0.5"
                  :class="col.align === 'right' ? 'flex-row-reverse' : ''"
                >
                  {{ col.label }}
                  <UIcon
                    :name="sortIcon(col.key)"
                    class="h-3 w-3"
                    :class="sortKey === col.key ? 'text-(--sk-brand)' : 'text-(--sk-ink-subtle)'"
                  />
                </span>
              </th>
              <th
                v-if="col.key === 'mp'"
                scope="col"
                class="px-1.5 py-1.5 text-center font-semibold"
              >
                <UCheckbox
                  size="xs"
                  aria-label="보이는 측정점 전체 선택"
                  :model-value="headerCheck === 'all'"
                  :indeterminate="headerCheck === 'some'"
                  @update:model-value="toggleAllVisible"
                />
              </th>
            </template>
```

In the `<tbody>`, insert a checkbox cell immediately after the MP `<td>` (`MeasurementPoints.vue:98-100`). After that `<td>` block, add:

```html
            <td
              class="px-1.5 py-1.5 text-center"
              @click.stop
            >
              <UCheckbox
                size="xs"
                :aria-label="`측정점 ${p.seq} 선택`"
                :model-value="selectedSet.has(p.seq)"
                @update:model-value="analysis.toggleSelectedSequence(p.seq)"
              />
            </td>
```

(The `@click.stop` on the cell keeps a checkbox click from also firing the row's `onRowClick` focus handler.)

- [ ] **Step 6: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: PASS.

- [ ] **Step 7: Verify in the app**

Via `/verify`: check several rows → the meta shows "N 선택"; the header checkbox goes indeterminate then all; Excel/clipboard export contains only the checked rows; with nothing checked, export contains all visible rows. Arrow to a row and press Space → its checkbox toggles. Switch parameter → selection persists; switch MSR → selection clears.

- [ ] **Step 8: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue
git commit -m "feat(skewvoir): checkbox multi-select in Measurement Points

Checkbox column right of MP with a tri-state select-all header; Space toggles
the focused row; copy/Excel scope to the checked rows (all when none checked);
meta shows the selected count.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Wafer map highlight for the selection

**Files:**
- Modify: `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`
- Modify: `app/components/ebeam/skewvoir/WaferMap.vue`
- Modify: `app/components/ebeam/skewvoir/WaferDetailModal.vue`

**Interfaces:**
- Consumes: `analysis.selectedSequences` (Task 4); the chart's existing `outlierSeqs`/`focusedSequence` render pattern (`WaferMap.vue:70-86`, `:240-246`).
- Produces: a `selectedSeqs: number[]` prop on the chart + detail modal, rendered as a distinct scatter series.

- [ ] **Step 1: Accept + render `selectedSeqs` in the chart (`app/components/ebeam/skewvoir/WaferMap.vue`)**

Add to the `defineProps` block (`WaferMap.vue:19-37`), after `outlierSeqs: number[]`:

```ts
  /** Sequences the user multi-selected in the points table (highlight halo). */
  selectedSeqs?: number[]
```

Add to the `withDefaults` defaults object:

```ts
  selectedSeqs: () => [],
```

After the `outlierPoints` computed (`WaferMap.vue:70-76`), add a mirror:

```ts
// Halo on any active point whose sequence is in the multi-selection set.
const selectedPoints = computed(() => {
  const picked = new Set(props.selectedSeqs)
  return activePoints.value
    .filter(p => p.seqs.some(s => picked.has(s)))
    .map(p => ({ name: String(p.seq), value: [p.x, p.y] }))
})
```

In the `series: [...]` array, add a selection series. Place it BEFORE the outlier series (`WaferMap.vue:240`) so the ◎ outlier ring and the focus ring stay visually on top:

```ts
    { type: 'scatter', symbol: 'circle', symbolSize: 22, data: selectedPoints.value,
      itemStyle: { color: SK_CHART.series, opacity: 0.18, borderColor: SK_CHART.series, borderWidth: 1.5 },
      silent: true, z: 3 },
```

- [ ] **Step 2: Thread the prop through the dashboard wrappers**

In `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`, add `:selected-seqs="analysis.selectedSequences.value"` to BOTH the main chart (`dashboard/WaferMap.vue:38-50`, next to `:outlier-seqs`) and the detail modal (`dashboard/WaferMap.vue:75-84`, next to `:outlier-seqs`):

```html
            :selected-seqs="analysis.selectedSequences.value"
```

In `app/components/ebeam/skewvoir/WaferDetailModal.vue`, add a matching optional prop to its plain `defineProps<{ ... }>()` block (`WaferDetailModal.vue:60-66`), after `outlierSeqs: number[]`:

```ts
  selectedSeqs?: number[]
```

Then forward it to the `<EbeamSkewvoirWaferMap>` it renders (`WaferDetailModal.vue:38-39`, next to `:outlier-seqs`):

```html
            :selected-seqs="selectedSeqs"
```

No default is needed here — when `selectedSeqs` is undefined the child chart's own `withDefaults` fills in `[]`.

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: PASS.

- [ ] **Step 4: Verify in the app**

Via `/verify`: check rows in Measurement Points → their sites show a translucent halo on the wafer map, distinct from the ◎ outlier ring and the focus ring; open the wafer detail modal → the same halos appear. Uncheck → halos disappear.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue front-dev-home/app/components/ebeam/skewvoir/WaferDetailModal.vue
git commit -m "feat(skewvoir): highlight multi-selected sites on the wafer map

Thread selectedSequences into the wafer chart + detail modal as selected-seqs,
rendered as a translucent halo distinct from the outlier and focus rings.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Radius plot highlight for the selection

**Files:**
- Modify: `app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue`
- Modify: `app/components/ebeam/skewvoir/RadiusChart.vue`

**Interfaces:**
- Consumes: `analysis.selectedSequences` (Task 4); the chart's existing `focused` render pattern (`RadiusChart.vue:64`, `:259-267`).
- Produces: a `selectedSeqs: number[]` prop on `RadiusChart`, rendered as a distinct scatter series.

- [ ] **Step 1: Accept + render `selectedSeqs` in `RadiusChart.vue`**

Add to the `defineProps` block (`RadiusChart.vue:14-23`), after `focusedSequence: number | null`:

```ts
  selectedSeqs?: number[]
```

Add to the `withDefaults` defaults object:

```ts
  selectedSeqs: () => [],
```

After the `focused` computed (`RadiusChart.vue:64`), add:

```ts
const selectedPts = computed(() => {
  const picked = new Set(props.selectedSeqs)
  return scatterData.value.filter(point => picked.has(Number(point.name)))
})
```

In the `series: [...]` array, add a selection series BEFORE the `focused` series (`RadiusChart.vue:259`) so the focus ring stays on top:

```ts
      {
        name: 'selected',
        type: 'scatter',
        symbolSize: 18,
        data: selectedPts.value,
        itemStyle: { color: SK_CHART.series, opacity: 0.18, borderColor: SK_CHART.series, borderWidth: 1.5 },
        tooltip: { show: false },
        silent: true,
        z: 5
      },
```

- [ ] **Step 2: Thread the prop through `dashboard/RadiusPlot.vue`**

Add `:selected-seqs="analysis.selectedSequences.value"` to the `<EbeamSkewvoirRadiusChart>` (`RadiusPlot.vue:38-44`, next to `:focused-sequence`):

```html
      :selected-seqs="analysis.selectedSequences.value"
```

(The `RadiusAnalysisDialog` highlight is out of scope — the dashboard plot is the primary spatial view. Leave the dialog unchanged.)

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: PASS.

- [ ] **Step 4: Verify in the app**

Via `/verify`: check rows in Measurement Points → the matching points on the Radius Plot show the translucent halo, distinct from the focus ring. Uncheck → halos disappear.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue
git commit -m "feat(skewvoir): highlight multi-selected points on the radius plot

Thread selectedSequences into RadiusChart as selected-seqs, rendered as a
translucent halo distinct from the focus ring.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] **Full test + lint sweep**

Run: `cd front-dev-home && npm test && npm run lint`
Expected: all `node --test` tests PASS; eslint clean.

- [ ] **End-to-end `/verify`**

Confirm the whole flow on a CD-SEM skewvoir analysis with data:
1. Click a Measurement Points row, arrow ↑/↓ → SEM image steps through; row scrolls into view.
2. Space on a focused row → checkbox toggles; halo appears on wafer map + radius plot.
3. Header select-all → indeterminate/all; export scoped to checked rows.
4. 파라미터 요약 arrows move the active parameter (comparison set preserved); Space/Enter toggles membership.
5. Switch parameter → selection persists; switch MSR → selection clears.
6. Hold ↓ (key-repeat) → confirm no visible stutter. If it stutters, add `requestAnimationFrame` coalescing to the wafer/radius chart option rebuild (per the spec's compute note) and re-verify.

- [ ] **Repeat the keyboard + highlight checks on the HV-SEM page** (`/ebeam/hv-sem/skewvoir/analysis`) — same components, different `tool-type`.
