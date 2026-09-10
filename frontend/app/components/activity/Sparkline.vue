<template>
  <div>
    <div
      v-if="hasData"
      class="flex justify-between text-xs text-(--sk-ink-muted) mb-1 tabular-nums"
    >
      <span class="text-(--sk-ink-subtle) truncate">막대를 누르면 그날 호출한 기능을 봅니다</span>
      <span class="shrink-0">{{ totalLabel }}</span>
    </div>
    <div
      v-if="hasData"
      ref="chartEl"
      data-testid="sparkline-canvas"
      class="w-full h-16 cursor-pointer"
    />
    <div
      v-else
      class="sk-body h-16 flex items-center"
    >
      30일간 활동이 없습니다.
    </div>
    <div
      v-if="hasData"
      class="flex justify-between text-xs text-(--sk-ink-muted) mt-1 tabular-nums"
    >
      <span>{{ firstLabel }}</span>
      <span>{{ lastLabel }}</span>
    </div>

    <!-- The clicked day. Lives inside this component rather than in the page
         so both callers — my own card and an expanded user row — get the
         drill-down from the same series they already pass in. -->
    <div
      v-if="selected"
      class="mt-3 pt-3 border-t border-(--sk-border)"
    >
      <div class="flex items-center justify-between gap-2 mb-2">
        <span class="sk-value">
          {{ formatSparklineDay(selected.date) }} · {{ selected.count }}건
        </span>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="선택한 날짜 닫기"
          @click="selectedIndex = null"
        />
      </div>
      <ActivityFeatureBarList
        :items="selected.features"
        empty-text="이 날은 기능 호출 기록이 없습니다."
      />
      <!-- Named, not hidden: the bar counts every request and the list only
           counts feature calls, so the gap is entry traffic rather than a
           dropped row. -->
      <p
        v-if="selected.other_count > 0"
        class="sk-meta mt-2"
      >
        진입 요청 {{ selected.other_count }}건은 기능에 속하지 않습니다.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DailyCount } from '~/composables/useActivityApi'
import { nearestIndex } from '~/utils/chartNearest'
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

const selectedIndex = ref<number | null>(null)
const selected = computed(() =>
  selectedIndex.value === null ? null : props.series[selectedIndex.value] ?? null
)

// A refreshed series is a different 30 days, so an index picked against the
// old one now points at another date.
watch(() => props.series, () => {
  selectedIndex.value = null
})

// The host sits inside v-if, so an empty series never mounts it and no chart is
// created — which matters in the user table, where every expanded row would
// otherwise cost an instance. useEchart's elRef watch initialises against the
// node if and when it appears.
useEchart(chartEl, option, {
  disableDownload: true,
  // Grid click, not a series click: a one-request day is a 2px-tall bar, and
  // the tooltip already trades item hits for whole-column ones for exactly
  // this reason. Clicking the column is clicking the day.
  onGridClick: ({ x }) => {
    const index = nearestIndex(x, props.series.length)
    if (index === null) return
    selectedIndex.value = selectedIndex.value === index ? null : index
  }
})

const totalLabel = computed(() => `합계 ${sparklineTotal(props.series)}`)
const firstLabel = computed(() =>
  props.series.length ? formatSparklineDay(props.series[0]!.date) : ''
)
const lastLabel = computed(() =>
  props.series.length ? formatSparklineDay(props.series[props.series.length - 1]!.date) : ''
)
</script>
