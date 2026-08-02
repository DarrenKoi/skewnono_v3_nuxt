<template>
  <EbeamSkewvoirPanelFrame
    v-model="mode"
    title="Distribution"
    :meta="meta"
    :toggles="['Hist', 'Box', 'Violin']"
    icon="i-lucide-bar-chart-3"
    body-class="flex flex-col"
  >
    <AppLoadingState
      v-if="analysis.focusPending.value"
      variant="inline"
      class="flex-1"
      title="불러오는 중입니다."
    />
    <EbeamSkewvoirDistributionChart
      v-else-if="hasData"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :mode="mode"
      :highlights="highlights"
      height-class="h-full min-h-[8rem]"
    />
    <div
      v-else
      class="flex flex-1 items-center justify-center sk-body"
    >
      {{ analysis.activeParamLabel.value }} 데이터가 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { DistributionHighlight } from '~/components/ebeam/skewvoir/DistributionChart.vue'
import { isMeasuredRow } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const mode = ref('Hist')

const hasData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r))
)

// Selected points of the active parameter as (value, identity color) pairs — the
// value from the row, the color from the composable's finished seq → color map.
// The chart marks them per its active shape (Box dots / Violin rug / Hist bin).
const highlights = computed<DistributionHighlight[]>(() => {
  const param = props.analysis.activeParam.value
  const colors = props.analysis.seqColorsForActiveParam.value
  const out: DistributionHighlight[] = []
  for (const r of props.analysis.siteRows.value) {
    const color = r.parameter === param ? colors[r.sequence] : undefined
    if (!color || !isMeasuredRow(r) || r.cd_value == null) continue
    out.push({ value: r.cd_value, color })
  }
  return out
})

const meta = computed(() => {
  const s = props.analysis.activeSummary.value
  return s ? `μ ${s.mean.toFixed(2)} · 3σ ${(s.std * 3).toFixed(2)}` : props.analysis.activeParamLabel.value
})
</script>
