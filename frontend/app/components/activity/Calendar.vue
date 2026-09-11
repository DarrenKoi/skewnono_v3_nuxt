<template>
  <div class="space-y-3">
    <p class="sk-meta">
      {{ series[0]?.date }} ~ {{ series.at(-1)?.date }} · 방문한 날 {{ activeDays }}일
    </p>
    <div
      v-if="series.length"
      ref="chartEl"
      data-testid="visit-calendar-canvas"
      class="w-full h-44 cursor-pointer"
    />
    <p
      v-else
      class="sk-body"
    >
      방문 기록을 불러오지 못했습니다.
    </p>
    <div class="flex flex-wrap justify-between gap-2 sk-meta">
      <span>진한 칸일수록 페이지 조회가 많습니다. 빈 칸은 보관된 조회 기록이 없는 날입니다.</span>
      <span>한국 시간 기준</span>
    </div>
    <p
      class="sk-value min-h-5"
      aria-live="polite"
    >
      {{ selected ? visitLabel(selected) : '날짜를 누르면 페이지 조회 수를 확인합니다.' }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { buildCalendarOption, visitLabel, type VisitDay } from '~/utils/activityCalendar'

const props = defineProps<{ series: VisitDay[] }>()

const chartEl = ref<HTMLDivElement | null>(null)
const sk = useChartPalette()

const activeDays = computed(() => props.series.filter(day => day.count > 0).length)
// Zero-visit days sit at the palette's neutral band, so an empty day reads as
// "nothing" rather than as the faintest shade of the series color.
const option = computed(() => buildCalendarOption(props.series, {
  empty: sk.value.sand,
  full: sk.value.series,
  ink: sk.value.ink,
  muted: sk.value.muted
}))

const selected = ref<VisitDay | null>(null)
watch(() => props.series, () => {
  selected.value = null
})

useEchart(chartEl, option, {
  exportName: 'visit-calendar',
  onDataIndex: (dataIndex) => {
    const day = props.series[dataIndex] ?? null
    selected.value = selected.value?.date === day?.date ? null : day
  }
})
</script>
