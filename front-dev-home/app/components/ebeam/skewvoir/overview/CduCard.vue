<template>
  <div class="dashboard-surface flex flex-col gap-1.5 rounded-(--sk-r-card) px-4 py-2.5">
    <div class="flex items-baseline gap-2">
      <span class="sk-eyebrow">CDU 지표</span>
      <span class="truncate sk-label">{{ paramLabel }}<span v-if="unit"> · {{ unit }}</span></span>
      <!-- Valid N rides in the header, not in a corner: every spread below is
           only as trustworthy as the sample it came from.

           The words are 11px chrome; the counts are not. DESIGN.md holds a hard
           floor — "a data value never renders below 12px" — and N is the value
           the whole card leans on, so it takes .sk-value-num rather than
           inheriting the label's size. -->
      <span class="ml-auto flex shrink-0 items-baseline gap-1">
        <span class="sk-label">유효 N</span>
        <span class="sk-value-num font-bold">{{ metrics.n }}</span>
        <template v-if="metrics.missing > 0">
          <span class="sk-label">· 결측</span>
          <span class="sk-value-num text-(--sk-bad)">{{ metrics.missing }}</span>
        </template>
      </span>
    </div>

    <!-- Three lines, deliberately separate: where the wafer sits, how wide it
         spreads, and what shape it has. -->
    <div
      v-for="line in lines"
      :key="line.key"
      class="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-t border-(--sk-border-soft) pt-1.5 first:border-t-0 first:pt-0"
    >
      <span class="w-16 shrink-0 sk-label">{{ line.label }}</span>
      <template v-if="line.cells.length">
        <div
          v-for="cell in line.cells"
          :key="cell.label"
          class="flex items-baseline gap-1"
        >
          <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ cell.label }}</span>
          <span class="font-mono text-sm font-bold tabular-nums text-(--sk-ink)">{{ cell.value }}</span>
        </div>
      </template>
      <span
        v-else
        class="text-xs font-semibold text-(--sk-ink-subtle)"
      >평가 불가 — {{ line.reason }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { cduMetrics } from '~/utils/skewvoirAnalysis/cdu'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const paramLabel = computed(() => props.analysis.activeParamLabel.value)
const unit = computed(() => props.analysis.activeUnit.value)

// Level + spread are computed from the FULL row set (the msr-file response is
// never truncated), not from MsrParamSummary — that summary carries no median
// and no MAD, so the robust half of this card cannot come from it.
const metrics = computed(() =>
  cduMetrics(props.analysis.siteRows.value, props.analysis.activeParam.value, unit.value)
)

// Shape reuses the feature table's ALREADY-COMPUTED centre→edge delta (OLS fit
// of cd_value against site radius, slope × radius span). Recomputing it here
// would be a second formula for the same question.
const shape = computed(() => {
  const msr = props.analysis.focusMsr.value
  return props.analysis.featureRows.value.find(r => r.msr === msr)?.spatial ?? null
})

const signed = (value: number, digits: number) => `${value >= 0 ? '+' : ''}${formatFixed(value, digits)}`

interface Cell { label: string, value: string }

const lines = computed<{ key: string, label: string, cells: Cell[], reason: string }[]>(() => {
  const level = metrics.value.level
  const spread = metrics.value.spread
  return [
    {
      key: 'level',
      label: 'Wafer level',
      // No target offset: this repo has no spec/target contract to subtract
      // against, and an offset against an invented target is a fiction.
      cells: level
        ? [
            { label: 'mean', value: formatFixed(level.mean, 2) },
            { label: 'median', value: formatFixed(level.median, 2) }
          ]
        : [],
      reason: '측정된 site 가 없습니다.'
    },
    {
      key: 'spread',
      label: 'Spread',
      cells: spread
        ? [
            { label: 'σ', value: formatFixed(spread.std, 3) },
            { label: '3σ', value: formatFixed(spread.threeSigma, 3) },
            // Scaled to a sigma so the two stand on one axis: MAD far below σ
            // means a few extreme sites, not a wide wafer.
            { label: 'MAD(σ환산)', value: formatFixed(spread.madSigma, 3) },
            { label: 'range', value: formatFixed(spread.range, 3) }
          ]
        : [],
      reason: '산포를 정의하려면 측정 site 가 2개 이상 필요합니다.'
    },
    {
      key: 'shape',
      label: 'Shape',
      cells: shape.value
        ? [{ label: '중심→외곽', value: signed(shape.value.value, 3) }]
        : [],
      reason: '좌표를 확인할 수 있는 site 가 부족해 반경 추세를 적합할 수 없습니다.'
    }
  ]
})
</script>
