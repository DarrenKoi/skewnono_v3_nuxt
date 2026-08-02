<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-grid-3x3"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Wafer heat map
          </h2>
        </div>
        <div
          v-if="stats.count"
          class="flex items-center gap-2 sk-meta tabular-nums"
        >
          <span>{{ stats.count.toLocaleString() }} pts</span>
          <span>min {{ stats.min.toFixed(2) }}</span>
          <span>max {{ stats.max.toFixed(2) }}</span>
          <span>μ {{ stats.mean.toFixed(2) }}</span>
          <UBadge
            v-if="filtered.removed > 0"
            :label="`${filtered.removed} removed`"
            color="warning"
            size="xs"
            variant="subtle"
          />
        </div>
      </div>
    </template>

    <AppLoadingState
      v-if="loading"
      variant="inline"
      class="h-72"
      title="히트맵을 불러오는 중입니다."
    />
    <div
      v-else-if="profile.length === 0"
      class="flex h-72 items-center justify-center text-center sk-body"
    >
      Heat map data unavailable
    </div>
    <template v-else>
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <USelect
          v-model="outlierMethod"
          :items="outlierMethodItems"
          size="xs"
          class="min-w-36"
          aria-label="Outlier method"
        />
        <UInput
          v-if="outlierMethod !== 'none'"
          v-model.number="threshold"
          type="number"
          size="xs"
          class="w-24"
          :step="0.1"
          aria-label="Outlier threshold"
        />
        <USelect
          v-model="colorScheme"
          :items="colorSchemeItems"
          size="xs"
          class="min-w-28"
          aria-label="Color scheme"
        />
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </template>
  </UCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { OutlierMethod, HeatmapColorScheme } from '~/utils/afmHeatmap'

const props = defineProps<{
  profile: AfmProfilePoint[]
  loading?: boolean
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const outlierMethod = ref<OutlierMethod>('none')
const threshold = ref<number>(OUTLIER_DEFAULT_THRESHOLD.iqr)
const colorScheme = ref<HeatmapColorScheme>('spectral')

const outlierMethodItems: { label: string, value: OutlierMethod }[] = [
  { label: 'No outlier filter', value: 'none' },
  { label: 'IQR', value: 'iqr' },
  { label: 'Z-Score', value: 'zscore' }
]
const colorSchemeItems: { label: string, value: HeatmapColorScheme }[] = [
  { label: 'Spectral', value: 'spectral' },
  { label: 'Viridis', value: 'viridis' },
  { label: 'Grayscale', value: 'grayscale' }
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

const zRange = computed(() =>
  stats.value.count ? [stats.value.min, stats.value.max] : [0, 1]
)

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 50, right: 60, top: 16, bottom: 36 },
  tooltip: {
    formatter: formatTooltip
  },
  xAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  visualMap: {
    min: zRange.value[0],
    max: zRange.value[1],
    calculable: true,
    orient: 'vertical',
    right: 4,
    top: 'center',
    inRange: { color: HEATMAP_COLOR_RAMPS[colorScheme.value] },
    textStyle: { fontSize: 10 }
  },
  series: [{
    type: 'scatter',
    symbolSize: 8,
    data: filtered.value.kept.map(p => [p.x, p.y, p.z])
  }]
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
