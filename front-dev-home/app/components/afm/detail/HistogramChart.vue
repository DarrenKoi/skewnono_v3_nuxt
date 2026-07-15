<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-bar-chart-3"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Z-value distribution
          </h2>
        </div>
        <span
          v-if="profile.length"
          class="sk-meta tabular-nums"
        >
          μ={{ stats.mean.toFixed(2) }} · σ={{ stats.stdev.toFixed(2) }}
        </span>
      </div>
    </template>

    <div
      v-if="loading"
      class="flex h-60 items-center justify-center sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mr-2 h-4 w-4 animate-spin"
      />
      Loading distribution…
    </div>
    <div
      v-else-if="profile.length === 0"
      class="flex h-60 items-center justify-center text-center sk-body"
    >
      No distribution data
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-60 w-full"
    />
  </UCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  profile: AfmProfilePoint[]
  loading?: boolean
}>()

const BIN_COUNT = 24

const stats = computed(() => {
  const points = props.profile
  if (points.length === 0) return { mean: 0, stdev: 0, min: 0, max: 0 }
  let sum = 0
  let min = Infinity
  let max = -Infinity
  for (const p of points) {
    sum += p.z
    if (p.z < min) min = p.z
    if (p.z > max) max = p.z
  }
  const mean = sum / points.length
  let sqSum = 0
  for (const p of points) sqSum += (p.z - mean) ** 2
  return { mean, stdev: Math.sqrt(sqSum / points.length), min, max }
})

const bins = computed(() => {
  if (props.profile.length === 0) return { centers: [], counts: [] }
  const { min, max } = stats.value
  const span = max - min || 1
  const width = span / BIN_COUNT
  const counts = new Array(BIN_COUNT).fill(0)
  for (const p of props.profile) {
    const idx = Math.min(BIN_COUNT - 1, Math.max(0, Math.floor((p.z - min) / width)))
    counts[idx] += 1
  }
  const centers = Array.from({ length: BIN_COUNT }, (_, i) =>
    (min + width * (i + 0.5)).toFixed(2)
  )
  return { centers, counts }
})

const chartEl = ref<HTMLDivElement | null>(null)

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 44, right: 12, top: 16, bottom: 32 },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: bins.value.centers,
    axisLabel: { fontSize: 10, interval: 3 }
  },
  yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
  series: [{
    type: 'bar',
    data: bins.value.counts,
    itemStyle: { borderRadius: [3, 3, 0, 0] }
  }]
}))

useEchart(chartEl, chartOption)
</script>
