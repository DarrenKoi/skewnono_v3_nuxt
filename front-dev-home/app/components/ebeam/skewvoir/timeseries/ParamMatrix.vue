<template>
  <div
    ref="chartEl"
    role="img"
    tabindex="0"
    class="w-full"
    :style="{ height: `${height}px` }"
    :aria-label="ariaLabel"
  />
  <span class="sr-only">{{ ariaLabel }}</span>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MatrixCell, ParamMatrixModel } from '~/utils/skewvoirAnalysis/paramMatrix'

// The FDC sparkline matrix: one mini line chart per param, laid out by the
// ECharts 6 `matrix` coordinate system. Each cell is a full cartesian grid with
// its OWN scaled y-axis, so every param keeps its native unit — the reason this
// exists rather than reusing the σ-normalised multi-MSR trend chart.
//
// Presentational only. Row composition, ordering, suspects and the column cap
// are all decided in utils/skewvoirAnalysis/paramMatrix.ts.
//
// DELIBERATELY not focus-aware. useEchart rebuilds with `notMerge` on any option
// change and hands back no chart instance, so taking the focused sequence as a
// prop would tear down every grid/axis/series on each cursor move (measured
// 19.4 ms at 40 params, 38.6 ms at 80 — past a frame). The option is a function
// of the model alone; the hover crosshair still spans cells via
// axisPointer.link, and the detail panes below carry the persisted cursor.
const props = defineProps<{
  model: ParamMatrixModel
}>()

const emit = defineEmits<{ select: [sequence: number], drill: [param: string] }>()

const ROW_HEIGHT = 86
const HEADER = 22
const ZOOM = 44

const height = computed(() => HEADER + props.model.rows.length * ROW_HEIGHT + ZOOM)

const categories = computed(() => props.model.sequences.map(String))

// Column keys are deliberately NOT numeric strings. A matrix coord value can be
// either an ordinal raw value or an ordinal index, so '1' would be ambiguous.
const colKey = (i: number): string => `c${i + 1}`
const colKeys = computed(() => Array.from({ length: props.model.columns }, (_, i) => colKey(i)))

const sk = useChartPalette()
const { palette } = useEchartsTheme()

// Distinct accent per row so neighbouring cells never read as one series. Index
// 0 is reserved for CD, matching the CD pane below the matrix.
const colorFor = (rowIdx: number, kind: string): string => {
  if (kind === 'cd') return sk.value.series
  if (palette.value.length < 2) return sk.value.series
  return palette.value[1 + (rowIdx % (palette.value.length - 1))]!
}

const rBadge = (cell: MatrixCell): string => {
  if (cell.category === 'cd') return 'ref'
  if (cell.readiness !== 'ready' || cell.r == null) return '평가 불가'
  return `r ${cell.r >= 0 ? '+' : '−'}${Math.abs(cell.r).toFixed(2)}`
}

// Flat cell list in the SAME order grids/axes/series are pushed below, so both
// `gridIndex` from a grid click and `seriesIndex` from a tooltip index into it.
const cellByIndex = computed<MatrixCell[]>(() => props.model.rows.flatMap(r => r.cells))

const option = computed<EChartsOption>(() => {
  const grids: Record<string, unknown>[] = []
  const xAxis: Record<string, unknown>[] = []
  const yAxis: Record<string, unknown>[] = []
  const series: Record<string, unknown>[] = []

  const cols = props.model.columns

  props.model.rows.forEach((row, rowIdx) => {
    row.cells.forEach((cell, colIdx) => {
      const id = `${rowIdx}|${colIdx}`
      const color = colorFor(rowIdx, row.kind)

      grids.push({
        id,
        coordinateSystem: 'matrix',
        // The CD row spans every column; all other cells occupy one. Grid range
        // coords resolve through Matrix.dataToLayout → parseCoordRangeOption.
        coord: row.kind === 'cd' ? [[colKey(0), colKey(cols - 1)], row.label] : [colKey(colIdx), row.label],
        left: 4,
        right: 4,
        // Room above the plot for the per-cell param label (yAxis.name below).
        top: 26,
        bottom: 5,
        containLabel: true
      })

      xAxis.push({
        id,
        gridId: id,
        type: 'category',
        data: categories.value,
        boundaryGap: false,
        axisTick: { show: false },
        axisLabel: { show: false },
        axisLine: { show: false },
        splitLine: { show: false }
      })

      yAxis.push({
        id,
        gridId: id,
        type: 'value',
        scale: true,
        // The cell's own caption. Row headers only say which CATEGORY you are
        // looking at, so without this you cannot tell StigmaX from StigmaY —
        // which would defeat the ranking entirely.
        name: `${cell.param}  ${rBadge(cell)}`,
        nameLocation: 'end',
        nameGap: 9,
        nameTextStyle: {
          fontSize: 9,
          align: 'left',
          color: cell.readiness === 'ready' ? undefined : '#f59e0b'
        },
        // One label only — the max. A tiny cell cannot carry a full scale.
        interval: Number.MAX_SAFE_INTEGER,
        axisLabel: { showMaxLabel: true, fontSize: 8, opacity: 0.55 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      })

      // Nominal only. A focus marker here would make the option focus-dependent.
      const marks = cell.nominal == null
        ? []
        : [{ yAxis: cell.nominal, lineStyle: { color: '#94a3b8', type: 'dashed', opacity: 0.5 } }]

      series.push({
        id,
        name: `${cell.param} · ${rBadge(cell)}`,
        xAxisId: id,
        yAxisId: id,
        type: 'line',
        symbol: 'none',
        // Gaps must read as gaps, never as interpolated measurements.
        connectNulls: false,
        lineStyle: { width: 1.15, color },
        itemStyle: { color },
        data: cell.values,
        markLine: marks.length
          ? { silent: true, symbol: 'none', label: { show: false }, data: marks }
          : undefined
      })
    })
  })

  return {
    matrix: {
      x: {
        data: colKeys.value,
        levelSize: 2,
        // The column position carries no meaning of its own — the param name
        // lives in each cell's series name, so a header here would be noise.
        label: { show: false }
      },
      y: {
        // Labels are unique by construction in paramMatrix.ts, which is what
        // lets them double as the ordinal coord values used above.
        data: props.model.rows.map(r => ({ value: r.label })),
        levelSize: 88,
        label: { fontSize: 10 }
      },
      corner: { data: [{ coord: [-1, -1], value: 'param' }], label: { fontSize: 9 } },
      left: 6,
      right: 6,
      top: HEADER,
      bottom: ZOOM
    },
    tooltip: {
      trigger: 'axis',
      // axisPointer.link makes every cell's axis fire together, so one hover
      // reports the whole matrix at that sequence — the cross-param readout
      // this view exists for. Confine it so the tall list cannot escape the
      // chart box.
      confine: true,
      textStyle: { fontSize: 11 },
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params]
        const first = list[0] as { dataIndex: number } | undefined
        if (!first) return ''
        const seq = props.model.sequences[first.dataIndex]
        const lines = [`<b>sequence ${seq ?? '—'}</b>`]
        for (const item of list as { seriesIndex: number, value: number | null }[]) {
          const cell = cellByIndex.value[item.seriesIndex]
          // The suspects row holds COPIES of cells from the category rows, so
          // without this every suspect would be listed twice in one tooltip.
          if (!cell || cell.duplicated) continue
          const v = item.value == null ? '결측' : item.value
          lines.push(`${cell.param}: <b>${v}</b> ${cell.unit}`)
        }
        return lines.join('<br/>')
      }
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [
      { type: 'inside', xAxisIndex: 'all', throttle: 120 },
      { type: 'slider', xAxisIndex: 'all', bottom: 8, height: 18, throttle: 120 }
    ],
    grid: grids,
    xAxis,
    yAxis,
    series
  } as EChartsOption
})

// Screen-reader alternative: what the grid is and where the ranking points.
const ariaLabel = computed(() => {
  const n = cellByIndex.value.length
  const suspects = props.model.rows.find(r => r.kind === 'suspects')
  const top = suspects?.cells.map(c => c.param).join(', ')
  return `FDC 파라미터 매트릭스: ${n}개 셀, ${props.model.sequences.length}개 측정 순서`
    + (top ? `. 주요 용의자: ${top}` : '')
})

const chartEl = ref<HTMLDivElement | null>(null)

useEchart(chartEl, option, {
  exportName: 'fdc-param-matrix',
  // One gesture, two effects: move the shared cursor (what every other pane's
  // click does) and open the clicked param's full-size pane.
  onGridClick: (xValue, gridIndex) => {
    const seq = props.model.sequences[Math.round(xValue)]
    if (seq != null) emit('select', seq)
    const cell = cellByIndex.value[gridIndex]
    if (cell && cell.category !== 'cd') emit('drill', cell.param)
  }
})
</script>
