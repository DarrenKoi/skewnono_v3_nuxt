<template>
  <div class="dashboard-surface flex flex-col gap-1.5 rounded-(--sk-r-card) px-4 py-2.5">
    <div class="flex items-baseline gap-2">
      <span class="sk-eyebrow">실패 원인</span>
      <span class="sk-label">{{ breakdown.sites.measured }}/{{ breakdown.sites.total }} site 측정</span>
      <span class="ml-auto shrink-0 font-mono text-[11px] tabular-nums text-(--sk-ink-muted)">
        <span :class="breakdown.failedCount > 0 ? 'font-bold text-(--sk-bad)' : 'text-(--sk-ink)'">실패 {{ breakdown.failedCount }}</span>
        <span v-if="breakdown.unknownCount > 0"> · 미상 {{ breakdown.unknownCount }}</span>
      </span>
    </div>

    <!-- Four causes side by side. They are never summed: an unjudged Align and
         a failed one are different answers, and one health score would erase
         which of the four actually went wrong. -->
    <div class="flex flex-wrap gap-x-4 gap-y-1.5">
      <div
        v-for="r in breakdown.reasons"
        :key="r.key"
        class="flex min-w-0 flex-col gap-0.5"
        :title="r.detail"
      >
        <span class="sk-label">{{ r.label }}</span>
        <span
          class="font-mono text-sm font-bold tabular-nums"
          :class="r.status === 'fail' ? 'text-(--sk-bad)' : r.status === 'unknown' ? 'text-(--sk-ink-subtle)' : 'text-(--sk-ink)'"
        >{{ statusText(r) }}</span>
      </div>
    </div>

    <!-- Spatial question, kept separate from the counts: a cluster and a spread
         of the same count mean different things. -->
    <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1 border-t border-(--sk-border-soft) pt-1.5">
      <span class="sk-label">공간 분포</span>
      <template v-if="clustering.status === 'ok'">
        <span
          class="font-mono text-xs font-bold"
          :class="clustering.verdict === 'clustered' ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
        >{{ clustering.verdict === 'clustered' ? '군집' : '분산' }}</span>
        <span class="font-mono text-[11px] tabular-nums text-(--sk-ink-muted)">
          {{ clustering.sectors.map(s => `${s.label} ${s.count}`).join(' · ') }}
          <span v-if="clustering.unplaced > 0"> · 좌표 없음 {{ clustering.unplaced }}</span>
        </span>
      </template>
      <span
        v-else
        class="text-xs font-semibold text-(--sk-ink-subtle)"
      >평가 불가 — {{ clustering.reason }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { analyzeSpatial } from '~/utils/skewvoirAnalysis/spatial'
import { failureBreakdown, failureClustering, type FailureReason } from '~/utils/skewvoirAnalysis/cdu'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// The three MSR-level causes come from the focus measurement's meas-hist row,
// which the analysis composable already holds — no extra request.
const breakdown = computed(() =>
  failureBreakdown(
    props.analysis.siteRows.value,
    props.analysis.activeParam.value,
    props.analysis.focusRow.value
  )
)

// Reuses the spatial module's own failure layer: it places every unmeasured
// site and labels its sector, so this card counts rather than re-derives.
const clustering = computed(() =>
  failureClustering(
    analyzeSpatial(
      props.analysis.siteRows.value,
      props.analysis.activeParam.value,
      props.analysis.waferGeo.value,
      { unit: props.analysis.activeUnit.value }
    ).failures
  )
)

// '평가 불가' is printed, not hidden: a cause nobody could judge must not read
// as a cause that passed.
const statusText = (r: FailureReason): string => {
  if (r.status === 'unknown') return '평가 불가'
  if (r.count == null) return r.status === 'fail' ? '실패' : '정상'
  // fail_ratio arrives as a percent already — nothing is scaled here.
  return r.percent == null
    ? `${r.count}`
    : `${r.count}/${r.total} · ${formatFixed(r.percent, 2)}%`
}
</script>
