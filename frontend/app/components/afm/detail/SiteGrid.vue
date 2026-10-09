<template>
  <AfmCard
    icon="i-lucide-layout-grid"
    title="Site 인덱스 격자"
    :count="grid.cells.length || undefined"
  >
    <!-- Shown whenever there is a block to switch to: a first block without
         Site X/Y must not hide the way to one that has them. -->
    <template
      v-if="grid.cells.length || blockItems.length > 1"
      #actions
    >
      <div class="flex flex-wrap items-center gap-2.5">
        <USelect
          v-if="blockItems.length > 1"
          v-model="block"
          :items="blockItems"
          size="xs"
          class="min-w-44"
          aria-label="블록"
        />
        <USelect
          v-if="grid.cells.length"
          v-model="column"
          :items="columns"
          size="xs"
          class="min-w-44"
          aria-label="측정 항목"
        />
      </div>
    </template>

    <p
      v-if="!grid.cells.length"
      class="flex h-24 items-center justify-center sk-body"
    >
      {{ blockItems.length > 1 ? '이 블록' : '이 측정' }}의 행에는 Site X · Site Y 가 없어 격자를 그릴 수 없습니다.
    </p>
    <template v-else>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
      <p class="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1 sk-meta">
        <span>{{ grid.min === null ? '유효한 값이 없습니다' : `색 범위 ${fmt2(grid.min)} – ${fmt2(grid.max)} · ${column}` }}</span>
        <span
          v-for="mark in MARKS"
          :key="mark.label"
          class="flex items-center gap-1"
        >
          <span :style="{ color: mark.color }">▲</span>{{ mark.label }}
        </span>
        <span class="text-(--sk-ink)">□ 선택한 포인트의 Site</span>
      </p>
      <p class="mt-1 sk-meta">
        Site X · Site Y 인덱스의 배치이며 웨이퍼 형상이 아닙니다. 인덱스는 단위가 없고, Site Y 가 큰 쪽이 위입니다.
        ▲ 는 값으로 칠하지 않은 포인트(색이 없는 칸은 유효한 값이 없는 Site)입니다.
        <template v-if="shared">
          한 Site 에 포인트가 여럿이면 유효한 값의 평균으로 칠하고 칸에 포인트 수를 적습니다.
        </template>
        <template v-if="laps > 1">
          같은 포인트를 {{ laps }}회 측정한 반복 Recipe 이며, 마지막 회차의 값으로 칠합니다.
        </template>
      </p>
    </template>
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import type { SiteCell } from '~/utils/afmSiteGrid'

const props = defineProps<{
  data: AfmDetailRow[]
  summary: AfmSummaryRow[]
  exportName: string
}>()
const selectedPoint = defineModel<string>('selectedPoint', { required: true })

const sk = useChartPalette()

const blocks = computed(() => blockRows(props.data, props.summary))
const blockItems = computed(() => [...blocks.value.keys()])
const block = ref('')
watch(blockItems, (names) => {
  if (!names.includes(block.value)) block.value = names[0] ?? ''
}, { immediate: true })

const columns = computed(() => relationColumns([{ rowsByBlock: blocks.value }], block.value).measured)
const column = ref('')
watch(columns, (names) => {
  if (!names.includes(column.value)) column.value = names[0] ?? ''
}, { immediate: true })

const grid = computed(() => siteGrid(blocks.value.get(block.value) ?? [], column.value))
const shared = computed(() => grid.value.cells.some(cell => cell.points.length > 1))
const laps = computed(() => Math.max(0, ...grid.value.cells.map(cell => cell.laps)))

// A reading that is not a value is marked, never drawn as a low one. The
// colour repeats the state, which the tooltip and the points table spell out.
const MARKS = computed(() => [
  { label: 'FAILED', color: SK_STATE.bad },
  { label: 'STOPPED', color: SK_STATE.warn },
  { label: 'Valid FALSE · 값 없음', color: sk.value.muted }
])
const markColor = (cell: SiteCell) =>
  cell.state === 'FAILED' ? SK_STATE.bad : cell.state === 'STOPPED' ? SK_STATE.warn : sk.value.muted

// Series 0 holds the cells with a value, series 1 the ones with a marked point.
const valued = computed(() => grid.value.cells.filter(cell => cell.value !== null))
const marked = computed(() => grid.value.cells.filter(cell => cell.invalid > 0))
const cellAt = (seriesIndex: number, dataIndex: number) =>
  (seriesIndex === 0 ? valued.value : marked.value)[dataIndex]

const tooltipOf = (cell: SiteCell) => [
  `Site X ${cell.x} · Site Y ${cell.y}`,
  `포인트 ${escapeHtml(cell.points.join(', '))}`,
  `${escapeHtml(column.value)}: ${cell.value === null ? '유효한 값 없음' : fmt2(cell.value)}${cell.valued > 1 ? ` (${cell.valued}개 평균)` : ''}`,
  ...(cell.invalid ? [`값으로 쓰지 않은 포인트 ${cell.invalid}개 · ${escapeHtml(cell.state ?? 'State 없음')}`] : []),
  ...(cell.laps > 1 ? [`${cell.laps}회차 중 마지막 회차`] : [])
].join('<br/>')

const chartOption = computed<EChartsOption>(() => {
  const { xs, ys, min, max } = grid.value
  const at = (cell: SiteCell) => [cell.x - xs[0]!, cell.y - ys[0]!]
  const ring = (cell: SiteCell) => cell.points.includes(selectedPoint.value)
    ? { borderColor: sk.value.ink, borderWidth: 2 }
    : {}
  // Raw column names, and an index per tick: there is no length to label.
  const axis = (name: string, values: number[], nameGap: number) => ({
    type: 'category' as const,
    data: values.map(String),
    name,
    nameLocation: 'middle' as const,
    nameGap,
    nameTextStyle: CHART_LEGEND_LABEL,
    axisLabel: CHART_AXIS_LABEL,
    splitLine: { show: true }
  })
  return {
    grid: { left: 64, right: 96, top: 16, bottom: 48 },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const { seriesIndex, dataIndex } = p as { seriesIndex: number, dataIndex: number }
        const cell = cellAt(seriesIndex, dataIndex)
        return cell ? tooltipOf(cell) : ''
      }
    },
    xAxis: axis('Site X', xs, 30),
    yAxis: axis('Site Y', ys, 40),
    visualMap: {
      show: min !== null,
      seriesIndex: 0,
      dimension: 2,
      min: min ?? 0,
      max: max ?? 1,
      // The two ends of the scale, printed: the bar alone carries no number.
      text: [fmt2(max), fmt2(min)],
      orient: 'vertical',
      right: 4,
      top: 'center',
      inRange: { color: [...SK_SCALE] },
      textStyle: CHART_LEGEND_LABEL
    },
    series: [
      {
        type: 'heatmap',
        animation: false,
        emphasis: { disabled: true },
        // The number in a cell is how many points share the Site, never the value.
        label: {
          show: true,
          color: sk.value.ink,
          ...CHART_AXIS_LABEL,
          formatter: (p: unknown) => {
            const count = valued.value[(p as { dataIndex: number }).dataIndex]?.points.length ?? 0
            return count > 1 ? String(count) : ''
          }
        },
        data: valued.value.map(cell => ({
          value: [...at(cell), cell.value!],
          itemStyle: ring(cell)
        }))
      },
      {
        type: 'scatter',
        animation: false,
        symbol: 'triangle',
        emphasis: { disabled: true },
        data: marked.value.map(cell => ({
          value: at(cell),
          // Small on a coloured cell, where it marks only some of the Site's points.
          symbolSize: cell.value === null ? 14 : 8,
          itemStyle: { color: markColor(cell), ...(cell.value === null ? ring(cell) : {}) }
        }))
      }
    ]
  }
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, {
  exportName: props.exportName,
  // A click picks the Site's next point, so every point of a shared Site is reachable.
  onDataIndex: (dataIndex, seriesIndex) => {
    const points = cellAt(seriesIndex, dataIndex)?.points
    if (points) selectedPoint.value = points[(points.indexOf(selectedPoint.value) + 1) % points.length]!
  }
})
</script>
