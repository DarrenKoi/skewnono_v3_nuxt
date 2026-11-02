<template>
  <div
    v-if="hasData"
    ref="chartEl"
    class="h-72 w-full"
  />
  <p
    v-else
    class="sk-body h-72 flex items-center justify-center"
  >
    이 기간에는 호출 기록이 없습니다.
  </p>
</template>

<script setup lang="ts">
import type { EndpointDay, EndpointsResponse } from '~/composables/useActivityApi'
import { buildEndpointsOption, type TrendAxis } from '~/utils/activityEndpoints'

const props = defineProps<{
  // Already cut to the chosen window — the tabs live in the card header.
  series: EndpointDay[]
  axis: TrendAxis
  names: EndpointsResponse['names']
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const hasData = computed(() => props.series.some(day => day.requests > 0))
// No color set: the active ECharts theme supplies it.
const option = computed(() => buildEndpointsOption(props.series, props.axis, props.names))

useEchart(chartEl, option, { exportName: '엔드포인트 호출 추이' })
</script>
