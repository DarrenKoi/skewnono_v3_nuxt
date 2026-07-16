<template>
  <!-- Branch-by-abstraction on analysis scope:
       • single → the single-MSR measurement-order + dynamic-FDC workbench (Task 7)
       • set    → the existing multi-measurement trend + sequence-trend panels
                  (kept until the multi-MSR run chart of Task 8). -->
  <EbeamSkewvoirTimeseriesSequenceWorkbench
    v-if="analysis.scope.value === 'single'"
    :analysis="analysis"
  />

  <div
    v-else
    class="space-y-3"
  >
    <!-- Multi-measurement trend (mean ± min/max band) -->
    <EbeamSkewvoirPanelFrame
      title="Multi-Measurement Trend"
      :meta="`mean ± min/max · ${analysis.activeParam.value}`"
      icon="i-lucide-trending-up"
    >
      <div
        v-if="analysis.setPending.value"
        class="flex h-72 items-center justify-center gap-2 sk-body"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        추이 데이터를 불러오는 중…
      </div>
      <template v-else-if="analysis.trendPoints.value.length">
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <USelect
            v-model="anomalyCfg.method"
            size="xs"
            :items="methodItems"
            class="min-w-[11rem]"
          />
          <template v-if="anomalyCfg.method === 'range'">
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              주의 ±<UInput
                v-model.number="anomalyCfg.range.watchPct"
                type="number"
                min="0"
                size="xs"
                class="w-14"
              />%
            </label>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              이상 ±<UInput
                v-model.number="anomalyCfg.range.abnormalPct"
                type="number"
                min="0"
                size="xs"
                class="w-14"
              />%
            </label>
          </template>
          <template v-else>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              주의 ±<UInput
                v-model.number="anomalyCfg.stddev.watchK"
                type="number"
                min="0"
                size="xs"
                class="w-14"
              />σ
            </label>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              이상 ±<UInput
                v-model.number="anomalyCfg.stddev.abnormalK"
                type="number"
                min="0"
                size="xs"
                class="w-14"
              />σ
            </label>
          </template>
          <span class="sk-meta tabular-nums">
            주의 {{ analysis.trendSummary.value.watch }} · 이상 {{ analysis.trendSummary.value.abnormal }} / {{ analysis.trendPoints.value.length }} MSR
          </span>
          <SkAnomalyLegend
            class="ml-auto"
            :method="anomalyCfg.method"
            :range="anomalyCfg.range"
            :stddev="anomalyCfg.stddev"
          />
        </div>
        <EbeamSkewvoirTimeSeriesChart
          :points="analysis.trendPoints.value"
          :parameter="analysis.activeParam.value"
          :unit="analysis.activeUnit.value"
        />
      </template>
      <div
        v-else
        class="flex h-72 items-center justify-center sk-body"
      >
        비교할 측정을 추가하세요.
      </div>
    </EbeamSkewvoirPanelFrame>

    <!-- Sequence trend of the focus measurement -->
    <EbeamSkewvoirPanelFrame
      title="Sequence Trend"
      :meta="`focus · ${analysis.focusRow.value?.lot_id ?? '—'}`"
      icon="i-lucide-activity"
    >
      <template #actions>
        <SkAnomalyBadge :verdict="analysis.focusVerdict.value" />
      </template>
      <EbeamSkewvoirSequenceTrend
        v-if="hasFocusData"
        :rows="analysis.siteRows.value"
        :parameter="analysis.activeParam.value"
        :unit="analysis.activeUnit.value"
      />
      <div
        v-else
        class="flex h-56 items-center justify-center sk-body"
      >
        focus 측정의 sequence 데이터가 없습니다.
      </div>
    </EbeamSkewvoirPanelFrame>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'

const props = defineProps<{
  ws: SkewvoirWorkspace
  analysis: SkewvoirAnalysis
}>()

// Destructure the mutable shared state ref into a local so v-model bindings do
// not trigger vue/no-mutating-props (anomalyCfg is useState-backed reactive state,
// not a plain prop value — accessing it through a local ref is safe).
const anomalyCfg = props.analysis.anomalyCfg

const methodItems = [
  { label: '범위(%)', value: 'range' },
  { label: '표준편차(σ) · 진단', value: 'stddev' }
]

const hasFocusData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r))
)
</script>
