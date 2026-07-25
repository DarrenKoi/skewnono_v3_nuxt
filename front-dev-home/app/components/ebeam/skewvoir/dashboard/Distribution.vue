<template>
  <EbeamSkewvoirPanelFrame
    v-model="mode"
    title="Distribution"
    :meta="meta"
    :toggles="['Hist', 'Box', 'Violin']"
    icon="i-lucide-bar-chart-3"
    body-class="flex flex-col"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex flex-1 items-center justify-center gap-2 sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
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
      {{ analysis.activeParam.value }} 데이터가 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const mode = ref('Hist')
const sk = useChartPalette()

const hasData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r))
)

// Selected points of the active parameter as (value, identity color) pairs;
// overflow picks use the muted tone. The chart marks them per its active shape.
const highlights = computed<{ value: number, color: string }[]>(() => {
  const param = props.analysis.activeParam.value
  const picked = new Set(props.analysis.selectedSeqsForActiveParam.value)
  const out: { value: number, color: string }[] = []
  for (const r of props.analysis.siteRows.value) {
    if (r.parameter !== param || !picked.has(r.sequence)) continue
    if (!isMeasuredRow(r) || r.cd_value == null) continue
    out.push({ value: r.cd_value, color: props.analysis.siteColor(param, r.sequence) ?? sk.value.muted })
  }
  return out
})

const meta = computed(() => {
  const s = props.analysis.activeSummary.value
  return s ? `μ ${s.mean.toFixed(2)} · 3σ ${(s.std * 3).toFixed(2)}` : props.analysis.activeParam.value
})
</script>
