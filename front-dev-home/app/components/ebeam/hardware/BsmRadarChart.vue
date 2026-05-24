<template>
  <div class="flex flex-col">
    <div class="mb-1 text-center text-[11px] font-semibold uppercase tracking-[0.06em] text-(--sk-ink-muted)">
      {{ title }}
    </div>
    <div
      v-if="values.length === 0"
      class="flex h-64 items-center justify-center text-sm text-(--sk-ink-muted)"
    >
      측정을 선택하세요.
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-64 w-full"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  title: string
  angles: string[]
  values: number[]
  color: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

// Pad the shared radial scale by ~15% of the value range so the profile reads
// as a shape rather than a near-circle pinned to the axis edge.
const bounds = computed(() => {
  if (props.values.length === 0) return { min: 0, max: 1 }
  const lo = Math.min(...props.values)
  const hi = Math.max(...props.values)
  const pad = Math.max((hi - lo) * 0.15, 0.02)
  return {
    min: Number((lo - pad).toFixed(2)),
    max: Number((hi + pad).toFixed(2))
  }
})

const chartOption = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    valueFormatter: (value) => (typeof value === 'number' ? value.toFixed(3) : String(value))
  },
  radar: {
    indicator: props.angles.map(angle => ({
      name: `${angle}°`,
      min: bounds.value.min,
      max: bounds.value.max
    })),
    radius: '66%',
    axisName: { fontSize: 9, color: 'var(--sk-ink-muted)' },
    splitNumber: 4
  },
  series: [
    {
      type: 'radar',
      symbolSize: 3,
      lineStyle: { width: 2, color: props.color },
      itemStyle: { color: props.color },
      areaStyle: { opacity: 0.12, color: props.color },
      data: [{ value: props.values, name: props.title }]
    }
  ]
}))

useEchart(chartEl, chartOption)
</script>
