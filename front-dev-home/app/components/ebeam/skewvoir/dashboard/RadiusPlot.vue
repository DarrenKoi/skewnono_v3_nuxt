<template>
  <EbeamSkewvoirPanelFrame
    v-model="degToggle"
    title="Radius Plot"
    :meta="meta"
    :toggles="['1°', '3°']"
    icon="i-lucide-line-chart"
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
    <EbeamSkewvoirRadiusChart
      v-else-if="hasData"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :degree="degree"
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

const degToggle = ref('3°')
const degree = computed(() => (degToggle.value === '1°' ? 1 : 3))

const hasData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value)
)

const meta = computed(() => (degree.value === 3 ? '3rd polynomial' : '1st order fit'))
</script>
