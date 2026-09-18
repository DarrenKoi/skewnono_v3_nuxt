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
              반경 분석 · {{ parameter }}
            </h2>
            <p class="sk-meta">
              관측 반경 {{ format(profile.metrics.radiusMin, 1) }}–{{ format(profile.metrics.radiusMax, 1) }} mm · 측정점 {{ profile.metrics.n }}개 · 서로 다른 반경 {{ profile.metrics.distinctRadii }}개
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <!-- 세그먼트 버튼: 드롭다운은 body 로 portal 되어 이 z-50 다이얼로그 뒤에 깔렸다.
                 PanelFrame 의 토글과 같은 모양. -->
            <div
              class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
              role="group"
              aria-label="추세 모델"
            >
              <button
                v-for="item in modelItems"
                :key="item.value"
                type="button"
                class="rounded-[6px] px-2.5 py-1 font-mono text-xs font-medium transition-colors duration-200"
                :class="item.value === model
                  ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
                  : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
                :aria-pressed="item.value === model"
                @click="model = item.value"
              >
                {{ item.label }}
              </button>
            </div>
            <div class="inline-flex items-center gap-1">
              <div
                class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
                role="group"
                aria-label="산포 밴드"
              >
                <button
                  v-for="item in bandItems"
                  :key="item.value"
                  type="button"
                  class="rounded-[6px] px-2.5 py-1 font-mono text-xs font-medium transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40"
                  :class="item.value === band
                    ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
                    : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
                  :aria-pressed="item.value === band"
                  :disabled="item.needsFit && profile.status !== 'fitted'"
                  :title="item.needsFit && profile.status !== 'fitted' ? '추세선이 있어야 계산됩니다' : undefined"
                  @click="band = item.value"
                >
                  {{ item.label }}
                </button>
              </div>
              <EbeamSkewvoirDashboardInfoTip
                label="산포 밴드"
                :text="bandHint"
              />
            </div>
            <UButton
              color="neutral"
              :variant="colorBySector ? 'solid' : 'subtle'"
              size="sm"
              icon="i-lucide-scan"
              label="섹터 색"
              :aria-pressed="colorBySector"
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
              {{ warningKo }} 원본 점과 반경 구간 중앙값은 그대로 표시됩니다.
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
                적합 품질
              </h3>
              <dl class="grid grid-cols-2 gap-x-3 gap-y-2">
                <div
                  v-for="metric in metricItems"
                  :key="metric.label"
                >
                  <dt class="flex items-center gap-1 sk-meta">
                    {{ metric.label }}
                    <EbeamSkewvoirDashboardInfoTip
                      :label="metric.label"
                      :text="metric.hint"
                    />
                  </dt>
                  <dd class="font-mono text-sm font-semibold tabular-nums text-(--sk-ink)">
                    {{ metric.value }}
                  </dd>
                </div>
              </dl>
            </section>

            <section class="rounded-(--sk-r-chip) border border-(--sk-border) p-3">
              <h3 class="mb-2 flex items-center gap-1 sk-title">
                가장 큰 잔차
                <EbeamSkewvoirDashboardInfoTip
                  label="가장 큰 잔차"
                  text="추세선에서 가장 멀리 떨어진 측정점입니다. 진단용 단서일 뿐, 측정 개요의 사이트 판정을 대신하지 않습니다."
                />
              </h3>
              <p class="font-mono text-lg font-semibold tabular-nums text-(--sk-ink)">
                {{ withUnit(profile.metrics.maxAbsResidual, 4) }}
              </p>
              <p class="sk-meta">
                {{ profile.metrics.maxResidualSequence != null ? `측정점 seq ${profile.metrics.maxResidualSequence}` : '추세선이 없어 계산되지 않았습니다' }}
              </p>
            </section>

            <section class="rounded-(--sk-r-chip) border border-(--sk-border) p-3">
              <h3 class="mb-2 flex items-center gap-1 sk-title">
                모델 식
                <EbeamSkewvoirDashboardInfoTip
                  label="모델 식"
                  text="t 는 관측 반경 범위를 -1~1 로 정규화한 값입니다. 측정하지 않은 중심·가장자리 구간으로는 곡선을 연장하지 않습니다."
                />
              </h3>
              <p class="break-words font-mono text-xs leading-5 text-(--sk-ink-muted)">
                {{ equation }}
              </p>
            </section>

            <section
              v-if="colorBySector"
              class="rounded-(--sk-r-chip) border border-(--sk-border) p-3"
            >
              <h3 class="mb-2 flex items-center gap-1 sk-title">
                섹터
                <EbeamSkewvoirDashboardInfoTip
                  label="섹터"
                  text="웨이퍼 중심 기준 방위로 점을 4등분해 색을 입혔습니다. 한 방향만 추세선에서 벗어나면 반경이 아니라 방향(틸트·정렬) 문제를 의심할 수 있습니다."
                />
              </h3>
              <div class="flex flex-wrap gap-3 font-mono text-xs">
                <span
                  v-for="sector in sectorLegend"
                  :key="sector.key"
                  :style="{ color: sector.color }"
                >● {{ sector.key }} {{ sector.name }}</span>
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
import { SK_STATE } from '~/utils/chartPalette'

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
const colorBySector = ref(true)

const modelItems: { label: string, value: RadialModel }[] = [
  { label: '원본만', value: 'none' },
  { label: '1차', value: 'linear' },
  { label: '2차', value: 'quadratic' },
  { label: '3차', value: 'cubic' }
]
const bandItems: { label: string, value: RadialBandMode, needsFit: boolean }[] = [
  { label: 'IQR', value: 'iqr', needsFit: false },
  { label: '95% 신뢰', value: 'confidence', needsFit: true },
  { label: '95% 예측', value: 'prediction', needsFit: true },
  { label: '없음', value: 'none', needsFit: false }
]
const bandHints: Record<RadialBandMode, string> = {
  iqr: 'IQR: 반경 구간별 실측값의 가운데 50% 범위입니다. 모델과 무관하게 관측만으로 그립니다.',
  confidence: '95% 신뢰: 추세선(평균) 자체가 어디에 있을지의 불확실성입니다. 같은 조건이면 점이 많을수록 대체로 좁아집니다. 최소제곱(OLS) 가정 위에서 계산하며, 웨이퍼 점들은 공간적으로 상관되어 있어 실제보다 낙관적일 수 있습니다.',
  prediction: '95% 예측: 새 측정점 하나가 떨어질 범위입니다. 신뢰 밴드에 잔차 산포가 더해지므로 대체로 더 넓습니다. 최소제곱(OLS) 가정 위에서 계산하며, 웨이퍼 점들은 공간적으로 상관되어 있어 실제보다 낙관적일 수 있습니다.',
  none: '산포 밴드를 표시하지 않습니다.'
}
const bandHint = computed(() => bandHints[band.value])

const profile = computed(() => analyzeRadialProfile(props.samples, { model: model.value }))

// A model change can leave a model-based band with nothing to draw.
watch(() => profile.value.status, (status) => {
  if (status !== 'fitted' && (band.value === 'confidence' || band.value === 'prediction')) band.value = 'iqr'
})

const format = (value: number | null, digits: number): string =>
  value != null && Number.isFinite(value) ? value.toFixed(digits) : '—'
const withUnit = (value: number | null, digits: number): string => {
  const shown = format(value, digits)
  return shown === '—' || !props.unit ? shown : `${shown} ${props.unit}`
}
const metricItems = computed(() => [
  {
    label: '조정 R²',
    value: format(profile.value.metrics.adjustedR2, 3),
    hint: '추세선이 값 변동을 얼마나 설명하는지를 차수(복잡도) 벌점을 준 뒤 매긴 점수입니다. 1 에 가까울수록 반경 추세가 뚜렷하고, 0 이하이면 벌점을 감안하면 평균선보다 나을 게 없다는 뜻입니다. 차수를 올려도 공짜로 오르지 않습니다.'
  },
  {
    label: 'RMSE',
    value: withUnit(profile.value.metrics.rmse, 4),
    hint: '실측값과 추세선 차이(잔차)의 제곱평균제곱근입니다. 측정값과 같은 단위이며, 작을수록 추세선이 점들을 가깝게 지납니다.'
  },
  {
    label: 'CV RMSE',
    value: withUnit(profile.value.metrics.cvRmse, 4),
    hint: '측정점을 하나씩 빼고 나머지로 예측했을 때의 오차(교차검증)입니다. RMSE 보다 훨씬 크면 특정 점에 끌려간 과적합을 의심합니다.'
  },
  {
    label: '잔차 σ',
    value: withUnit(profile.value.metrics.residualStd, 4),
    hint: '잔차의 표준편차(자유도 보정)입니다. 이상점 하나에도 크게 움직입니다.'
  },
  {
    label: '잔차 MAD',
    value: withUnit(profile.value.metrics.residualMad, 4),
    hint: '잔차의 중앙절대편차를 σ 척도로 환산한 값입니다. 이상점에 둔감하므로 σ 와 크게 벌어지면 소수의 점이 튀고 있을 가능성을 시사합니다.'
  },
  {
    label: 'Δ 추세',
    value: withUnit(profile.value.metrics.spanDelta, 4),
    hint: '가장 바깥 반경의 추세값에서 가장 안쪽 반경의 추세값을 뺀 값입니다. 부호가 중심→가장자리 방향을, 크기가 그 폭을 나타냅니다.'
  }
])
// radialAnalysis.ts phrases its warnings in English; translate at the
// presentation layer so the math module stays language-free.
const MODEL_KO: Record<string, string> = { linear: '1차', quadratic: '2차', cubic: '3차' }
const warningKo = computed(() => {
  const warning = profile.value.warning
  if (!warning) return ''
  let match = warning.match(/^(\w+) fit requires at least (\d+) measured sites$/)
  if (match) return `${MODEL_KO[match[1]!] ?? match[1]} 추세선에는 측정점이 최소 ${match[2]}개 필요합니다.`
  match = warning.match(/^(\w+) fit requires at least (\d+) distinct radii$/)
  if (match) return `${MODEL_KO[match[1]!] ?? match[1]} 추세선에는 서로 다른 반경이 최소 ${match[2]}개 필요합니다.`
  if (warning.startsWith('fit is singular')) return '이 반경 배치로는 추세선을 구할 수 없습니다.'
  return `${warning}.`
})
const equation = computed(() => {
  const coefficients = profile.value.coefficients
  if (!coefficients) return model.value === 'none' ? '추세 모델을 선택하지 않았습니다.' : '이 반경 배치로는 추세선을 구할 수 없습니다.'
  return coefficients.map((coefficient, i) => {
    const sign = i > 0 && coefficient >= 0 ? '+ ' : ''
    const term = i === 0 ? '' : (i === 1 ? '·t' : `·t^${i}`)
    return `${sign}${coefficient.toFixed(5)}${term}`
  }).join(' ')
})

// Same source RadiusChart paints from, so the legend cannot drift from the dots.
const sk = useChartPalette()
const sectorLegend = computed(() => [
  { key: 'E', name: '동', color: sk.value.series },
  { key: 'N', name: '북', color: sk.value.brand },
  { key: 'W', name: '서', color: SK_STATE.warn },
  { key: 'S', name: '남', color: SK_STATE.ok }
])

const close = () => emit('update:modelValue', false)
const onKey = (event: KeyboardEvent) => {
  // An open (i) tooltip owns the first Escape; Reka does not stop propagation.
  if (event.key === 'Escape' && !document.querySelector('[role="tooltip"]')) close()
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
