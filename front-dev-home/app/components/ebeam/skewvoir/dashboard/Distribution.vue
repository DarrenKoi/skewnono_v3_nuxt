<template>
  <EbeamSkewvoirPanelFrame
    title="Distribution"
    :meta="meta"
    :toggles="['Hist', 'Box', 'Violin']"
    icon="i-lucide-bar-chart-3"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex h-56 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
    <EbeamSkewvoirCdDistribution
      v-else-if="hasData"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
    />
    <div
      v-else
      class="flex h-56 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      {{ analysis.activeParam.value }} 데이터가 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const hasData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value)
)

const meta = computed(() => {
  const s = props.analysis.activeSummary.value
  return s ? `μ ${s.mean.toFixed(3)} · 3σ ${(s.std * 3).toFixed(3)}` : `MP · ${props.analysis.activeParam.value}`
})
</script>
