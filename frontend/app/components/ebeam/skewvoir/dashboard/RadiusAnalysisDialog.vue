<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="radius-analysis-title"
      @click="close"
    >
      <section
        class="dashboard-surface flex h-[min(92vh,58rem)] w-full max-w-[96rem] flex-col overflow-hidden rounded-(--sk-r-card) shadow-2xl"
        @click.stop
      >
        <header class="flex flex-wrap items-center gap-3 border-b border-(--sk-border-soft) px-4 py-3">
          <div class="min-w-0 flex-1">
            <h2
              id="radius-analysis-title"
              class="sk-title"
            >
              Radius Analysis · {{ parameter }}
            </h2>
            <p class="sk-meta">
              observed radius {{ format(profile.metrics.radiusMin, 1) }}–{{ format(profile.metrics.radiusMax, 1) }} mm · n={{ profile.metrics.n }} · {{ profile.metrics.distinctRadii }} distinct radii
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <USelect
              v-model="model"
              size="sm"
              :items="modelItems"
              class="w-36"
              aria-label="회귀 모델"
            />
            <USelect
              v-model="band"
              size="sm"
              :items="bandItems"
              class="w-40"
              aria-label="산포 밴드"
            />
            <UButton
              color="neutral"
              :variant="colorBySector ? 'solid' : 'subtle'"
              size="sm"
              icon="i-lucide-scan"
              label="Sector"
              @click="colorBySector = !colorBySector"
            />
            <button
              type="button"
              class="rounded-(--sk-r-nav) p-1.5 text-(--sk-ink-muted) transition-colors duration-200 hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)"
              aria-label="닫기"
              @click="close"
            >
              <UIcon
                name="i-lucide-x"
                class="h-5 w-5"
              />
            </button>
          </div>
        </header>

        <div class="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-auto p-3 xl:grid-cols-[minmax(0,1fr)_20rem] xl:overflow-hidden">
          <div class="flex min-h-[34rem] min-w-0 flex-col rounded-(--sk-r-chip) border border-(--sk-border) p-2 xl:min-h-0">
            <div
              v-if="profile.warning"
              class="mb-2 rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-3 py-2 text-(--sk-warn) sk-meta"
            >
              {{ profile.warning }}. Raw points and radial bins remain available.
            </div>
            <EbeamSkewvoirRadiusChart
              class="min-h-0 flex-1"
              :profile="profile"
              :parameter="parameter"
              :unit="unit"
              :focused-sequence="focusedSequence"
              :band="band"
              :color-by-sector="colorBySector"
              show-residuals
              height-class="h-full min-h-[32rem]"
              @focus="emit('focus', $event)"
            />
          </div>

          <aside class="min-h-0 space-y-3 overflow-auto pr-1">
            <section class="rounded-(--sk-r-chip) border border-(--sk-border) p-3">
              <h3 class="mb-2 sk-title">
                Fit quality
              </h3>
              <dl class="grid grid-cols-2 gap-x-3 gap-y-2">
                <div
                  v-for="metric in metricItems"
                  :key="metric.label"
                >
                  <dt class="sk-meta">
                    {{ metric.label }}
                  </dt>
                  <dd class="font-mono text-sm font-semibold tabular-nums text-(--sk-ink)">
                    {{ metric.value }}
                  </dd>
                </div>
              </dl>
            </section>

            <section class="rounded-(--sk-r-chip) border border-(--sk-border) p-3">
              <h3 class="mb-2 sk-title">
                Largest radial residual
              </h3>
              <p class="font-mono text-lg font-semibold tabular-nums text-(--sk-ink)">
                {{ withUnit(profile.metrics.maxAbsResidual, 4) }}
              </p>
              <p class="sk-meta">
                {{ profile.metrics.maxResidualSequence != null ? `sequence ${profile.metrics.maxResidualSequence}` : 'not available' }}
              </p>
              <p class="mt-2 sk-meta">
                Residual candidates are diagnostic evidence only. They do not replace the dashboard's site verdict.
              </p>
            </section>

            <section class="rounded-(--sk-r-chip) border border-(--sk-border) p-3">
              <h3 class="mb-2 sk-title">
                Model details
              </h3>
              <p class="break-words font-mono text-xs leading-5 text-(--sk-ink-muted)">
                {{ equation }}
              </p>
              <p class="mt-2 sk-meta">
                t is normalized over the observed radius range. The curve is never extended into an unmeasured center or edge region.
              </p>
            </section>

            <section class="rounded-(--sk-r-chip) border border-(--sk-border) p-3">
              <h3 class="mb-2 sk-title">
                Band meaning
              </h3>
              <p class="sk-meta">
                <template v-if="band === 'iqr'">
                  IQR shows the observed middle 50% within radial bins.
                </template>
                <template v-else-if="band === 'confidence'">
                  95% confidence estimates uncertainty in the mean fitted trend.
                </template>
                <template v-else-if="band === 'prediction'">
                  95% prediction estimates the range for one additional site under OLS assumptions.
                </template>
                <template v-else>
                  No spread band is shown.
                </template>
              </p>
              <p
                v-if="band === 'confidence' || band === 'prediction'"
                class="mt-2 text-(--sk-warn) sk-meta"
              >
                Wafer sites can be spatially correlated, so model-based intervals may be optimistic.
              </p>
            </section>

            <section
              v-if="colorBySector"
              class="rounded-(--sk-r-chip) border border-(--sk-border) p-3"
            >
              <h3 class="mb-2 sk-title">
                Sectors
              </h3>
              <div class="flex flex-wrap gap-2 font-mono text-xs">
                <span class="text-[#5C86AE]">● E</span>
                <span class="text-[#C75A3C]">● N</span>
                <span class="text-[#C98A2E]">● W</span>
                <span class="text-[#3E8E5E]">● S</span>
              </div>
            </section>
          </aside>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import {
  analyzeRadialProfile,
  type RadialBandMode,
  type RadialModel,
  type RadialSample
} from '~/utils/radialAnalysis'

const props = defineProps<{
  modelValue: boolean
  samples: RadialSample[]
  parameter: string
  unit: string
  focusedSequence: number | null
  initialModel: RadialModel
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'focus': [sequence: number]
}>()

const model = ref<RadialModel>(props.initialModel)
const band = ref<RadialBandMode>('iqr')
const colorBySector = ref(false)

const modelItems = [
  { label: 'Raw only', value: 'none' },
  { label: 'Linear · 1°', value: 'linear' },
  { label: 'Quadratic · 2°', value: 'quadratic' },
  { label: 'Cubic · 3°', value: 'cubic' }
]
const bandItems = [
  { label: 'Observed IQR', value: 'iqr' },
  { label: '95% confidence', value: 'confidence' },
  { label: '95% prediction', value: 'prediction' },
  { label: 'No band', value: 'none' }
]

const profile = computed(() => analyzeRadialProfile(props.samples, { model: model.value }))

const format = (value: number | null, digits: number): string =>
  value != null && Number.isFinite(value) ? value.toFixed(digits) : '—'
const withUnit = (value: number | null, digits: number): string => {
  const shown = format(value, digits)
  return shown === '—' || !props.unit ? shown : `${shown} ${props.unit}`
}
const metricItems = computed(() => [
  { label: 'Adjusted R²', value: format(profile.value.metrics.adjustedR2, 3) },
  { label: 'RMSE', value: withUnit(profile.value.metrics.rmse, 4) },
  { label: 'CV RMSE', value: withUnit(profile.value.metrics.cvRmse, 4) },
  { label: 'Residual σ', value: withUnit(profile.value.metrics.residualStd, 4) },
  { label: 'Residual MAD', value: withUnit(profile.value.metrics.residualMad, 4) },
  { label: 'Δ observed span', value: withUnit(profile.value.metrics.spanDelta, 4) }
])
const equation = computed(() => {
  const coefficients = profile.value.coefficients
  if (!coefficients) return model.value === 'none' ? 'No regression model selected.' : 'Fit not available for this radius layout.'
  return coefficients.map((coefficient, i) => {
    const sign = i > 0 && coefficient >= 0 ? '+ ' : ''
    const term = i === 0 ? '' : (i === 1 ? '·t' : `·t^${i}`)
    return `${sign}${coefficient.toFixed(5)}${term}`
  }).join(' ')
})

const close = () => emit('update:modelValue', false)
const onKey = (event: KeyboardEvent) => {
  if (event.key === 'Escape') close()
}
watch(() => props.modelValue, (open) => {
  if (!import.meta.client) return
  if (open) {
    model.value = props.initialModel
    window.addEventListener('keydown', onKey)
  } else {
    window.removeEventListener('keydown', onKey)
  }
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', onKey)
})
</script>
