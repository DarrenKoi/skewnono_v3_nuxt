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
import { analyzeRadialProfile, type RadialSample } from '~/utils/radialAnalysis'
import { radialSamples } from '~/utils/skewvoirAnalysis/spatial'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// URL-carried (`rfit`): 위치 비교's residual layer fits with the same degree.
const DEGREES = { '1°': 'linear', '2°': 'quadratic', '3°': 'cubic' } as const
const model = props.analysis.radialModel
const degreeToggle = computed({
  get: () => model.value === 'cubic' ? '3°' : model.value === 'quadratic' ? '2°' : '1°',
  set: (v: string) => props.analysis.setRadialModel(DEGREES[v as keyof typeof DEGREES] ?? 'linear')
})
const open = ref(false)

// Built by the shared radialSamples so the review receipt's 반경 fit sheet fits
// exactly these points.
const samples = computed<RadialSample[]>(() =>
  radialSamples(props.analysis.siteRows.value, props.analysis.activeParam.value, props.analysis.waferGeo.value))

const profile = computed(() => analyzeRadialProfile(samples.value, { model: model.value }))

const meta = computed(() => {
  const label = model.value === 'linear' ? 'linear' : (model.value === 'quadratic' ? 'quadratic' : 'cubic')
  const rmse = profile.value.metrics.rmse
  return `${label} · n=${profile.value.metrics.n}${rmse != null ? ` · RMSE ${rmse.toFixed(3)}` : ''}`
})
</script>
