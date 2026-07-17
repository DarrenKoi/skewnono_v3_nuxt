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
        <span
          v-if="profile.length"
          class="sk-meta tabular-nums"
        >
          {{ profile.length.toLocaleString() }} points
        </span>
      </div>
    </template>

    <div
      v-if="loading"
      class="flex h-72 items-center justify-center sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mr-2 h-4 w-4 animate-spin"
      />
      Loading heat map…
    </div>
    <div
      v-else-if="profile.length === 0"
      class="flex h-72 items-center justify-center text-center sk-body"
    >
      Heat map data unavailable
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-72 w-full"
    />
  </UCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  profile: AfmProfilePoint[]
  loading?: boolean
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const formatTooltip = (params: unknown) => {
  const value = (params as { value?: unknown }).value
  if (!Array.isArray(value)) return ''
  const [x, y, z] = value
  if (typeof x !== 'number' || typeof y !== 'number' || typeof z !== 'number') return ''
  return `x: ${x.toFixed(1)}<br/>y: ${y.toFixed(1)}<br/>z: ${z.toFixed(2)}`
}

const zRange = computed(() => {
  if (!props.profile.length) return [0, 1]
  let min = Infinity
  let max = -Infinity
  for (const p of props.profile) {
    if (p.z < min) min = p.z
    if (p.z > max) max = p.z
  }
  return [min, max]
})

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
    inRange: { color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'] },
    textStyle: { fontSize: 10 }
  },
  series: [{
    type: 'scatter',
    symbolSize: 8,
    data: props.profile.map(p => [p.x, p.y, p.z])
  }]
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
