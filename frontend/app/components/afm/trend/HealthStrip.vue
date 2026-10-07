<template>
  <AfmCard
    icon="i-lucide-heart-pulse"
    title="측정별 상태 지표"
  >
    <template #actions>
      <span class="sk-meta">{{ hint ?? '포인트별 data 행과 측정 정보의 Tip 값에서 집계 · 블록·항목 선택과 무관 · x축은 01 추세와 같은 시각 · 세로선은 팁이 바뀐 시점(ID·카세트·포트·슬롯 변화, 또는 Mileage 감소 + Pick Up 갱신)' }}</span>
    </template>
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-5">
      <AfmTrendHealthChart
        v-for="c in charts"
        :key="c.label"
        v-bind="c"
        :selected="selected"
        :export-name="`${exportName}-${c.slug}`"
        @select="emit('select', $event)"
      />
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import { tipChanges, type HealthPoint } from '~/utils/afmTrend'
import { SK_SCALE, SK_STATE } from '~/utils/chartPalette'

const props = defineProps<{
  health: HealthPoint[]
  selected: string | null
  exportName: string
  // What the strip was built from, where that is not 시계열 비교's group.
  hint?: string
  // Limits to shade on a chart, by the HealthPoint field it draws.
  bands?: Partial<Record<'notCompleted' | 'invalid' | 'approach' | 'mileage' | 'tipWidth', [number, number]>>
}>()
const emit = defineEmits<{ select: [key: string] }>()

const series = (pick: (h: HealthPoint) => number | null) =>
  props.health.map(h => ({ key: h.key, time: h.time, value: pick(h) }))

const sum = (values: (number | null)[]) => values.reduce<number>((a, v) => a + (v ?? 0), 0)

const charts = computed(() => {
  const approaches = props.health.flatMap(h => h.approach ?? [])
  const lastMileage = props.health.findLast(h => h.mileage !== null)?.mileage ?? null
  const marks = tipChanges(props.health)
  const tipCount = new Set(props.health.flatMap(h => h.tip ?? [])).size
  const lastTip = props.health.findLast(h => h.tip !== null)?.tip ?? null
  // The office stores 'NaN' for a width the measurement did not record.
  const noWidth = props.health.filter(h => h.tip !== null && h.tipWidth === null).length
  return [
    {
      slug: 'not-completed',
      label: 'FAILED + STOPPED 포인트',
      summary: `${sum(props.health.map(h => h.notCompleted))}건`,
      note: '0이 정상. 한 측정에 몰리면 그 측정만, 꾸준히 늘면 팁.',
      kind: 'bar' as const,
      color: SK_STATE.bad,
      points: series(h => h.notCompleted),
      band: props.bands?.notCompleted
    },
    {
      slug: 'invalid',
      label: 'Valid = FALSE 포인트',
      summary: `${sum(props.health.map(h => h.invalid))}건`,
      note: '완료됐지만 recipe 기준을 못 넘긴 포인트.',
      kind: 'bar' as const,
      color: SK_STATE.warn,
      points: series(h => h.invalid),
      band: props.bands?.invalid
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
    }
  ]
})
</script>
