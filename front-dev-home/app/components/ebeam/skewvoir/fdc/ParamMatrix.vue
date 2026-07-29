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
import type {
  EChartsOption,
  GridComponentOption,
  LineSeriesOption,
  XAXisComponentOption,
  YAXisComponentOption
} from 'echarts'
import type { MatrixCell, MatrixRow, ParamMatrixModel } from '~/utils/skewvoirAnalysis/paramMatrix'
import { SK_STATE } from '~/utils/chartPalette'

// The FDC sparkline matrix: one mini line chart per param, laid out by the
// ECharts 6 `matrix` coordinate system. Each cell is a full cartesian grid with
// its OWN scaled y-axis, so every param keeps its native unit — the reason this
// exists rather than reusing the σ-normalised multi-MSR trend chart.
//
// Presentational only. Row composition, ordering, the 검토 근거 ranking, the
// column cap and each cell's relation verdict are all decided in
// utils/skewvoirAnalysis/paramMatrix.ts.
//
// DELIBERATELY not focus-aware. useEchart rebuilds with `notMerge` on any option
// change and hands back no chart instance, so taking the focused sequence as a
// prop would tear down every grid/axis/series on each cursor move (measured
// 19.4 ms at 40 params, 38.6 ms at 80 — past a frame). The option is a function
// of the model alone; the hover crosshair still spans cells via
// axisPointer.link, and the detail panes below carry the persisted cursor.
const props = defineProps<{
  model: ParamMatrixModel
  /** param name → colour, assigned ONCE by the parent and shared with the detail
   * panes. Passed in rather than derived here because two independent
   * assignments drift the moment their input ordering differs, and then the cell
   * you click and the pane you land on disagree. */
  colors: Record<string, string>
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

interface FlatCell { cell: MatrixCell, row: MatrixRow, rowIdx: number, colIdx: number }

// ONE traversal drives both the option builder and the click/tooltip lookups, so
// `gridIndex` and `seriesIndex` correspond to a cell structurally rather than by
// two loops agreeing to stay in step.
const flatCells = computed<FlatCell[]>(() =>
  props.model.rows.flatMap((row, rowIdx) =>
    row.cells.map((cell, colIdx) => ({ cell, row, rowIdx, colIdx }))
  )
)

const sk = useChartPalette()

// The CD reference keeps palette[0] (sk.series); every FDC param takes the
// colour its detail pane already uses.
const colorFor = (cell: MatrixCell): string =>
  cell.category === 'cd' ? sk.value.series : (props.colors[cell.param] ?? sk.value.series)

// The verdict itself comes from the model; only the glyphs are chosen here.
const rBadge = (cell: MatrixCell): string => {
  if (cell.rState === 'reference') return 'ref'
  if (cell.rState === 'unavailable') return '평가 불가'
  const r = cell.r ?? 0
  return `r ${r >= 0 ? '+' : '−'}${Math.abs(r).toFixed(2)}`
}

const option = computed<EChartsOption>(() => {
  const grids: GridComponentOption[] = []
  const xAxis: XAXisComponentOption[] = []
  const yAxis: YAXisComponentOption[] = []
  const series: LineSeriesOption[] = []

  for (const { cell, row, rowIdx, colIdx } of flatCells.value) {
    const id = `${rowIdx}|${colIdx}`
    const color = colorFor(cell)

    grids.push({
      id,
      coordinateSystem: 'matrix',
      // Every cell occupies one matrix column. The model guarantees that the CD row
      // has exactly one cell at colIdx 0, so CD keeps the same width as each FDC cell.
      coord: [colKey(colIdx), row.label],
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
      // which would defeat the ranking.
      name: `${cell.param} (${cell.unit})  ${rBadge(cell)}`,
      nameLocation: 'end',
      nameGap: 9,
      nameTruncate: {
        maxWidth: 112,
        ellipsis: '…'
      },
      nameTextStyle: {
        fontSize: 9,
        align: 'left',
        color: cell.rState === 'unavailable' ? SK_STATE.warn : undefined
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
      : [{
          yAxis: cell.nominal,
          lineStyle: { color: sk.value.muted, type: 'dashed' as const, opacity: 0.7 }
        }]

    series.push({
      id,
      name: cell.param,
      xAxisId: id,
      yAxisId: id,
      type: 'line',
      // The CD reference row alone gets a visible marker. Under the 'all'
      // sequence axis, the active parameter occupies only alternating
      // sequences, so with connectNulls:false and symbol:'none' no two
      // adjacent CD points are ever both non-null and the line draws
      // nothing at all — an isolated point needs its own mark to be seen,
      // or "gapped" reads as "absent". FDC cells stay symbol:'none': they
      // are dense, and per-point marks there would just add visual noise.
      ...(row.kind === 'cd' ? { symbol: 'circle', symbolSize: 2 } : { symbol: 'none' }),
      // Gaps must read as gaps, never as interpolated measurements.
      connectNulls: false,
      lineStyle: { width: 1.15, color },
      itemStyle: { color },
      data: cell.values,
      markLine: marks.length
        ? { silent: true, symbol: 'none', label: { show: false }, data: marks }
        : undefined
    })
  }

  return {
    matrix: {
      x: {
        data: colKeys.value,
        levelSize: 2,
        // The column position carries no meaning of its own — the param name
        // lives in each cell's caption, so a header here would be noise.
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
          const cell = flatCells.value[item.seriesIndex]?.cell
          // The 검토 근거 row holds COPIES of cells from the category rows, so
          // without this every suspect would be listed twice in one tooltip.
          if (!cell || cell.duplicated) continue
          const v = item.value == null ? '결측' : item.value
          // The reason `assess()` produced is the honest distinction between
          // "no pairs", "too few" and "constant" — surface it rather than
          // flattening all three into the caption's 평가 불가.
          const why = cell.reason ? ` <span style="opacity:.65">${cell.reason}</span>` : ''
          lines.push(`${cell.param}: <b>${v}</b> ${cell.unit}${why}`)
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
  }
})

// Screen-reader alternative: what the grid is and where the ranking points.
const ariaLabel = computed(() => {
  const n = flatCells.value.length
  const evidence = props.model.rows.find(r => r.kind === 'evidence')
  const top = evidence?.cells.map(c => c.param).join(', ')
  return `FDC 파라미터 매트릭스: ${n}개 셀, ${props.model.sequences.length}개 측정 순서`
    + (top ? `. 주요 검토 근거: ${top}` : '')
})

const chartEl = ref<HTMLDivElement | null>(null)

useEchart(chartEl, option, {
  exportName: 'fdc-param-matrix',
  // One gesture, two effects: move the shared cursor (what every other pane's
  // click does) and open the clicked param's full-size pane.
  onGridClick: (xValue, gridIndex) => {
    const seq = props.model.sequences[Math.round(xValue)]
    if (seq != null) emit('select', seq)
    const cell = flatCells.value[gridIndex]?.cell
    if (cell && cell.category !== 'cd') emit('drill', cell.param)
  }
})
</script>
