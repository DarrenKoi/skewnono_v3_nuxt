<template>
  <div
    v-if="hasData"
    ref="chartEl"
    class="h-56 w-full"
  />
  <p
    v-else
    class="sk-body h-56 flex items-center justify-center"
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

const hasData = computed(() => props.series.some(day => day.visitors > 0))
// No bar color set: the active ECharts theme hands out its first series color.
const option = computed(() => buildVisitorsOption(props.series))

useEchart(chartEl, option, { exportName: '일별 방문자' })
</script>
