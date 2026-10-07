<template>
  <AfmCard
    icon="i-lucide-heart-pulse"
    title="측정별 상태 지표"
  >
    <template #actions>
      <span class="sk-meta">{{ hint ?? '포인트별 data 행과 측정 정보의 Tip 값에서 집계 · 블록·항목 선택과 무관 · x축은 01 추세와 같은 시각 · 세로선은 팁이 바뀐 시점(ID·카세트·포트·슬롯 변화, 또는 Mileage 감소 + Pick Up 갱신)' }}</span>
    </template>
    <div class="grid grid-cols-1 gap-x-6 gap-y-5 md:grid-cols-2">
      <AfmTrendHealthChart
        v-for="c in charts"
        :key="c.label"
        v-bind="c"
        :range="range"
        :selected="selected"
        :export-name="`${exportName}-${c.slug}`"
        @select="emit('select', $event)"
      />
    </div>
    <div
      v-if="extent"
      class="mt-4 flex items-center gap-3 border-t border-(--sk-border-soft) pt-3"
    >
      <span class="sk-label whitespace-nowrap">구간</span>
      <span class="sk-value-num whitespace-nowrap text-(--sk-ink-muted)">{{ shortTime(shown[0]) }}</span>
      <USlider
        v-model="zoom"
        :min="0"
        :max="100"
        :step="1"
        :min-steps-between-thumbs="1"
        size="sm"
        color="neutral"
        aria-label="차트 4개의 시간 구간"
        class="flex-1"
      />
      <span class="sk-value-num whitespace-nowrap text-(--sk-ink-muted)">{{ shortTime(shown[1]) }}</span>
      <UButton
        size="xs"
        color="neutral"
        variant="ghost"
        icon="i-lucide-rotate-ccw"
        label="전체"
        :disabled="!range"
        @click="zoom = [0, 100]"
      />
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import { shortTime, tipChanges, type HealthPoint } from '~/utils/afmTrend'
import { SK_SCALE, SK_STATE } from '~/utils/chartPalette'

const props = defineProps<{
  health: HealthPoint[]
  selected: string | null
  exportName: string
  // What the strip was built from, where that is not 시계열 비교's group.
  hint?: string
  // Limits to shade on a chart, by the HealthPoint field it draws.
  bands?: Partial<Record<'notCompleted' | 'approach' | 'mileage' | 'tipWidth', [number, number]>>
}>()
const emit = defineEmits<{ select: [key: string] }>()

// One window for all four charts, as % of the strip's own time span.
const zoom = ref([0, 100])
// Null when there is no span to zoom into (no measurement, or a single time).
const extent = computed(() => {
  const times = props.health.map(h => h.time)
  const [from, to] = [Math.min(...times), Math.max(...times)]
  return to > from ? [from, to] as const : null
})
// Keyed on the span, not on `health`: 팁 모니터링 hands in a fresh array on every
// render, and a click on a point must not throw the window away.
watch(() => extent.value?.join(), () => {
  zoom.value = [0, 100]
})
const shown = computed<[number, number]>(() => {
  const [from, to] = extent.value ?? [0, 0]
  return [from + (to - from) * zoom.value[0]! / 100, from + (to - from) * zoom.value[1]! / 100]
})
const range = computed(() => zoom.value[0]! > 0 || zoom.value[1]! < 100 ? shown.value : undefined)
// Only the window's points reach a chart, so its y axis fits what is on screen.
const visible = computed(() => range.value
  ? props.health.filter(h => h.time >= range.value![0] && h.time <= range.value![1])
  : props.health)

const series = (pick: (h: HealthPoint) => number | null) =>
  visible.value.map(h => ({ key: h.key, time: h.time, value: pick(h) }))

const charts = computed(() => {
  const approaches = props.health.flatMap(h => h.approach ?? [])
  const lastMileage = props.health.findLast(h => h.mileage !== null)?.mileage ?? null
  const marks = tipChanges(props.health)
  const tipCount = new Set(props.health.flatMap(h => h.tip ?? [])).size
  const lastTip = props.health.findLast(h => h.tip !== null)?.tip ?? null
  // The office stores 'NaN' for a width the measurement did not record.
  const noWidth = props.health.filter(h => h.tip !== null && h.tipWidth === null).length
  // Most telling first: the grid reads left to right, top to bottom.
  return [
    {
      slug: 'tip-width',
      label: 'Tip Width',
      summary: lastTip === null ? '–' : `팁 ${tipCount}개${noWidth ? ` · 측정 없음 ${noWidth}건` : ''}`,
      note: lastTip === null
        ? '측정 정보에 Tip 값이 없습니다.'
        : `지금 ${lastTip} (ID · 카세트/포트/슬롯). 폭은 측정 시점의 기록값.`,
      kind: 'line' as const,
      color: SK_SCALE[1],
      points: series(h => h.tipWidth),
      band: props.bands?.tipWidth,
      marks
    },
    {
      slug: 'mileage',
      label: 'Mileage 평균',
      summary: lastMileage === null ? '–' : `${lastMileage.toFixed(1)} 마지막`,
      note: '팁 하나의 누적값이라 단조 증가가 정상. 세로선 = 팁이 바뀐 지점(Tip 값 변화, 또는 Mileage 감소 + Pick Up 갱신).',
      kind: 'line' as const,
      color: SK_STATE.ok,
      points: series(h => h.mileage),
      band: props.bands?.mileage,
      marks
    },
    {
      slug: 'approach',
      label: 'Approach Count 평균',
      summary: approaches.length ? `${fmt2(approaches.reduce((a, b) => a + b, 0) / approaches.length)}회` : '–',
      note: '재접근이 늘면 표면·팁 상태 의심.',
      kind: 'line' as const,
      color: SK_SCALE[0],
      points: series(h => h.approach),
      band: props.bands?.approach
    },
    {
      slug: 'not-completed',
      label: 'FAILED + STOPPED 포인트',
      summary: `${props.health.reduce((a, h) => a + h.notCompleted, 0)}건`,
      note: '0이 정상. 한 측정에 몰리면 그 측정만, 꾸준히 늘면 팁.',
      kind: 'bar' as const,
      color: SK_STATE.bad,
      points: series(h => h.notCompleted),
      band: props.bands?.notCompleted
    }
  ]
})
</script>
