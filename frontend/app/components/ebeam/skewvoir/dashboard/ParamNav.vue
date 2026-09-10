<template>
  <div class="flex flex-col gap-2 rounded-(--sk-r-card) border border-(--sk-border) bg-(--sk-muted-surface) px-3 py-2">
    <!-- Header — stays put whether or not the chips are showing, so the row
         height is stable and the current scope never disappears with them. -->
    <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span class="sk-eyebrow">
        Parameter
      </span>
      <span class="font-mono text-xs font-semibold text-(--sk-ink)">
        {{ paramLabel(activeParam) }}
      </span>
      <span
        v-if="selectedCount > 1"
        class="font-mono text-xs text-(--sk-ink-muted)"
      >· {{ selectedCount }}개 선택</span>
      <!-- The chips carry one signal 파라미터 요약 does not — per-parameter
           failures + outliers. Rolled up here so collapsing the row never
           hides the fact that something needs looking at. -->
      <button
        v-if="flaggedParamCount"
        type="button"
        class="inline-flex items-center rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-2 py-1 font-mono text-xs font-semibold text-(--sk-bad) transition-colors hover:bg-(--sk-bad-soft-hover) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--sk-focus-ring)"
        :aria-expanded="open"
        :aria-controls="chipsId"
        @click="open = true"
      >
        ● {{ flaggedParamCount }}개 이상·실패 파라미터 보기
      </button>

      <!-- NAVIGATE family (ink), not the terracotta the chips use: this reveals,
           it does not filter. See DESIGN.md. -->
      <button
        v-if="chips.length"
        type="button"
        class="ml-auto inline-flex items-center gap-1.5 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-surface) px-2 py-1 text-xs font-medium text-(--sk-ink-muted) transition-colors duration-200 hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)"
        :aria-expanded="open"
        :aria-controls="chipsId"
        @click="open = !open"
      >
        <UIcon
          :name="open ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          class="size-3.5 shrink-0"
        />
        파라미터 리스트 {{ open ? '감추기' : '보이기' }}
        <span class="text-xs tabular-nums text-(--sk-ink-subtle)">{{ chips.length }}</span>
      </button>
    </div>

    <!-- Body — collapsed by default. A recipe can carry hundreds of parameters,
         and 파라미터 요약 already selects any of them from its table rows. -->
    <div
      v-if="open && chips.length"
      :id="chipsId"
      class="flex flex-wrap items-center gap-2"
    >
      <button
        v-for="c in chips"
        :key="c.parameter"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) px-2.5 py-1 font-mono text-xs transition-colors duration-200"
        :class="c.parameter === activeParam
          ? 'bg-(--sk-brand) font-semibold text-(--sk-brand-fg)'
          : c.selected
            ? 'border border-(--sk-brand)/50 bg-(--sk-brand)/15 font-medium text-(--sk-brand)'
            : 'border border-(--sk-border) bg-(--sk-surface) text-(--sk-ink-muted) hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)'"
        :aria-pressed="c.selected"
        @click="onChipClick(c.parameter, $event)"
      >
        {{ paramLabel(c.parameter) }}
        <span
          class="text-xs tabular-nums"
          :class="c.parameter === activeParam
            ? 'text-(--sk-brand-fg)/80'
            : c.flagged ? 'font-semibold text-(--sk-bad)' : 'text-(--sk-ink-subtle)'"
        >{{ c.flagged ? `● ${c.flaggedCount}` : `${c.measured}/${c.total}` }}</span>
      </button>
      <span class="font-mono text-xs text-(--sk-ink-subtle)">⌘/Ctrl+클릭 다중 선택</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { paramLabel } from '~/utils/skewvoirAnalysis/paramOrder'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// Persisted, not local: Workspace unmounts the dashboard with `v-if` on every
// view switch, so a component ref would forget the choice each round trip.
const open = useSkewvoirParamNavOpen()
const chipsId = useId()

const activeParam = computed(() => props.analysis.activeParam.value)
const selectedSet = computed(() => new Set(props.analysis.selectedParams.value))
const selectedCount = computed(() => props.analysis.selectedParams.value.length)

// Plain click focuses one parameter; ⌘/Ctrl/⇧+click toggles it in and out of
// the multi-param comparison (Measurement Points shows the selection together).
const onChipClick = (parameter: string, e: MouseEvent) => {
  props.analysis.toggleParam(parameter, e.metaKey || e.ctrlKey || e.shiftKey)
}

// One chip per parameter. Coverage + outlier count come from the same overview
// source the panels use, so a chip's flag agrees with the site table.
const chips = computed(() =>
  props.analysis.paramSummaries.value.map((s) => {
    const ov = props.analysis.overviewFor(s.parameter)
    const flaggedCount = ov.coverage.failed + ov.outlierCount
    return {
      parameter: s.parameter,
      total: ov.coverage.total,
      measured: ov.coverage.measured,
      selected: selectedSet.value.has(s.parameter),
      flagged: flaggedCount > 0,
      flaggedCount
    }
  })
)

const flaggedParamCount = computed(() => chips.value.filter(c => c.flagged).length)
</script>
