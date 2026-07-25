// The layout + ranking model behind the single-MSR FDC sparkline matrix.
//
// Pure: no Vue, no ECharts. Everything the matrix decides — which row a param
// sits in, how cells are ordered, which params count as suspects, how wide the
// grid is — is decided here so it can be tested with `node --test`. The
// component that consumes this only turns the model into an ECharts option.
import type { FdcCategory, FdcParamSummary, MsrFileRow } from '~/composables/useMsrFileApi'
import type { SeqPoint, SequenceModel } from './sequence.ts'
import { buildCdFdcRelationship, type RelationshipReadiness } from './relationships.ts'

/** Hard cap on matrix width. Rows are CATEGORIES, so their count is small and
 * fixed; letting the column count track the widest row would let one fat
 * category (the office catalog is not a closed set) dictate cell width for the
 * whole matrix and shrink every cell to illegibility. Oversized categories wrap
 * onto continuation rows instead. */
export const MAX_COLUMNS = 4
export const MAX_SUSPECTS = 4

export interface MatrixCell {
  /** Param name. For the CD cell, the active CD parameter. */
  param: string
  /** `'cd'` marks the reference cell; otherwise the FDC category code. */
  category: FdcCategory | 'cd'
  unit: string
  /** Reference line value. Always null for the CD cell — CD has no nominal. */
  nominal: number | null
  /** Values aligned onto `ParamMatrixModel.sequences`; null marks a gap. */
  values: (number | null)[]
  /** Pearson r against cd_value. Null when not evaluable, and always null for
   * the CD cell itself, where correlation is not applicable rather than
   * unavailable — consumers detect that via `category === 'cd'`. */
  r: number | null
  readiness: RelationshipReadiness
  /** Why r is unavailable; null when ready. */
  reason: string | null
  /** True for the copy that lives in the suspects row. */
  duplicated: boolean
}

export type MatrixRowKind = 'cd' | 'suspects' | 'category'

export interface MatrixRow {
  /** Unique ordinal key. Doubles as the matrix y-dimension value, so it must
   * never repeat — duplicate ordinal keys make `coord` lookups ambiguous. */
  key: string
  kind: MatrixRowKind
  /** Row header text. Continuation rows carry a ` (n)` suffix to stay unique. */
  label: string
  continuation: boolean
  cells: MatrixCell[]
}

export interface ParamMatrixModel {
  columns: number
  rows: MatrixRow[]
  /** The shared sequence axis every cell indexes. */
  sequences: number[]
  /** True when any r came from a demo-coupled join. Always true on home mock. */
  demoCoupled: boolean
}

/** category code → Korean label, taken from the backend's own labelling rather
 * than a hardcoded map, so a new office category needs no frontend change. */
const labelsByCategory = (fdcParams: FdcParamSummary[]): Map<string, string> => {
  const out = new Map<string, string>()
  for (const p of fdcParams) if (!out.has(p.category)) out.set(p.category, p.category_label)
  return out
}

export const buildParamMatrix = (
  model: SequenceModel,
  rows: MsrFileRow[],
  dynamicFdc: Record<string, Record<string, number>>,
  fdcParams: FdcParamSummary[],
  cdParam: string
): ParamMatrixModel => {
  const sequences = model.sequences
  const align = (points: SeqPoint[]): (number | null)[] => {
    const bySeq = new Map(points.map(p => [p.sequence, p.measured ? p.value : null]))
    return sequences.map(s => bySeq.get(s) ?? null)
  }

  const labels = labelsByCategory(fdcParams)

  const cdCell: MatrixCell = {
    param: cdParam,
    category: 'cd',
    unit: model.unit,
    nominal: null,
    values: align(model.cd.points),
    r: null,
    readiness: 'ready',
    reason: null,
    duplicated: false
  }

  let demoCoupled = false
  const fdcCells: MatrixCell[] = model.fdc.map((series) => {
    const rel = buildCdFdcRelationship(rows, cdParam, series.param, dynamicFdc)
    if (rel.demoCoupled) demoCoupled = true
    return {
      param: series.param,
      category: series.category,
      unit: series.unit,
      nominal: series.nominal,
      values: align(series.points),
      r: rel.readiness === 'ready' ? rel.pearson : null,
      readiness: rel.readiness,
      reason: rel.reason,
      duplicated: false
    }
  })

  const matrixRows: MatrixRow[] = [
    { key: 'cd', kind: 'cd', label: 'CD', continuation: false, cells: [cdCell] }
  ]

  // One row per category, in first-seen order from the sequence model.
  const seen: string[] = []
  for (const cell of fdcCells) if (!seen.includes(cell.category)) seen.push(cell.category)
  for (const category of seen) {
    matrixRows.push({
      key: category,
      kind: 'category',
      label: labels.get(category) ?? category,
      continuation: false,
      cells: fdcCells.filter(c => c.category === category)
    })
  }

  const widest = matrixRows
    .filter(r => r.kind !== 'cd')
    .reduce((max, r) => Math.max(max, r.cells.length), 0)

  return {
    columns: Math.max(1, Math.min(MAX_COLUMNS, widest)),
    rows: matrixRows,
    sequences,
    demoCoupled
  }
}
