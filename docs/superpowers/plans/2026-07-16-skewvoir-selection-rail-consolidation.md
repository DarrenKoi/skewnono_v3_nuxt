# Skewvoir Selection Rail Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the top `AnalysisContextBar` (단일 측정 / 세트 비교, 세트 편집, 분석 준비 상태) into the left rail's CURRENT SELECTION zone, with a compact rail view and a center "enlarge" modal for full detail.

**Architecture:** Pure frontend re-composition over the two existing composables (`useSkewvoirWorkspace`, `useSkewvoirAnalysis`) — no new state, no backend changes. The one piece of real logic (set-membership mutation with a focus guard) is extracted into a testable util module. The rest is view wiring: rebuild `LeftRail.vue`'s selection zone, add a new `SelectionDetailModal.vue`, and delete `AnalysisContextBar.vue`.

**Tech Stack:** Nuxt 4 + NuxtUI (`UModal`, `USelectMenu`, `UButton`, `UIcon`, `UKbd`, `UCheckbox`), Tailwind v4, `node --test` for pure-util characterization tests.

## Global Constraints

- Frontend only. **No** backend (`back_dev_home/`), composable API, or `ReadinessDrawer` internal changes — only the readiness-open *wiring* moves.
- Set vs. single scope stays governed by `?msrs=` length; do not change scope-entry logic. The searchable set editor stays gated to `scope === 'set'`.
- Membership writes go through `ws.setMsrs(list: string[])`; focus through `analysis.setFocusedMsr(msr: string)`. Both already exist — do not add new composable methods.
- `ParamNav` (parameter *selector*) stays in the Dashboard view body (`views/Dashboard.vue:14`) untouched; the rail shows only a read-only `activeParam` label.
- Korean UI copy uses the existing terms verbatim: `단일 측정`, `세트 비교`, `세트 편집`, `분석 준비 상태`, `선택 해제`, `기준`, `호환`, `로드`, `선택`, `제외`, `Focus`, `Parameter`.
- Run `npm run lint:md` after editing any Markdown. Run `npm run test` for util tests, `npm run typecheck` and `npm run lint` before final verification.
- Component auto-import names follow the path: `components/ebeam/skewvoir/workspace/SelectionDetailModal.vue` → `<EbeamSkewvoirWorkspaceSelectionDetailModal>`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/utils/skewvoirAnalysis/setEditing.ts` | **New.** Pure helpers: `removeFromSet(list, msr, focusMsr)` and `clearToFocus(focusMsr)` — the only real logic, with the focus guard. |
| `app/utils/skewvoirAnalysis/setEditing.test.ts` | **New.** `node --test` characterization tests for the two helpers. |
| `app/components/ebeam/skewvoir/workspace/SelectionDetailModal.vue` | **New.** Center enlarge modal: full selection fields, all counts, 기준, searchable set editor. |
| `app/components/ebeam/skewvoir/workspace/LeftRail.vue` | **Modify.** Rebuild the selection zone: scope badge + enlarge button, compact meta/counts, checkable MSR list (row=focus, checkbox=remove), 선택 해제, 분석 준비 상태 button; render the modal; emit `open-readiness`. |
| `app/components/ebeam/skewvoir/Workspace.vue` | **Modify.** Remove `AnalysisContextBar`; wire `@open-readiness` from `LeftRail`. |
| `app/components/ebeam/skewvoir/workspace/AnalysisContextBar.vue` | **Delete.** |

**Task order & dependencies:** Task 1 (helpers) → Task 2 (modal) → Task 3 (LeftRail, consumes both) → Task 4 (remove bar, depends on Task 3's emit existing). Each task ends independently testable.

---

### Task 1: Pure set-editing helpers

**Files:**
- Create: `front-dev-home/app/utils/skewvoirAnalysis/setEditing.ts`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/setEditing.test.ts`

**Interfaces:**
- Consumes: nothing (pure).
- Produces:
  - `removeFromSet(list: string[], msr: string, focusMsr: string): string[]` — returns a new list with `msr` removed, **unless** `msr === focusMsr` (guard: never drop the focused MSR), in which case the list is returned unchanged. Preserves order.
  - `clearToFocus(focusMsr: string): string[]` — returns `[focusMsr]` (empties the set down to the focus).

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/skewvoirAnalysis/setEditing.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { removeFromSet, clearToFocus } from './setEditing.ts'

test('removeFromSet drops the given msr and preserves order', () => {
  assert.deepEqual(
    removeFromSet(['a', 'b', 'c'], 'b', 'a'),
    ['a', 'c']
  )
})

test('removeFromSet never drops the focused msr (guard)', () => {
  assert.deepEqual(
    removeFromSet(['a', 'b', 'c'], 'a', 'a'),
    ['a', 'b', 'c']
  )
})

test('removeFromSet is a no-op when msr is absent', () => {
  assert.deepEqual(
    removeFromSet(['a', 'b'], 'z', 'a'),
    ['a', 'b']
  )
})

test('removeFromSet returns a new array (no mutation)', () => {
  const input = ['a', 'b']
  const out = removeFromSet(input, 'b', 'a')
  assert.notEqual(out, input)
  assert.deepEqual(input, ['a', 'b'])
})

test('clearToFocus returns just the focused msr', () => {
  assert.deepEqual(clearToFocus('b'), ['b'])
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && npm run test`
Expected: FAIL — `Cannot find module './setEditing.ts'` (module not created yet).

- [ ] **Step 3: Write minimal implementation**

Create `front-dev-home/app/utils/skewvoirAnalysis/setEditing.ts`:

```ts
// Pure set-membership helpers for the CURRENT SELECTION rail. The rail shows
// the compared set's members; unchecking a row removes it, but the focused MSR
// is never removable (the workspace must always keep an active measurement).
// Callers pass the result straight to `ws.setMsrs(...)`.

/** Remove `msr` from the set, unless it is the focused MSR (guarded). */
export const removeFromSet = (list: string[], msr: string, focusMsr: string): string[] => {
  if (msr === focusMsr) return list.slice()
  return list.filter(m => m !== msr)
}

/** Empty the set down to just the focused MSR (선택 해제). */
export const clearToFocus = (focusMsr: string): string[] => [focusMsr]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && npm run test`
Expected: PASS — all 5 `setEditing` tests pass (plus the rest of the suite unchanged).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/setEditing.ts front-dev-home/app/utils/skewvoirAnalysis/setEditing.test.ts
git commit -m "feat(skewvoir): add pure set-editing helpers for selection rail"
```

---

### Task 2: SelectionDetailModal (enlarge modal)

**Files:**
- Create: `front-dev-home/app/components/ebeam/skewvoir/workspace/SelectionDetailModal.vue`

**Interfaces:**
- Consumes: `ws: SkewvoirWorkspace`, `analysis: SkewvoirAnalysis` (same objects `LeftRail` receives). Reads: `ws.selection.value` (`.lot/.recipe/.eq/.mp/.capturedAt/.msr`), `analysis.scope.value`, `analysis.activeParam.value`, `analysis.manifest.value.counts` (`{ compatible, loaded, selected, excluded }`), `analysis.reference.value`, `analysis.candidateRows.value` (`MeasHistRow[]`), `ws.msrList.value`, `ws.setMsrs`.
- Produces: an open state via `defineModel<boolean>('open')`, consumed by `LeftRail` in Task 3 as `v-model:open`.

- [ ] **Step 1: Create the modal component**

Create `front-dev-home/app/components/ebeam/skewvoir/workspace/SelectionDetailModal.vue`:

```vue
<template>
  <UModal
    v-model:open="open"
    :title="scope === 'set' ? '세트 비교 · 상세' : '단일 측정 · 상세'"
    :ui="{ content: 'w-[92vw] sm:max-w-[560px]' }"
  >
    <template #body>
      <div
        v-if="ws.selection.value"
        class="flex flex-col gap-4"
      >
        <!-- Scope + Focus + Parameter -->
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span
            class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) px-2 py-0.5 text-[11px] font-semibold"
            :class="scope === 'set'
              ? 'bg-(--sk-accent-soft) text-(--sk-accent)'
              : 'bg-(--sk-chip-bg) text-(--sk-ink-muted)'"
          >
            <UIcon
              :name="scope === 'set' ? 'i-lucide-layers' : 'i-lucide-focus'"
              class="h-3.5 w-3.5"
            />
            {{ scope === 'set' ? '세트 비교' : '단일 측정' }}
          </span>
          <span class="flex items-baseline gap-1.5">
            <span class="sk-label">Focus</span>
            <span class="truncate font-mono text-[12px] font-semibold text-(--sk-ink)">{{ ws.selection.value.msr || '—' }}</span>
          </span>
          <span class="flex items-baseline gap-1.5">
            <span class="sk-label">Parameter</span>
            <span class="font-mono text-[12px] text-(--sk-ink)">{{ analysis.activeParam.value || '—' }}</span>
          </span>
        </div>

        <!-- Full selection fields -->
        <dl class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
          <div
            v-for="field in selectionFields"
            :key="field.label"
            class="flex items-baseline justify-between gap-2"
          >
            <dt class="sk-label">{{ field.label }}</dt>
            <dd
              class="truncate font-mono text-(--sk-ink)"
              :class="{ 'font-semibold': field.strong }"
            >{{ field.value }}</dd>
          </div>
        </dl>

        <!-- Counts -->
        <div class="flex flex-wrap items-center gap-1.5 border-t border-(--sk-border-soft) pt-3">
          <span class="rounded-(--sk-r-chip) bg-(--sk-ok-soft) px-2 py-0.5 font-mono text-[11px] text-(--sk-ok)">호환 {{ counts.compatible }}</span>
          <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 font-mono text-[11px] text-(--sk-ink-muted)">로드 {{ counts.loaded }}</span>
          <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 font-mono text-[11px] text-(--sk-ink-muted)">선택 {{ counts.selected }}</span>
          <span
            v-if="counts.excluded > 0"
            class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-2 py-0.5 font-mono text-[11px] text-(--sk-bad)"
          >제외 {{ counts.excluded }}</span>
        </div>

        <!-- Reference provenance -->
        <div
          v-if="referenceLabel"
          class="flex items-baseline gap-1.5"
        >
          <span class="sk-label shrink-0">기준</span>
          <span class="truncate font-mono text-[11px] text-(--sk-ink-muted)">{{ referenceLabel }}</span>
        </div>

        <!-- Searchable set editor (set scope only) — the place to add a new MSR -->
        <div
          v-if="scope === 'set'"
          class="flex flex-col gap-1.5 border-t border-(--sk-border-soft) pt-3"
        >
          <span class="sk-label">세트 편집</span>
          <USelectMenu
            :model-value="ws.msrList.value"
            multiple
            value-key="value"
            :items="candidateItems"
            :search-input="{ placeholder: 'lot / eq 로 검색…' }"
            placeholder="측정 추가/제거"
            size="sm"
            @update:model-value="ws.setMsrs"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { formatRecipeTimestamp } from '~/utils/recipeView'

const props = defineProps<{ ws: SkewvoirWorkspace, analysis: SkewvoirAnalysis }>()
const open = defineModel<boolean>('open', { default: false })

const scope = computed(() => props.analysis.scope.value)
const counts = computed(() => props.analysis.manifest.value.counts)

const selectionFields = computed(() => {
  const sel = props.ws.selection.value
  if (!sel) return []
  return [
    { label: 'Lot', value: sel.lot, strong: true },
    { label: 'Recipe', value: sel.recipe, strong: false },
    { label: 'EQ', value: sel.eq, strong: false },
    { label: 'MP', value: sel.mp, strong: false },
    { label: 'Captured', value: sel.capturedAt, strong: false }
  ]
})

const referenceLabel = computed(() => {
  const ref = props.analysis.reference.value
  if (!ref) return ''
  const recipe = ref.signature.recipe.state === 'known'
    ? ref.signature.recipe.value.recipeName
    : null
  return recipe ? `${ref.msr} · ${recipe}` : ref.msr
})

const candidateItems = computed(() =>
  props.analysis.candidateRows.value.map(r => ({
    label: `${formatRecipeTimestamp(r.timestamp)} · ${r.eqp_id} · ${r.lot_id}`,
    value: r.msr
  }))
)
</script>
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd front-dev-home && npm run typecheck`
Expected: PASS — no errors referencing `SelectionDetailModal.vue`. (The component is not yet mounted anywhere; this only confirms the file itself is sound.)

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/workspace/SelectionDetailModal.vue
git commit -m "feat(skewvoir): add SelectionDetailModal enlarge surface"
```

---

### Task 3: Rebuild LeftRail's CURRENT SELECTION zone

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue`

**Interfaces:**
- Consumes: `removeFromSet`, `clearToFocus` from Task 1; `<EbeamSkewvoirWorkspaceSelectionDetailModal>` from Task 2 (auto-imported); existing `ws`/`analysis`/`fab` props.
- Produces: emits `open-readiness: []` (consumed by `Workspace.vue` in Task 4).

- [ ] **Step 1: Replace the two selection sections and add the emit**

In `front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue`, replace the **비교 세트** section and the **Current selection (single)** section (the two `<section>` blocks spanning the `v-if="ws.selection.value && isSet"` and `v-else-if="ws.selection.value"` at lines 60–118) with the single consolidated block below. Leave the WORKSPACE section (lines 5–58) and the ACTIONS section (lines 120–142) unchanged.

```vue
    <!-- CURRENT SELECTION — scope, compact meta/counts, and the member list.
         Row click focuses an MSR (all views); the leading checkbox removes it
         from the compared set (the focused MSR is guarded, never removable).
         Enlarge (⤢) opens the full-detail modal; 분석 준비 상태 opens the drawer. -->
    <section
      v-if="ws.selection.value"
      class="space-y-2 border-t border-(--sk-border-soft) pt-4"
    >
      <div class="flex items-center justify-between gap-2 px-1">
        <span
          class="inline-flex items-center gap-1 rounded-(--sk-r-chip) px-1.5 py-0.5 text-[10.5px] font-semibold"
          :class="isSet
            ? 'bg-(--sk-accent-soft) text-(--sk-accent)'
            : 'bg-(--sk-chip-bg) text-(--sk-ink-muted)'"
        >
          <UIcon
            :name="isSet ? 'i-lucide-layers' : 'i-lucide-focus'"
            class="h-3 w-3"
          />
          {{ isSet ? '세트 비교' : '단일 측정' }}
        </span>
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          icon="i-lucide-maximize-2"
          aria-label="상세 보기"
          @click="detailOpen = true"
        />
      </div>

      <!-- Compact meta -->
      <dl class="space-y-1 px-1 text-[12px]">
        <div class="flex items-baseline justify-between gap-2">
          <dt class="sk-label">Focus</dt>
          <dd class="truncate font-mono font-semibold text-(--sk-ink)">{{ focusMsr || '—' }}</dd>
        </div>
        <div class="flex items-baseline justify-between gap-2">
          <dt class="sk-label">Param</dt>
          <dd class="truncate font-mono text-(--sk-ink)">{{ analysis.activeParam.value || '—' }}</dd>
        </div>
        <div class="flex items-baseline justify-between gap-2">
          <dt class="sk-label">Lot</dt>
          <dd class="truncate font-mono text-(--sk-ink)">{{ ws.selection.value.lot || '—' }}</dd>
        </div>
      </dl>

      <!-- Compact counts -->
      <div class="flex flex-wrap items-center gap-1 px-1">
        <span class="rounded-(--sk-r-chip) bg-(--sk-ok-soft) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-ok)">호환 {{ counts.compatible }}</span>
        <span
          v-if="counts.excluded > 0"
          class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-bad)"
        >제외 {{ counts.excluded }}</span>
      </div>

      <!-- MSR member list — row = focus, checkbox = membership (guarded) -->
      <template v-if="isSet">
        <div class="flex items-center justify-between px-1">
          <span class="sk-eyebrow">비교 세트 · {{ setChips.length }}</span>
          <button
            type="button"
            class="text-[11px] text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
            @click="deselectToFocus"
          >
            선택 해제
          </button>
        </div>
        <ul class="space-y-1">
          <li
            v-for="chip in setChips"
            :key="chip.msr"
            class="flex items-center gap-1.5"
          >
            <UCheckbox
              :model-value="true"
              :disabled="chip.active"
              :aria-label="`${chip.label} 세트에서 제거`"
              size="sm"
              @update:model-value="removeMember(chip.msr)"
            />
            <button
              type="button"
              class="flex min-w-0 flex-1 items-center gap-2 rounded-(--sk-r-nav) px-2 py-1.5 text-left font-mono text-[12px] transition-colors"
              :class="chip.active
                ? 'bg-(--sk-brand) font-semibold text-(--sk-brand-fg)'
                : 'text-(--sk-ink-muted) hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)'"
              :aria-pressed="chip.active"
              :title="chip.label"
              @click="props.analysis.setFocusedMsr(chip.msr)"
            >
              <UIcon
                :name="chip.active ? 'i-lucide-crosshair' : 'i-lucide-circle-dot'"
                class="h-3.5 w-3.5 shrink-0"
              />
              <span class="min-w-0 flex-1 truncate">{{ chip.label }}</span>
            </button>
          </li>
        </ul>
      </template>

      <!-- Readiness drawer opener -->
      <UButton
        block
        color="neutral"
        variant="soft"
        size="xs"
        class="justify-start"
        icon="i-lucide-list-checks"
        :label="`분석 준비 상태${counts.excluded > 0 ? ` · 제외 ${counts.excluded}` : ''}`"
        @click="emit('openReadiness')"
      />
    </section>

    <!-- Full-detail enlarge modal -->
    <EbeamSkewvoirWorkspaceSelectionDetailModal
      v-if="ws.selection.value"
      v-model:open="detailOpen"
      :ws="ws"
      :analysis="analysis"
    />
```

- [ ] **Step 2: Update the `<script setup>` — add emit, modal state, counts, and set-edit handlers**

In the same file's `<script setup lang="ts">`, add the `removeFromSet`/`clearToFocus` import, the `open-readiness` emit, the `detailOpen` ref, the `counts`/`focusMsr` computeds, and the `removeMember`/`deselectToFocus` handlers. Insert these alongside the existing `isSet`/`setChips` definitions (keep those unchanged). Add near the top of the script:

```ts
import { removeFromSet, clearToFocus } from '~/utils/skewvoirAnalysis/setEditing'

const emit = defineEmits<{ openReadiness: [] }>()

const detailOpen = ref(false)

const focusMsr = computed(() => props.ws.selection.value?.msr ?? '')
const counts = computed(() => props.analysis.manifest.value.counts)

// Uncheck removes the member (focused MSR is guarded inside removeFromSet).
const removeMember = (msr: string) => {
  props.ws.setMsrs(removeFromSet(props.analysis.msrList.value, msr, focusMsr.value))
}

// 선택 해제 — empty the set down to the focused MSR.
const deselectToFocus = () => {
  if (focusMsr.value) props.ws.setMsrs(clearToFocus(focusMsr.value))
}
```

- [ ] **Step 3: Type-check and lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: PASS — no errors in `LeftRail.vue`. (`AnalysisContextBar.vue` still exists and still compiles at this point; it is removed in Task 4.)

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue
git commit -m "feat(skewvoir): consolidate analysis context into LeftRail selection zone"
```

---

### Task 4: Remove AnalysisContextBar from the workspace

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/Workspace.vue`
- Delete: `front-dev-home/app/components/ebeam/skewvoir/workspace/AnalysisContextBar.vue`

**Interfaces:**
- Consumes: `LeftRail`'s `open-readiness` emit (Task 3).
- Produces: nothing new.

- [ ] **Step 1: Move the readiness wiring onto LeftRail and drop the bar**

In `front-dev-home/app/components/ebeam/skewvoir/Workspace.vue`:

Add the `@open-readiness` listener to the existing `<EbeamSkewvoirWorkspaceLeftRail>` (currently at lines 4–8):

```vue
      <EbeamSkewvoirWorkspaceLeftRail
        :ws="ws"
        :analysis="analysis"
        :fab="analysis.fab.value"
        @open-readiness="readinessOpen = true"
      />
```

Then delete the entire `AnalysisContextBar` block (currently lines 11–18, the comment plus the `<EbeamSkewvoirWorkspaceAnalysisContextBar ... @open-readiness="readinessOpen = true" />`) so `<main>` opens directly with the view-body `<div>`. The `readinessOpen` ref and the `<EbeamSkewvoirWorkspaceReadinessDrawer>` at the bottom stay unchanged.

- [ ] **Step 2: Delete the bar component**

Run:

```bash
git rm front-dev-home/app/components/ebeam/skewvoir/workspace/AnalysisContextBar.vue
```

- [ ] **Step 3: Confirm nothing else references the bar**

Run: `cd front-dev-home && grep -rn 'AnalysisContextBar' app`
Expected: no output (zero matches).

- [ ] **Step 4: Type-check and lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: PASS — no unresolved-component or unused-ref errors.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/Workspace.vue
git commit -m "refactor(skewvoir): remove AnalysisContextBar, view body reclaims height"
```

---

### Task 5: Verify in the running app

**Files:** none (verification only).

- [ ] **Step 1: Run the full test + static gates**

Run: `cd front-dev-home && npm run test && npm run typecheck && npm run lint`
Expected: all PASS.

- [ ] **Step 2: Launch and drive the app**

Use the `verify` skill (Flask mock on :5050 + Nuxt on :3000). Open a CD-SEM skewvoir analysis with a comparison set (`?msrs=` with ≥2 MSRs). Confirm, screenshotting via the Tailscale IP `http://100.103.116.55:3000`:

- The top horizontal context strip is gone; the view body fills the height.
- The left rail CURRENT SELECTION shows the scope badge (세트 비교 / 단일 측정), Focus, Param, Lot, and 호환/제외 counts.
- Clicking an MSR row switches focus across views; the crosshair/highlight moves.
- Unchecking a member's checkbox removes it from the set (URL `?msrs=` shrinks); the focused member's checkbox is disabled and cannot be removed.
- 선택 해제 collapses the set to just the focused MSR.
- The ⤢ enlarge button opens `SelectionDetailModal` with full fields, all counts, 기준, and the searchable 세트 편집 menu; adding an MSR there grows the set.
- 분석 준비 상태 opens the existing `ReadinessDrawer`.
- A single-measurement analysis (no `?msrs=`) shows the compact card with no checkboxes / 선택 해제.

- [ ] **Step 3: Final commit if any polish was needed**

Only if Step 2 surfaced fixes:

```bash
git add -A
git commit -m "fix(skewvoir): selection rail consolidation polish from verification"
```

---

## Self-Review

**Spec coverage:**
- Remove `AnalysisContextBar`, view body reclaims height → Task 4. ✓
- Rail scope badge + compact meta + counts → Task 3. ✓
- Checkable MSR list, row=focus, checkbox=remove with focus guard → Task 3 (view) + Task 1 (`removeFromSet` guard). ✓
- 선택 해제 = clear to focus; 모두 선택 dropped → Task 3 (`deselectToFocus`) + Task 1 (`clearToFocus`). ✓
- Enlarge ⤢ → center modal with full fields, all counts, 기준, searchable set editor → Task 2 + Task 3 (button/mount). ✓
- 분석 준비 상태 opens existing ReadinessDrawer via emit → Task 3 (emit) + Task 4 (wiring). ✓
- ParamNav stays in Dashboard; rail shows read-only Param → Task 3 (read-only `activeParam` label); no ParamNav change. ✓
- No backend/composable changes → honored across all tasks. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases" — every step has concrete code or an exact command. ✓

**Type consistency:** `removeFromSet(list, msr, focusMsr)` and `clearToFocus(focusMsr)` signatures match between Task 1 (definition), the test, and Task 3 (call sites). `defineModel<boolean>('open')` in Task 2 matches `v-model:open` in Task 3. `counts.{compatible,loaded,selected,excluded}` matches the shape read from `manifest.value.counts` (verified against `AnalysisContextBar.vue`). `emit('openReadiness')` in Task 3 matches `@open-readiness` in Task 4. ✓
