<template>
  <div class="space-y-3">
    <!-- Curate the comparison set — writes straight to the URL ?msrs= -->
    <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-(--sk-r-card) px-3 py-2.5">
      <span class="font-mono text-[10px] tracking-wide text-zinc-400">비교 세트</span>
      <USelectMenu
        :model-value="ws.msrList.value"
        multiple
        value-key="value"
        :items="candidateItems"
        :search-input="{ placeholder: 'lot / eq 로 검색…' }"
        placeholder="측정 추가/제거"
        class="min-w-[20rem] flex-1"
        size="sm"
        @update:model-value="ws.setMsrs"
      />
      <span class="font-mono text-[11px] text-(--sk-ink-muted)">
        {{ analysis.setRows.value.length }} measurements · {{ analysis.activeParam.value }}
      </span>
    </div>

    <!-- Multi-measurement trend (mean ± min/max band) -->
    <EbeamSkewvoirPanelFrame
      title="Multi-Measurement Trend"
      :meta="`mean ± min/max · ${analysis.activeParam.value}`"
      icon="i-lucide-trending-up"
    >
      <div
        v-if="analysis.trendPending.value"
        class="flex h-72 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        추이 데이터를 불러오는 중…
      </div>
      <EbeamSkewvoirTimeSeriesChart
        v-else-if="analysis.trendPoints.value.length"
        :points="analysis.trendPoints.value"
        :parameter="analysis.activeParam.value"
        :unit="analysis.activeUnit.value"
      />
      <div
        v-else
        class="flex h-72 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
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
      <EbeamSkewvoirSequenceTrend
        v-if="hasFocusData"
        :rows="analysis.siteRows.value"
        :parameter="analysis.activeParam.value"
        :unit="analysis.activeUnit.value"
      />
      <div
        v-else
        class="flex h-56 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
      >
        focus 측정의 sequence 데이터가 없습니다.
      </div>
    </EbeamSkewvoirPanelFrame>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { formatRecipeTimestamp } from '~/utils/recipeView'

const props = defineProps<{
  ws: SkewvoirWorkspace
  analysis: SkewvoirAnalysis
}>()

const candidateItems = computed(() =>
  props.analysis.candidateRows.value.map(r => ({
    label: `${formatRecipeTimestamp(r.timestamp)} · ${r.eqp_id} · ${r.lot_id}`,
    value: r.msr
  }))
)

const hasFocusData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value)
)
</script>
