<template>
  <EbeamSkewvoirPanelFrame
    v-model="degreeToggle"
    title="Radius Plot"
    :meta="meta"
    :toggles="['1°', '2°', '3°']"
    icon="i-lucide-line-chart"
    body-class="flex flex-col"
  >
    <template #actions>
      <button
        type="button"
        class="rounded-(--sk-r-sidebar) border border-(--sk-border) bg-(--sk-surface)/90 p-1 text-(--sk-ink-muted) transition-colors duration-200 hover:text-(--sk-ink) disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Radius Analysis 전체 화면"
        title="Radius Analysis 전체 화면"
        :disabled="!samples.length"
        @click="open = true"
      >
        <UIcon
          name="i-lucide-maximize-2"
          class="h-3.5 w-3.5"
        />
      </button>
    </template>

    <AppLoadingState
      v-if="analysis.focusPending.value"
      variant="inline"
      class="flex-1"
      title="불러오는 중입니다."
    />
    <EbeamSkewvoirRadiusChart
      v-else-if="samples.length"
      :profile="profile"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :focused-sequence="analysis.focusedSequence.value"
      :selected-seqs="analysis.selectedSeqsForActiveParam.value"
      :seq-colors="analysis.seqColorsForActiveParam.value"
      band="iqr"
      @focus="analysis.setFocusedSequence"
    />
    <div
      v-else
      class="flex flex-1 items-center justify-center sk-body"
    >
      {{ analysis.activeParamLabel.value }} 데이터가 없습니다.
    </div>

    <EbeamSkewvoirDashboardRadiusAnalysisDialog
      v-model="open"
      :samples="samples"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :focused-sequence="analysis.focusedSequence.value"
      :initial-model="model"
      @focus="analysis.setFocusedSequence"
    />
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'
import { analyzeRadialProfile, type RadialModel, type RadialSample } from '~/utils/radialAnalysis'
import { stagePosMm } from '~/utils/waferGeometry'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const degreeToggle = ref('1°')
const open = ref(false)
const model = computed<RadialModel>(() => {
  if (degreeToggle.value === '2°') return 'quadratic'
  if (degreeToggle.value === '3°') return 'cubic'
  return 'linear'
})

const sectorOf = (x: number, y: number): string => {
  const angle = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360
  if (angle < 45 || angle >= 315) return 'E'
  if (angle < 135) return 'N'
  if (angle < 225) return 'W'
  return 'S'
}

const samples = computed<RadialSample[]>(() => {
  const parameter = props.analysis.activeParam.value
  const geo = props.analysis.waferGeo.value
  return measuredRows(props.analysis.siteRows.value).flatMap((row) => {
    if (row.parameter !== parameter) return []
    const position = stagePosMm(row.stage_coordinate, geo)
    if (!position) return []
    const [x, y] = position
    return [{
      sequence: row.sequence,
      radius: Math.hypot(x, y),
      value: row.cd_value,
      x,
      y,
      sector: sectorOf(x, y)
    }]
  })
})

const profile = computed(() => analyzeRadialProfile(samples.value, { model: model.value }))

const meta = computed(() => {
  const label = model.value === 'linear' ? 'linear' : (model.value === 'quadratic' ? 'quadratic' : 'cubic')
  const rmse = profile.value.metrics.rmse
  return `${label} · n=${profile.value.metrics.n}${rmse != null ? ` · RMSE ${rmse.toFixed(3)}` : ''}`
})
</script>
