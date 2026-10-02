<template>
  <AfmCard
    icon="i-lucide-grid-3x3"
    :title="isLine ? '라인 프로파일' : '웨이퍼 히트맵'"
  >
    <template
      v-if="stats.count"
      #actions
    >
      <p class="flex flex-wrap items-center gap-x-2 sk-meta">
        <span><b class="sk-value-num">{{ stats.count.toLocaleString() }}</b> pts</span>
        <span>min <b class="sk-value-num">{{ stats.min.toFixed(2) }}</b></span>
        <span>max <b class="sk-value-num">{{ stats.max.toFixed(2) }}</b></span>
        <span>μ <b class="sk-value-num">{{ stats.mean.toFixed(2) }}</b></span>
        <span v-if="meta">{{ axisTitle('Z', meta.z_unit) }}</span>
        <UBadge
          v-if="filtered.removed > 0"
          :label="`${filtered.removed}개 제외`"
          color="warning"
          size="xs"
          variant="subtle"
        />
      </p>
    </template>

    <AppLoadingState
      v-if="loading"
      variant="inline"
      class="h-72"
      title="히트맵을 불러오는 중입니다."
    />
    <p
      v-else-if="profile.length === 0"
      class="flex h-72 items-center justify-center sk-body"
    >
      히트맵 데이터가 없습니다.
    </p>
    <template v-else>
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <USelect
          v-model="outlierMethod"
          :items="outlierMethodItems"
          size="xs"
          class="min-w-36"
          aria-label="이상치 필터"
        />
        <UInput
          v-if="outlierMethod !== 'none'"
          v-model.number="threshold"
          type="number"
          size="xs"
          class="w-24"
          :step="0.1"
          aria-label="이상치 기준값"
        />
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </template>
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfileMeta, AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { OutlierMethod } from '~/utils/afmHeatmap'

const props = defineProps<{
  profile: AfmProfilePoint[]
  meta?: AfmProfileMeta | null
  loading?: boolean
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const outlierMethod = ref<OutlierMethod>('none')
const threshold = ref<number>(OUTLIER_DEFAULT_THRESHOLD.iqr)

const outlierMethodItems: { label: string, value: OutlierMethod }[] = [
  { label: '이상치 필터 없음', value: 'none' },
  { label: 'IQR', value: 'iqr' },
  { label: 'Z-Score', value: 'zscore' }
]

watch(outlierMethod, (method) => {
  if (method !== 'none') threshold.value = OUTLIER_DEFAULT_THRESHOLD[method]
})

const filtered = computed(() =>
  filterProfileByOutlier(props.profile, outlierMethod.value, threshold.value)
)
const stats = computed(() => heatmapStats(filtered.value.kept))

// A 1D profile has no second lateral axis to map, so it is drawn as height along the line.
const isLine = computed(() => isLineProfile(props.profile, props.meta?.data_size))

const axisName = (name: string, gap: number) => ({
  name,
  nameLocation: 'middle' as const,
  nameGap: gap,
  nameTextStyle: CHART_LEGEND_LABEL
})
// A file in nm or pm labels its lateral axis in five- and six-digit numbers.
const tickLabel = { ...CHART_AXIS_LABEL, hideOverlap: true }
const xName = computed(() => axisTitle('X', props.meta?.x_unit))
const yName = computed(() => axisTitle('Y', props.meta?.y_unit))
const zName = computed(() => axisTitle('Z', props.meta?.z_unit))

// The line's axis trigger hands over one entry per series, the map's item trigger a single one.
const formatTooltip = (params: unknown) => {
  const value = ((Array.isArray(params) ? params[0] : params) as { value?: unknown } | undefined)?.value
  if (!Array.isArray(value) || !value.every(v => typeof v === 'number')) return ''
  const names = value.length === 2 ? [xName.value, zName.value] : [xName.value, yName.value, zName.value]
  return value.map((v, i) => `${names[i]}: ${v.toFixed(2)}`).join('<br/>')
}

const lineOption = computed<EChartsOption>(() => ({
  grid: { left: 72, right: 16, top: 16, bottom: 48 },
  // Axis-triggered: with no symbols drawn there is no item under the cursor to hit.
  tooltip: { trigger: 'axis', formatter: formatTooltip },
  xAxis: { type: 'value', scale: true, axisLabel: tickLabel, ...axisName(xName.value, 30) },
  yAxis: { type: 'value', scale: true, axisLabel: CHART_AXIS_LABEL, ...axisName(zName.value, 52) },
  series: [{
    type: 'line',
    // A single sample has no segment to draw, so it alone gets a symbol.
    showSymbol: filtered.value.kept.length === 1,
    // A line can hold 16384 samples; lttb keeps its shape at the canvas's width.
    sampling: 'lttb',
    data: filtered.value.kept.map(p => [p.x, p.z])
  }]
}))

const mapOption = computed<EChartsOption>(() => ({
  grid: { left: 72, right: 72, top: 16, bottom: 48 },
  tooltip: {
    formatter: formatTooltip
  },
  xAxis: { type: 'value', scale: true, axisLabel: tickLabel, ...axisName(xName.value, 30) },
  yAxis: { type: 'value', scale: true, axisLabel: CHART_AXIS_LABEL, ...axisName(yName.value, 52) },
  visualMap: {
    min: stats.value.count ? stats.value.min : 0,
    max: stats.value.count ? stats.value.max : 1,
    calculable: true,
    orient: 'vertical',
    right: 4,
    top: 'center',
    inRange: { color: [...SK_SCALE] },
    textStyle: CHART_LEGEND_LABEL
  },
  series: [{
    type: 'scatter',
    symbolSize: 8,
    data: filtered.value.kept.map(p => [p.x, p.y, p.z])
  }]
}))

const chartOption = computed(() => isLine.value ? lineOption.value : mapOption.value)

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
