<template>
  <div class="space-y-3">
    <p class="sk-meta">
      {{ series[0]?.date }} ~ {{ series.at(-1)?.date }} · 방문한 날 {{ activeDays }}일
    </p>
    <div
      v-if="series.length"
      class="overflow-x-auto pb-2"
    >
      <div class="flex gap-1 w-max mx-auto">
        <div class="grid grid-rows-8 gap-1 text-xs text-(--sk-ink-muted) pr-2">
          <span />
          <span
            v-for="day in ['월', '화', '수', '목', '금', '토', '일']"
            :key="day"
            class="h-8 leading-8"
          >{{ day }}</span>
        </div>
        <div
          v-for="week in weeks"
          :key="week.start"
          class="grid grid-rows-8 gap-1"
        >
          <span class="text-xs h-8 w-8 leading-8 whitespace-nowrap text-(--sk-ink-muted)">{{ week.month }}</span>
          <template
            v-for="(day, index) in week.days"
            :key="index"
          >
            <button
              v-if="day"
              type="button"
              class="size-8 rounded-[var(--sk-r-sidebar)] border border-(--sk-border) focus-visible:outline-2 focus-visible:outline-(--sk-focus-ring)"
              :style="{ background: day.count ? `color-mix(in srgb, var(--sk-brand) ${25 + 75 * Math.min(day.count / maximum, 1)}%, var(--sk-surface))` : 'var(--sk-muted-surface)' }"
              :aria-label="`${day.date} · 페이지 조회 ${day.count}회`"
              :title="`${day.date} · 페이지 조회 ${day.count}회`"
              :aria-pressed="selected?.date === day.date"
              :class="{ 'outline-2 outline-(--sk-ink)': selected?.date === day.date }"
              @click="selected = day"
              @focus="selected = day"
            />
            <span
              v-else
              class="size-8"
            />
          </template>
        </div>
      </div>
    </div>
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
      {{ selected ? `${selected.date} · 페이지 조회 ${selected.count.toLocaleString()}회` : '날짜를 선택하면 페이지 조회 수를 확인합니다.' }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { calendarWeeks, type VisitDay } from '~/utils/activityCalendar'

const props = defineProps<{ series: VisitDay[] }>()
const weeks = computed(() => calendarWeeks(props.series))
const activeDays = computed(() => props.series.filter(day => day.count > 0).length)
const maximum = computed(() => Math.max(1, ...props.series.map(day => day.count)))
const selected = ref<VisitDay | null>(null)
watch(() => props.series, () => {
  selected.value = null
})
</script>
