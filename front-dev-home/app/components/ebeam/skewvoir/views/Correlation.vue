<template>
  <div class="space-y-3">
    <div
      v-if="analysis.focusPending.value"
      class="dashboard-surface flex h-72 items-center justify-center gap-2 rounded-(--sk-r-card) text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>

    <template v-else-if="params.length">
      <!-- Param X / Y selectors -->
      <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-(--sk-r-card) px-3 py-2.5">
        <span class="font-mono text-[10px] tracking-wide text-zinc-400">X</span>
        <USelect
          v-model="paramX"
          :items="params"
          size="xs"
          class="min-w-[9rem]"
        />
        <UIcon
          name="i-lucide-x"
          class="h-3 w-3 text-zinc-300"
        />
        <span class="font-mono text-[10px] tracking-wide text-zinc-400">Y</span>
        <USelect
          v-model="paramY"
          :items="params"
          size="xs"
          class="min-w-[9rem]"
        />
      </div>

      <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <EbeamSkewvoirPanelFrame
          title="Parameter Correlation"
          :meta="`${paramX} × ${paramY}`"
          icon="i-lucide-scatter-chart"
        >
          <EbeamSkewvoirCorrelationScatter
            :rows="analysis.siteRows.value"
            :param-x="paramX"
            :param-y="paramY"
            :unit-x="unitOf(paramX)"
            :unit-y="unitOf(paramY)"
          />
        </EbeamSkewvoirPanelFrame>

        <EbeamSkewvoirPanelFrame
          v-model="distMode"
          title="Distribution"
          :meta="paramY"
          :toggles="['Hist', 'Box', 'Violin']"
          icon="i-lucide-bar-chart-3"
        >
          <EbeamSkewvoirDistributionChart
            :rows="analysis.siteRows.value"
            :parameter="paramY"
            :unit="unitOf(paramY)"
            :mode="distMode"
          />
        </EbeamSkewvoirPanelFrame>
      </div>
    </template>

    <div
      v-else
      class="dashboard-surface flex h-72 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      파라미터 데이터가 없습니다.
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const params = computed(() => props.analysis.availableParams.value)

const paramX = ref('')
const paramY = ref('')
const distMode = ref('Hist')

const unitOf = (param: string) =>
  props.analysis.paramSummaries.value.find(p => p.parameter === param)?.unit ?? ''

// Default X/Y to the first two params, and keep them valid as the focus changes.
watch(params, (list) => {
  if (!list.includes(paramX.value)) paramX.value = list[0] ?? ''
  if (!list.includes(paramY.value)) paramY.value = list[1] ?? list[0] ?? ''
}, { immediate: true })
</script>
