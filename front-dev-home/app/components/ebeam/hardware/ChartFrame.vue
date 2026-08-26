<template>
  <div class="flex flex-col">
    <div class="mb-1 text-center sk-title">
      {{ title }}
    </div>
    <div
      v-if="empty"
      class="flex h-80 items-center justify-center sk-body"
    >
      측정을 선택하세요.
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-80 w-full"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

// Shared frame for the hardware measurement charts (radar, degree-profile):
// centered title, a "select a measurement" empty state, and an ECharts host
// wired to useEchart. Each chart component computes its own `option` and hands
// it here, so only the option-building differs between the charts.
const props = defineProps<{
  title: string
  // Show the placeholder instead of the chart. Callers pass their own predicate
  // (currently values.length === 0) so the frame stays data-shape agnostic.
  empty: boolean
  option: EChartsOption
}>()

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, computed(() => props.option))
</script>
