<template>
  <div>
    <div
      v-if="hasData"
      class="flex justify-end text-[10px] text-(--sk-ink-muted) mb-1 tabular-nums"
    >
      <span>{{ totalLabel }}</span>
    </div>
    <svg
      v-if="hasData"
      :viewBox="`0 0 ${width} ${height}`"
      class="w-full h-16"
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient
          :id="gradientId"
          x1="0"
          x2="1"
          y1="0"
          y2="0"
        >
          <stop
            offset="0%"
            :stop-color="gradientStops.start"
          />
          <stop
            offset="100%"
            :stop-color="gradientStops.end"
          />
        </linearGradient>
      </defs>
      <rect
        v-for="bar in bars"
        :key="bar.x"
        :x="bar.x"
        :y="bar.y"
        :width="barWidth"
        :height="bar.h"
        rx="1.5"
        :fill="`url(#${gradientId})`"
      />
    </svg>
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

// Tailwind gradient class -> resolved SVG stop colors. Keeps the prop API
// consistent with the rest of the page (other places use "from-X to-Y")
// without forcing inline styles at the call site.
const GRADIENT_MAP: Record<string, { start: string, end: string }> = {
  'from-sky-400 to-violet-500': { start: '#38bdf8', end: '#8b5cf6' },
  'from-rose-400 to-amber-500': { start: '#fb7185', end: '#f59e0b' },
  'from-emerald-400 to-sky-500': { start: '#34d399', end: '#0ea5e9' }
}

const props = withDefaults(
  defineProps<{
    series: DailyCount[]
    color?: string
  }>(),
  { color: 'from-sky-400 to-violet-500' }
)

const gradientStops = computed(
  () => GRADIENT_MAP[props.color] ?? GRADIENT_MAP['from-sky-400 to-violet-500']!
)

// Each Sparkline instance needs a unique <linearGradient id="..."> so multiple
// sparklines on the page don't share/overwrite each other's defs.
const uid = useId()
const gradientId = computed(() => `sparkline-gradient-${uid}`)

const width = 300
const height = 60
const padding = 4

const maxCount = computed(() => props.series.reduce((m, d) => Math.max(m, d.count), 0))
const hasData = computed(() => maxCount.value > 0)
const total = computed(() => props.series.reduce((s, d) => s + d.count, 0))

const barWidth = computed(() => {
  if (!props.series.length) return 0
  return Math.max(1, (width - padding * 2) / props.series.length - 1)
})

const bars = computed(() => {
  const n = props.series.length
  if (!n || maxCount.value <= 0) return []
  const usableW = width - padding * 2
  const slot = usableW / n
  const usableH = height - padding * 2
  return props.series.map((d, i) => {
    const h = (d.count / maxCount.value) * usableH
    return {
      x: padding + i * slot,
      y: height - padding - h,
      h: Math.max(0, h)
    }
  })
})

const formatDay = (iso: string) => {
  const date = new Date(`${iso}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' })
}

const firstLabel = computed(() => (props.series.length ? formatDay(props.series[0]!.date) : ''))
const lastLabel = computed(() => (props.series.length ? formatDay(props.series[props.series.length - 1]!.date) : ''))
const totalLabel = computed(() => `합계 ${total.value}`)
</script>
