<template>
  <div
    v-if="hasData"
    ref="chartEl"
    class="h-64 w-full"
  />
  <p
    v-else
    class="sk-body h-64 flex items-center justify-center"
  >
    이 기간에는 방문 기록이 없습니다.
  </p>
</template>

<script setup lang="ts">
import type { DailyVisitors } from '~/composables/useActivityApi'
import { buildVisitorsOption, type VisitorMetricKey } from '~/utils/activityVisitors'

const props = defineProps<{
  // Already cut to the chosen window — the tabs live in the card header, on
  // the page, like every other window toggle here.
  series: DailyVisitors[]
  metric: VisitorMetricKey
}>()

const chartEl = ref<HTMLDivElement | null>(null)

// MAU, not the shown metric: a window whose days were all quiet can still sit
// inside someone's month, and an all-zero DAU tab is an answer, not an absence.
const hasData = computed(() => props.series.some(day => day.mau > 0))
// No color set: the active ECharts theme supplies it.
const option = computed(() => buildVisitorsOption(props.series, props.metric))

useEchart(chartEl, option, { exportName: '방문자 추이' })
</script>
