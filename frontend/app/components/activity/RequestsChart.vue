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
    이 기간에는 요청 기록이 없습니다.
  </p>
</template>

<script setup lang="ts">
import type { DailyRequests } from '~/composables/useActivityApi'
import { buildRequestsOption } from '~/utils/activityRequests'

const props = defineProps<{
  // Already cut to the chosen window — the tabs live in the card header.
  series: DailyRequests[]
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const hasData = computed(() => props.series.some(day => day.requests > 0))
// No color set: the active ECharts theme supplies it.
const option = computed(() => buildRequestsOption(props.series))

useEchart(chartEl, option, { exportName: '요청 추이' })
</script>
