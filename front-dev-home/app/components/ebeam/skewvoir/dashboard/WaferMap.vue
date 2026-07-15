<template>
  <EbeamSkewvoirPanelFrame
    title="Wafer Map"
    :meta="meta"
    icon="i-lucide-grid-3x3"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex h-72 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
    <EbeamSkewvoirWaferMap
      v-else-if="hasData"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :focused-sequence="analysis.focusedSequence.value"
      @focus="analysis.setFocusedSequence"
    />
    <div
      v-else
      class="flex h-72 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      {{ analysis.activeParam.value }} 데이터가 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const siteCount = computed(() =>
  props.analysis.siteRows.value.filter(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r)).length
)
const hasData = computed(() => siteCount.value > 0)
const meta = computed(() => `${props.analysis.activeParam.value} · ${siteCount.value} sites`)
</script>
