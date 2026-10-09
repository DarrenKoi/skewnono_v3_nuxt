<template>
  <AfmCard
    icon="i-lucide-scatter-chart"
    title="항목 × 항목"
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-2.5">
        <label class="flex items-center gap-1.5">
          <span class="sk-label">X</span>
          <USelect
            v-model="x"
            :items="xItems"
            size="xs"
            class="min-w-44"
            aria-label="X 항목"
          />
        </label>
        <label class="flex items-center gap-1.5">
          <span class="sk-label">Y</span>
          <USelect
            v-model="y"
            :items="columns.measured"
            size="xs"
            class="min-w-44"
            aria-label="Y 항목"
          />
        </label>
      </div>
    </template>

    <p
      v-if="summary.n < RELATION_MIN_SAMPLES"
      class="flex h-80 items-center justify-center sk-body"
    >
      {{ x && y ? `두 값이 모두 있는 행이 ${summary.n}개입니다. ${RELATION_MIN_SAMPLES}개부터 그립니다.` : '이 블록에는 짝지을 숫자 항목이 없습니다.' }}
    </p>
    <div
      v-else
      ref="chartEl"
      class="h-80 w-full"
    />
    <p class="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1 sk-meta">
      <span>{{ block }}{{ recipe ? ` · ${recipe}만` : '' }} · n {{ summary.n }}</span>
      <template v-if="summary.n >= RELATION_MIN_SAMPLES">
        <span>{{ summary.r === null ? 'r 계산 불가 (한 축의 값이 모두 같습니다)' : `r ${summary.r.toFixed(2)}` }}</span>
      </template>
      <span>● 다른 측정</span>
      <span class="text-(--sk-ink)">● 선택한 측정</span>
      <span>제외 {{ relation.excluded }}행 (COMPLETED가 아니거나 Valid FALSE)</span>
      <span v-if="relation.unpaired">값 없음 {{ relation.unpaired }}행</span>
      <span v-if="relation.unknownValid">Valid 미상 {{ relation.unknownValid }}행 포함</span>
    </p>
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { RELATION_MIN_SAMPLES } from '~/utils/afmRelation'
import type { TrendEntry } from '~/utils/afmTrend'

const props = defineProps<{
  // One recipe's measurements: a mixed group is narrowed before it gets here.
  entries: TrendEntry[]
  block: string
  // The page's 측정 항목: what Y starts on and follows.
  column: string
  // Set in a mixed group: the one recipe whose rows are paired.
  recipe?: string
  selected: string | null
  exportName: string
}>()
const emit = defineEmits<{ select: [key: string] }>()

const sk = useChartPalette()

const columns = computed(() => relationColumns(props.entries, props.block))
const xItems = computed(() => [...columns.value.measured, ...columns.value.usage])
const x = ref('')
const y = ref('')
// Y follows the page's 측정 항목 only when THAT changes. The column list is
// rebuilt on every group or baseline change, and resetting Y then would throw
// away a pick that is still valid — so a list change replaces Y only when the
// pick is gone.
const pageY = () => {
  const { measured } = columns.value
  return measured.includes(props.column) ? props.column : measured[0] ?? ''
}
watch(() => props.column, () => {
  y.value = pageY()
}, { immediate: true })
watch(columns, ({ measured }) => {
  if (!measured.includes(y.value)) y.value = pageY()
})
// X starts on another column than Y; a pick that still exists is kept.
watch([xItems, y], () => {
  if (!xItems.value.includes(x.value)) x.value = xItems.value.find(c => c !== y.value) ?? ''
}, { immediate: true })

const relation = computed(() => relationSamples(props.entries, props.block, x.value, y.value))
const summary = computed(() => relationSummary(relation.value.samples))
// The selected measurement's samples last, so they are drawn over the rest.
const drawn = computed(() => {
  const { samples } = relation.value
  return [...samples.filter(s => s.key !== props.selected), ...samples.filter(s => s.key === props.selected)]
})
const entryOf = computed(() => new Map(props.entries.map(entry => [entry.key, entry])))

const chartOption = computed<EChartsOption>(() => {
  const axis = (name: string) => ({
    type: 'value' as const,
    scale: true,
    name,
    nameLocation: 'middle' as const,
    nameTextStyle: CHART_LEGEND_LABEL,
    axisLabel: CHART_AXIS_LABEL
  })
  return {
    grid: { left: 72, right: 24, top: 16, bottom: 48 },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const sample = drawn.value[(p as { dataIndex: number }).dataIndex]
        const entry = sample && entryOf.value.get(sample.key)
        if (!sample || !entry) return ''
        return [
          `<b>${escapeHtml(`${entry.lot}·${entry.slot}`)}</b> ${shortTime(entry.time)}`,
          `포인트 ${escapeHtml(sample.point)}`,
          `${escapeHtml(x.value)}: ${fmt2(sample.x)}`,
          `${escapeHtml(y.value)}: ${fmt2(sample.y)}`
        ].join('<br/>')
      }
    },
    // Raw column names: Mileage's unit is not confirmed, so none is added.
    xAxis: { ...axis(x.value), nameGap: 30 },
    yAxis: { ...axis(y.value), nameGap: 52 },
    series: [{
      type: 'scatter',
      symbolSize: 7,
      emphasis: { focus: 'none' },
      data: drawn.value.map((s) => {
        const on = s.key === props.selected
        return { value: [s.x, s.y], itemStyle: { color: on ? sk.value.ink : sk.value.muted, opacity: on ? 1 : 0.55 } }
      })
    }]
  }
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, {
  exportName: props.exportName,
  onDataIndex: (dataIndex) => {
    const key = drawn.value[dataIndex]?.key
    if (key) emit('select', key)
  }
})
</script>
