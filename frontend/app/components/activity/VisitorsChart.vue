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
import { buildVisitorsOption } from '~/utils/activityVisitors'

const props = defineProps<{
  // Already cut to the chosen window — the tabs live in the card header, on
  // the page, like every other window toggle here.
  series: DailyVisitors[]
}>()

const chartEl = ref<HTMLDivElement | null>(null)

// MAU, not DAU: a window whose days were all quiet can still sit inside
// someone's month, and those lines are worth drawing.
const hasData = computed(() => props.series.some(day => day.mau > 0))
// No colors set: the active ECharts theme hands out its series colors in order.
const option = computed(() => buildVisitorsOption(props.series))

useEchart(chartEl, option, { exportName: '방문자 추이' })
</script>
