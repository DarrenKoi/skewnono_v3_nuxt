<template>
  <AfmCard
    icon="i-lucide-grid-3x3"
    title="웨이퍼 히트맵"
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
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { OutlierMethod } from '~/utils/afmHeatmap'

const props = defineProps<{
  profile: AfmProfilePoint[]
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

const formatTooltip = (params: unknown) => {
  const value = (params as { value?: unknown }).value
  if (!Array.isArray(value)) return ''
  const [x, y, z] = value
  if (typeof x !== 'number' || typeof y !== 'number' || typeof z !== 'number') return ''
  return `x: ${x.toFixed(1)}<br/>y: ${y.toFixed(1)}<br/>z: ${z.toFixed(2)}`
}

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 56, right: 72, top: 16, bottom: 36 },
  tooltip: {
    formatter: formatTooltip
  },
  xAxis: { type: 'value', scale: true, axisLabel: CHART_AXIS_LABEL },
  yAxis: { type: 'value', scale: true, axisLabel: CHART_AXIS_LABEL },
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

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
