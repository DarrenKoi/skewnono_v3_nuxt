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
      class="flex flex-1 items-center justify-center gap-2 text-sm text-(--sk-ink-muted)"
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
      height-class="h-full min-h-[8rem]"
    />
    <div
      v-else
      class="flex flex-1 items-center justify-center text-sm text-(--sk-ink-subtle)"
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

const hasData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r))
)

const meta = computed(() => {
  const s = props.analysis.activeSummary.value
  return s ? `μ ${s.mean.toFixed(2)} · 3σ ${(s.std * 3).toFixed(2)}` : props.analysis.activeParam.value
})
</script>
