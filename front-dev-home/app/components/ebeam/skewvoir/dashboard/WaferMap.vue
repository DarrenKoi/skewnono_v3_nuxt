<template>
  <EbeamSkewvoirPanelFrame
    v-model="mode"
    title="Wafer Map"
    :meta="meta"
    :toggles="['Field', 'Die']"
    icon="i-lucide-grid-3x3"
    body-class="flex flex-col gap-2"
  >
    <template #actions>
      <UButton
        icon="i-lucide-maximize-2"
        color="neutral"
        variant="ghost"
        size="xs"
        aria-label="확대"
        @click="detailOpen = true"
      />
      <EbeamSkewvoirWaferMapOptions
        v-model:options="options"
        :auto-range="autoRange"
      />
    </template>

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
    <template v-else-if="hasData">
      <div class="grid min-h-0 flex-1 place-items-center">
        <div class="aspect-square w-full max-w-[22rem]">
          <EbeamSkewvoirWaferMap
            :rows="analysis.siteRows.value"
            :parameter="analysis.activeParam.value"
            :unit="analysis.activeUnit.value"
            :geo="analysis.waferGeo.value"
            :mode="mode"
            :options="options"
            :color-min="effectiveRange.colorMin"
            :color-max="effectiveRange.colorMax"
            :focused-sequence="analysis.focusedSequence.value"
            :outlier-seqs="outlierSeqs"
            :selected-seqs="analysis.selectedSeqsForActiveParam.value"
            :seq-colors="analysis.seqColorsForActiveParam.value"
            @focus="analysis.setFocusedSequence"
            @rangechange="autoRange = $event"
          />
        </div>
      </div>
      <!-- Legend, separate from the chart so it can't overlap the wafer: a ticked
           color bar plus the ✕/◎ symbols. -->
      <div class="flex flex-col items-center gap-1">
        <EbeamSkewvoirColorScaleBar
          :min="effectiveRange.colorMin"
          :max="effectiveRange.colorMax"
          :unit="analysis.activeUnit.value"
        />
        <div class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 font-mono text-[11px] text-(--sk-ink-muted)">
          <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">✕</span>측정 실패</span>
          <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">◎</span>이상</span>
        </div>
      </div>
    </template>
    <div
      v-else
      class="flex flex-1 items-center justify-center sk-body"
    >
      {{ analysis.activeParamLabel.value }} 데이터가 없습니다.
    </div>

    <EbeamSkewvoirWaferDetailModal
      v-model:open="detailOpen"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :geo="analysis.waferGeo.value"
      :focused-sequence="analysis.focusedSequence.value"
      :outlier-seqs="outlierSeqs"
      :selected-seqs="analysis.selectedSeqsForActiveParam.value"
      :seq-colors="analysis.seqColorsForActiveParam.value"
      @focus="analysis.setFocusedSequence"
    />
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'
import { defaultWaferMapOptions, resolveColorRange } from '~/utils/waferMapOptions'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const mode = ref<'Field' | 'Die'>('Field')
const detailOpen = ref(false)
const options = ref(defaultWaferMapOptions())

// The leaf publishes its auto (data) range via @rangechange; the manual override
// from the popover is applied here and fed back to the leaf's visualMap + bar.
const autoRange = ref<{ min: number, max: number }>({ min: 0, max: 1 })
const effectiveRange = computed(() => {
  const r = resolveColorRange(options.value.colorMode, options.value.colorMin, options.value.colorMax, autoRange.value)
  return { colorMin: r.min, colorMax: r.max }
})

const siteCount = computed(() =>
  props.analysis.siteRows.value.filter(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r)).length
)
const hasData = computed(() => siteCount.value > 0)

// The single overview source — the ◎ rings mark exactly the sequences the site
// table flags (never re-derived here).
const outlierSeqs = computed(() =>
  props.analysis.activeOverview.value.tableRows.filter(r => r.kind !== 'failed').map(r => r.sequence)
)

// "fields" = measured points (a die can hold several); consistent with Field mode.
const meta = computed(() => `${props.analysis.activeParamLabel.value} · ${siteCount.value} fields`)
</script>
