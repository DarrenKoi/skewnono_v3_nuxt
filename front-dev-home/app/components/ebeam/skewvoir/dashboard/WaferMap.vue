<template>
  <EbeamSkewvoirPanelFrame
    v-model="mode"
    title="Wafer Map"
    :meta="meta"
    :toggles="['Sites', 'Field']"
    icon="i-lucide-grid-3x3"
    body-class="flex flex-col gap-2"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex flex-1 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
    <template v-else-if="hasData">
      <div class="grid min-h-0 flex-1 place-items-center">
        <div class="aspect-square w-full max-w-[17rem]">
          <EbeamSkewvoirWaferMap
            :rows="analysis.siteRows.value"
            :parameter="analysis.activeParam.value"
            :unit="analysis.activeUnit.value"
            :geo="analysis.waferGeo.value"
            :mode="mode"
            :focused-sequence="analysis.focusedSequence.value"
            :outlier-seqs="outlierSeqs"
            @focus="analysis.setFocusedSequence"
            @rangechange="colorRange = $event"
          />
        </div>
      </div>
      <!-- Legend, separate from the chart so it can't overlap the wafer: a color
           scale (low→high) plus the ✕/◎ symbols. -->
      <div class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 font-mono text-[11px] text-(--sk-ink-muted)">
        <span class="inline-flex items-center gap-1.5">
          <span class="tabular-nums text-(--sk-ink)">{{ rangeLabel.min }}</span>
          <span
            class="h-2.5 w-16 rounded-(--sk-r-sidebar)"
            :style="gradientStyle"
          />
          <span class="tabular-nums text-(--sk-ink)">{{ rangeLabel.max }}</span>
          <span>{{ analysis.activeUnit.value }}</span>
        </span>
        <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">✕</span>측정 실패</span>
        <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">◎</span>이상</span>
      </div>
    </template>
    <div
      v-else
      class="flex flex-1 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      {{ analysis.activeParam.value }} 데이터가 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'
import { SK_CHART } from '~/utils/chartPalette'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const mode = ref<'Sites' | 'Field'>('Sites')

// Color-scale range published by the chart — drives the DOM legend below it.
const colorRange = ref<{ min: number, max: number } | null>(null)
const gradientStyle = computed(() => ({ background: `linear-gradient(to right, ${SK_CHART.scale.join(', ')})` }))
const rangeLabel = computed(() =>
  colorRange.value
    ? { min: colorRange.value.min.toFixed(1), max: colorRange.value.max.toFixed(1) }
    : { min: '—', max: '—' }
)

const siteCount = computed(() =>
  props.analysis.siteRows.value.filter(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r)).length
)
const hasData = computed(() => siteCount.value > 0)

// The single overview source — the ◎ rings mark exactly the sequences the site
// table flags (never re-derived here).
const outlierSeqs = computed(() =>
  props.analysis.activeOverview.value.tableRows.filter(r => r.kind !== 'failed').map(r => r.sequence)
)

const meta = computed(() => `${props.analysis.activeParam.value} · ${siteCount.value} sites`)
</script>
