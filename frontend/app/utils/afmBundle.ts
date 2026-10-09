// AFM 이상 측정 조사 묶음 — the suspects of a 시계열 비교 group, the reference
// they were judged against and their per-point evidence, as one file that can
// be attached to a report.
//
// It records what the screen already marks; it adds no detection rule, no
// threshold and no verdict. The band is a reference range computed from
// measurements the user chose — never a control or spec limit.
//
// REUSE, do not re-derive: every number comes from the function that owns it
// on screen (trendRows, healthSeries, durationRows, pointMatrix).
//
// Two steps: `buildBundle` returns plain data, `bundleSheets` lays it out as
// rows. Writing the .xlsx is utils/xlsx.ts's job. Runs under `node --test`.
import { durationRows } from './afmDuration.ts'
import { tipWidthOf } from './afmInfo.ts'
import { comparePoints } from './afmPoints.ts'
import { summaryNumber } from './afmSummary.ts'
import { healthSeries, isValidRow, pointMatrix, pointScope, trendBandName, type RecipeCentre, type TrendRow, type TrendStat } from './afmTrend.ts'
import { formatDateTimeLocal } from './dateTime.ts'
import { toSheetRows } from './tableExport.ts'
import type { WorkbookSheet } from './xlsx.ts'

export interface BundleSuspect {
  row: TrendRow
  // `TrendRow.out`: a target outside its recipe's band.
  out: boolean
  // The page's `FAILED · STOPPED` KPI count: data rows not COMPLETED, every block.
  notCompleted: number
}

// Exactly what the screen marks: the trend's red dot, or the KPI's count.
export const bundleSuspects = (rows: TrendRow[]): BundleSuspect[] => {
  const health = healthSeries(rows.map(row => row.entry))
  return rows.flatMap((row, i) => {
    const notCompleted = health[i]!.notCompleted
    return row.out || notCompleted > 0 ? [{ row, out: row.out, notCompleted }] : []
  })
}

export const BUNDLE_CAUTION
  = '수치는 생성 시각 기준입니다. 기준 범위는 사용자가 고른 측정에서 계산한 참고 범위이며 관리 한계나 규격이 아닙니다. 대상은 이 장비의 목록에 있는 최근 3개월의 측정입니다.'

export interface BundleInput {
  generatedAt: Date
  tool: string
  block: string
  column: string
  stat: TrendStat
  // `trendRows` output, as the page holds it.
  rows: TrendRow[]
  centres: Map<string, RecipeCentre>
  showLimits: boolean
  // Grouped measurements whose detail did not load: they are in no sheet.
  notLoaded?: number
  // 02 포인트별 비교's 제외 choice: the per-point reference is then the mean of
  // valid rows only, as on screen. The suspect's own rows are listed either way.
  pointsValidOnly?: boolean
  memo: string
}

export interface BundleRecipe {
  recipe: string
  // Values μ and the band were computed from.
  n: number
  mu: number | null
  low: number | null
  high: number | null
  // Why there is no band; '' when there is one.
  reason: string
}

export interface BundleMeasurement {
  key: string
  lot: string
  slot: string
  recipe: string
  // As the page's own export writes it; '' when the time never parsed.
  time: string
  // '' when nothing is pinned: there is no baseline to be a target of.
  role: '기준' | '대상' | ''
  value: number | null
  delta: number | null
  out: boolean
  // Data rows of every block, by State; `invalid` is every row `isValidRow` rejects.
  failed: number
  stopped: number
  invalid: number
  tipId: string
  tipCassette: string
  tipPort: string
  tipSlot: string
  tipWidth: number | null
  // The measurement's row means, as 장비 건강 draws them.
  mileage: number | null
  approach: number | null
  seconds: number | null
  perPoint: number | null
  // Why it is a suspect; '' when it is not.
  suspect: string
}

// One data row of a suspect, in the picked block.
export interface BundlePoint {
  key: string
  lot: string
  slot: string
  recipe: string
  time: string
  point: string
  siteX: number | string | null
  siteY: number | string | null
  state: string
  // '' where the row states no Valid.
  valid: 'TRUE' | 'FALSE' | ''
  value: number | null
  // 포인트별 비교's default reference (기준 = 그룹 평균): the mean of the point
  // over the group's measurements of the same recipe.
  reference: number | null
  delta: number | null
}

export interface AfmBundle {
  // Whether the per-point reference left out FAILED · Valid FALSE rows.
  pointsValidOnly: boolean
  // `YYYY-MM-DD HH:mm`, the viewer's clock — the page's own time format.
  generatedAt: string
  tool: string
  block: string
  column: string
  stat: TrendStat
  bandName: string
  bandSource: string
  showLimits: boolean
  recipes: BundleRecipe[]
  total: number
  notLoaded: number
  suspectCount: number
  memo: string
  measurements: BundleMeasurement[]
  points: BundlePoint[]
}

export const buildBundle = (input: BundleInput): AfmBundle => {
  const { rows, centres } = input
  const pinnedCount = rows.filter(row => row.role === 'baseline').length
  const pinned = pinnedCount > 0
  const bandName = trendBandName(pinned)
  const suspects = new Map(bundleSuspects(rows).map(s => [s.row.entry.key, s]))
  const health = healthSeries(rows.map(row => row.entry))
  const durations = durationRows(rows.map(row => row.entry))
  const info = (row: TrendRow, key: string) => String(row.entry.payload.information[key] ?? '').trim()
  const measurements = rows.map((row, i): BundleMeasurement => {
    const { entry } = row
    const data = entry.payload.data
    const suspect = suspects.get(entry.key)
    const duration = durations[i]!
    return {
      key: entry.key,
      lot: entry.lot,
      slot: entry.slot,
      recipe: entry.recipe,
      time: Number.isFinite(entry.time) ? formatDateTimeLocal(new Date(entry.time).toISOString()) : '',
      role: !pinned ? '' : row.role === 'baseline' ? '기준' : '대상',
      value: row.value,
      delta: row.delta,
      out: row.out,
      failed: data.filter(r => r.State === 'FAILED').length,
      stopped: data.filter(r => r.State === 'STOPPED').length,
      invalid: data.filter(r => !isValidRow(r)).length,
      tipId: info(row, 'Tip ID'),
      tipCassette: info(row, 'Tip Cassette ID'),
      tipPort: info(row, 'Tip Port No'),
      tipSlot: info(row, 'Tip Slot No'),
      tipWidth: tipWidthOf(entry.payload.information),
      mileage: health[i]!.mileage,
      approach: health[i]!.approach,
      seconds: duration.duration.kind === 'ok' ? duration.duration.seconds : null,
      perPoint: duration.perPoint,
      suspect: [suspect?.out && `${bandName} 밖`, suspect?.notCompleted && 'FAILED·STOPPED 포인트'].filter(Boolean).join(' · ')
    }
  })
  // 02 포인트별 비교's own matrix, one per recipe: point keys belong to a recipe.
  const scoped = pointScope(rows, input.block, input.column, input.pointsValidOnly === true).rows
  const references = new Map([...centres.keys()].map((recipe) => {
    const matrix = pointMatrix(
      scoped.flatMap(row => row.entry.recipe === recipe && row.stats?.points.size ? [{ key: row.entry.key, points: row.stats.points }] : []),
      'mean',
      null
    )
    return [recipe, new Map(matrix.points.map((point, i) => [point, matrix.baseline[i] ?? null]))]
  }))
  const cell = (raw: unknown) => typeof raw === 'number' || typeof raw === 'string' ? raw : null
  const points = measurements.flatMap((m, i): BundlePoint[] => {
    if (!m.suspect) return []
    const blockRows = rows[i]!.entry.rowsByBlock.get(input.block) ?? []
    return [...blockRows].sort((a, b) => comparePoints(a.measurement_point, b.measurement_point)).map((r) => {
      const value = summaryNumber(r[input.column])
      const reference = references.get(m.recipe)?.get(r.measurement_point) ?? null
      return {
        key: m.key,
        lot: m.lot,
        slot: m.slot,
        recipe: m.recipe,
        time: m.time,
        point: r.measurement_point,
        siteX: cell(r['Site X']),
        siteY: cell(r['Site Y']),
        state: r.State,
        valid: r.Valid === true ? 'TRUE' : r.Valid === false ? 'FALSE' : '',
        value,
        reference,
        delta: value !== null && reference !== null ? value - reference : null
      }
    })
  })
  return {
    generatedAt: formatDateTimeLocal(input.generatedAt.toISOString()),
    tool: input.tool,
    block: input.block,
    column: input.column,
    stat: input.stat,
    bandName,
    bandSource: `${pinned ? `기준으로 고정한 측정 ${pinnedCount}건` : `그룹의 측정 ${rows.length}건`}의 평균 ± 3σ`,
    showLimits: input.showLimits,
    recipes: [...centres].map(([recipe, centre]) => ({
      recipe,
      n: rows.filter(row => row.entry.recipe === recipe && row.value !== null && (!pinned || row.role === 'baseline')).length,
      mu: centre.mu,
      low: centre.limits?.lcl ?? null,
      high: centre.limits?.ucl ?? null,
      // The KPI's own words for a band that cannot be drawn.
      reason: centre.limits ? '' : centre.reason || '값 2건 이상부터'
    })),
    total: rows.length,
    notLoaded: input.notLoaded ?? 0,
    suspectCount: suspects.size,
    memo: input.memo.trim(),
    pointsValidOnly: input.pointsValidOnly === true,
    measurements,
    points
  }
}

// 요약 is key/value rows, then one row per recipe: μ and the band are never
// pooled across recipes. A sheet with nothing to say is left out.
export const bundleSheets = (bundle: AfmBundle): WorkbookSheet[] => {
  const mixed = bundle.recipes.length > 1
  const summary: unknown[][] = [
    ['장비', bundle.tool],
    ['생성 시각', bundle.generatedAt],
    ['블록', bundle.block],
    ['측정 항목', bundle.column],
    ['통계', bundle.stat],
    ['기준 범위', bundle.bandName],
    ['기준 범위의 근거', bundle.showLimits ? bundle.bandSource : `${bundle.bandSource} · 기준 범위 꺼짐 — 범위 밖 표시를 하지 않았습니다`],
    ['그룹의 측정', bundle.total],
    ...(bundle.notLoaded ? [['불러오지 못한 측정', `${bundle.notLoaded}건 — 이 파일에 들어 있지 않습니다`]] : []),
    ['조사 대상 측정', bundle.suspectCount],
    ['조사 대상 기준', `화면의 표시 그대로입니다: ${bundle.bandName} 밖의 대상 측정, 또는 FAILED·STOPPED 포인트가 있는 측정`],
    ...(mixed ? [['Recipe 혼합', `recipe ${bundle.recipes.length}종 — μ와 기준 범위는 recipe별로 따로 계산하며 하나로 합치지 않습니다`]] : []),
    ['포인트 기준', `포인트별 비교의 그룹 평균입니다: 같은 recipe의 측정들에서 그 포인트 값의 평균 · ${bundle.pointsValidOnly ? 'FAILED · Valid FALSE 행 제외 (화면의 02 선택과 같음, 반복 포인트는 마지막 유효 값)' : 'FAILED · Valid FALSE 행 포함 (화면의 02 선택과 같음)'}`],
    ['범위 밖 판정', '반올림 전 값으로 판정했습니다. 이 파일의 수치는 소수 4자리로 반올림해 적었으므로, 경계에 있는 값은 적힌 숫자만으로는 범위 안처럼 보일 수 있습니다.'],
    ['유의', BUNDLE_CAUTION],
    ...(bundle.memo ? [['메모', bundle.memo]] : []),
    [],
    ['Recipe', '계산에 쓴 측정 수', 'μ', '범위 하한 (μ − 3σ)', '범위 상한 (μ + 3σ)', '비고'],
    ...bundle.recipes.map(r => [r.recipe, r.n, r.mu, r.low, r.high, r.reason])
  ]
  const sheets: WorkbookSheet[] = [{ name: '요약', rows: toSheetRows(['항목', '값'], summary) }]
  if (bundle.measurements.length) {
    sheets.push({
      name: '측정 목록',
      rows: toSheetRows(
        [
          '조사 대상', 'Lot', 'Slot', 'Recipe', '시각', '역할',
          `${bundle.column} ${bundle.stat}`, 'Δ μ', `${bundle.bandName} 밖`,
          'FAILED 행', 'STOPPED 행', '유효하지 않은 행',
          'Tip ID', 'Tip Cassette ID', 'Tip Port No', 'Tip Slot No', 'Tip Width', 'Mileage 평균', 'Approach Count 평균',
          '소요시간 (초)', '포인트당 시간 (초)', '파일'
        ],
        bundle.measurements.map(m => [
          m.suspect, m.lot, m.slot, m.recipe, m.time, m.role,
          m.value, m.delta, m.out ? '밖' : '',
          m.failed, m.stopped, m.invalid,
          m.tipId, m.tipCassette, m.tipPort, m.tipSlot, m.tipWidth, m.mileage, m.approach,
          m.seconds, m.perPoint, m.key
        ])
      ),
      emphasize: row => row[0] !== ''
    })
  }
  if (bundle.points.length) {
    sheets.push({
      name: '이상 측정 포인트',
      rows: toSheetRows(
        ['Lot', 'Slot', 'Recipe', '시각', 'Point', 'Site X', 'Site Y', 'State', 'Valid', bundle.column, '포인트 기준 (그룹 평균)', 'Δ (값 − 기준)', '파일'],
        bundle.points.map(p => [p.lot, p.slot, p.recipe, p.time, p.point, p.siteX, p.siteY, p.state, p.valid, p.value, p.reference, p.delta, p.key])
      )
    })
  }
  // For reading, not for re-use as input: 4 decimals, as the skewvoir receipt does.
  const round = (cell: string | number) => typeof cell === 'number' && !Number.isInteger(cell) ? Number(cell.toFixed(4)) : cell
  return sheets.map(sheet => ({ ...sheet, rows: sheet.rows.map(row => row.map(round)) }))
}
