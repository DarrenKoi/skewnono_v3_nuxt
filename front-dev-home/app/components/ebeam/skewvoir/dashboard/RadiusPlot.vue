<template>
  <EbeamSkewvoirPanelFrame
    v-model="degToggle"
    title="Radius Plot"
    :meta="meta"
    :toggles="['1°', '3°']"
    icon="i-lucide-line-chart"
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
    <EbeamSkewvoirRadiusChart
      v-else-if="hasData"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :geo="analysis.waferGeo.value"
      :degree="degree"
      :focused-sequence="analysis.focusedSequence.value"
      @focus="analysis.setFocusedSequence"
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

const degToggle = ref('3°')
const degree = computed(() => (degToggle.value === '1°' ? 1 : 3))

const hasData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r))
)

const meta = computed(() => (degree.value === 3 ? '3rd polynomial' : '1st order fit'))
</script>
