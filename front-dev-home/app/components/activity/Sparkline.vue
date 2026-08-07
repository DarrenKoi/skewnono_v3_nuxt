<template>
  <div>
    <div
      v-if="hasData"
      class="flex justify-end text-[10px] text-(--sk-ink-muted) mb-1 tabular-nums"
    >
      <span>{{ totalLabel }}</span>
    </div>
    <div
      v-if="hasData"
      ref="chartEl"
      data-testid="sparkline-canvas"
      class="w-full h-16"
    />
    <div
      v-else
      class="sk-body h-16 flex items-center"
    >
      30일간 활동이 없습니다.
    </div>
    <div
      v-if="hasData"
      class="flex justify-between text-[10px] text-(--sk-ink-muted) mt-1 tabular-nums"
    >
      <span>{{ firstLabel }}</span>
      <span>{{ lastLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DailyCount } from '~/composables/useActivityApi'
import {
  buildSparklineOption,
  formatSparklineDay,
  sparklineHasData,
  sparklineTotal
} from '~/utils/activitySparkline'

const props = withDefaults(
  defineProps<{
    series: DailyCount[]
    // Which palette role paints the bars. The page uses two so the reader can
    // tell "my activity" from "the user I expanded" at a glance; both follow
    // the active ECharts theme rather than a hardcoded hex.
    tone?: 'series' | 'brand'
  }>(),
  { tone: 'series' }
)

const chartEl = ref<HTMLDivElement | null>(null)
const sk = useChartPalette()

const hasData = computed(() => sparklineHasData(props.series))
const barColor = computed(() => (props.tone === 'brand' ? sk.value.brand : sk.value.series))
const option = computed(() => buildSparklineOption(props.series, barColor.value))

// The host sits inside v-if, so an empty series never mounts it and no chart is
// created — which matters in the user table, where every expanded row would
// otherwise cost an instance. useEchart's elRef watch initialises against the
// node if and when it appears.
useEchart(chartEl, option, { disableDownload: true })

const totalLabel = computed(() => `합계 ${sparklineTotal(props.series)}`)
const firstLabel = computed(() =>
  props.series.length ? formatSparklineDay(props.series[0]!.date) : ''
)
const lastLabel = computed(() =>
  props.series.length ? formatSparklineDay(props.series[props.series.length - 1]!.date) : ''
)
</script>
