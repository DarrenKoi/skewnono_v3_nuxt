// The layout + ranking model behind the single-MSR FDC sparkline matrix.
//
// Pure: no Vue, no ECharts. Everything the matrix decides — which row a param
// sits in, how cells are ordered, which params lead the ranking, how wide the
// grid is, and what verdict a cell's CD relation carries — is decided here so it
// can be tested with `node --test`. The component that consumes this only turns
// the model into an ECharts option.
import type { FdcCategory, FdcParamSummary } from '~/composables/useMsrFileApi'
import { alignToSequences, type SequenceModel, type SequenceSource } from './sequence.ts'
import { buildCdFdcRelationship } from './relationships.ts'

/** Hard cap on matrix width. Rows are CATEGORIES, so their count is small and
 * fixed; letting the column count track the widest row would let one fat
 * category (the office catalog is not a closed set) dictate cell width for the
 * whole matrix and shrink every cell to illegibility. Oversized categories wrap
 * onto continuation rows instead. */
export const MAX_COLUMNS = 4

/** How many params the lead 검토 근거 row holds. Clamped by MAX_COLUMNS at use,
 * so raising this can never silently widen the matrix. */
export const MAX_EVIDENCE = 4

/** What a cell's CD relation means, decided here rather than inferred by the
 * view. `reference` is the CD cell itself, where correlation is not applicable
 * rather than unavailable — a distinction a comment cannot enforce. */
export type CellRelationState = 'reference' | 'unavailable' | 'value'

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
  /** Pearson r against cd_value. Non-null only when `rState === 'value'`. */
  r: number | null
  rState: CellRelationState
  /** Why r is unavailable; null otherwise. Surfaced in the tooltip so the three
   * honest failures `assess()` distinguishes are not flattened away. */
  reason: string | null
  /** True for the copy that lives in the lead 검토 근거 row. */
  duplicated: boolean
}

export type MatrixRowKind = 'cd' | 'evidence' | 'category'

export interface MatrixRow {
  kind: MatrixRowKind
  /** Row header text, and the matrix y-dimension ordinal value. Unique by
   * construction — duplicates would make `coord` lookups ambiguous. */
  label: string
  cells: MatrixCell[]
}

export interface ParamMatrixModel {
  columns: number
  rows: MatrixRow[]
  /** The shared sequence axis every cell indexes. */
  sequences: number[]
  /** How many FDC cells `hideUnavailable` dropped. Zero when the option is off.
   * Surfaced so the view can say what it hid — a silent drop would read as
   * "not measured" rather than "hidden by choice". */
  hiddenUnavailable: number
}

export interface ParamMatrixOptions {
  /** Drop FDC cells whose CD relation is 평가 불가 (no pairs, too few, or a
   * constant axis). They crowd the matrix and drag their reason strings into
   * the linked-axis tooltip; hiding them is a view preference, so it lives
   * here as an option rather than a hard rule. */
  hideUnavailable?: boolean
}

/** category code → Korean label, taken from the backend's own labelling rather
 * than a hardcoded map, so a new office category needs no frontend change.
 * First NON-EMPTY label wins, so a blank `category_label` falls through to the
 * caller's `?? category` code fallback rather than rendering an empty header.
 *
 * Exported because the set-scope matrix (fdcSet.ts) groups by the same rule —
 * two copies would let the two FDC screens label one category differently. */
export const fdcCategoryLabels = (fdcParams: FdcParamSummary[]): Map<string, string> => {
  const out = new Map<string, string>()
  for (const p of fdcParams) if (p.category_label && !out.has(p.category)) out.set(p.category, p.category_label)
  return out
}

/** Strongest CD relation first; unevaluable cells last; name as a stable
 * tie-break so identical |r| never reorders between renders. */
const byCdRelation = (a: MatrixCell, b: MatrixCell): number => {
  const ra = a.r == null ? -1 : Math.abs(a.r)
  const rb = b.r == null ? -1 : Math.abs(b.r)
  if (ra !== rb) return rb - ra
  return a.param.localeCompare(b.param)
}

/** Split one category's cells into rows of at most MAX_COLUMNS. Continuation
 * rows carry a ` (n)` suffix, because the label doubles as the matrix
 * y-dimension ordinal value and a repeat would make `coord` ambiguous. */
const wrapCategory = (label: string, cells: MatrixCell[]): MatrixRow[] => {
  const out: MatrixRow[] = []
  for (let start = 0; start < cells.length; start += MAX_COLUMNS) {
    const part = start / MAX_COLUMNS
    out.push({
      kind: 'category',
      label: part === 0 ? label : `${label} (${part + 1})`,
      cells: cells.slice(start, start + MAX_COLUMNS)
    })
  }
  return out
}

export const buildParamMatrix = (
  model: SequenceModel,
  source: SequenceSource,
  options: ParamMatrixOptions = {}
): ParamMatrixModel => {
  const sequences = model.sequences
  const cdParam = model.parameter
  const labels = fdcCategoryLabels(source.fdc_params)

  const cdCell: MatrixCell = {
    param: cdParam,
    category: 'cd',
    unit: model.unit,
    nominal: null,
    // CD points follow the CD rows, which may not cover every sequence on the
    // shared axis, so they genuinely need projecting onto it.
    values: alignToSequences(model.cd.points, sequences),
    r: null,
    rState: 'reference',
    reason: null,
    duplicated: false
  }

  const allFdcCells: MatrixCell[] = model.fdc.map((series) => {
    // ALWAYS the parameter-scoped inner join, regardless of the sequence
    // axis mode: `source.rows` here is unscoped (every parameter's rows),
    // and buildCdFdcRelationship inner-joins CD against dynamic_fdc on its
    // own terms. Under axisMode 'param' this matches the sparkline
    // (series.points) exactly. Under 'all' it does NOT: the sparkline then
    // spans the whole MSR (the shared 'all' axis) while `r` beside it stays
    // computed from the narrower parameter-scoped join — a real divergence,
    // not a bug. Preserving `all` verbatim (a real, user-selectable
    // whole-MSR comparison) was the deliberate call, and this mismatch under
    // it is a known, accepted gap rather than an oversight.
    const rel = buildCdFdcRelationship(source.rows, cdParam, series.param, source.dynamic_fdc)
    const ready = rel.readiness === 'ready' && rel.pearson != null
    return {
      param: series.param,
      category: series.category,
      unit: series.unit,
      nominal: series.nominal,
      // NOT alignToSequences: analyzeSequence already builds FDC points by
      // mapping over this same axis, so they arrive one-per-slot in order.
      values: series.points.map(p => (p.measured ? p.value : null)),
      r: ready ? rel.pearson : null,
      rState: ready ? 'value' : 'unavailable',
      reason: rel.reason,
      duplicated: false
    }
  })

  // The CD reference is never hidden — with every FDC cell 평가 불가 and
  // hidden, the matrix degrades to the CD row alone rather than to nothing.
  const fdcCells = options.hideUnavailable === true
    ? allFdcCells.filter(c => c.rState !== 'unavailable')
    : allFdcCells
  const hiddenUnavailable = allFdcCells.length - fdcCells.length

  const rows: MatrixRow[] = [
    { kind: 'cd', label: 'CD', cells: [cdCell] }
  ]

  for (const category of new Set(fdcCells.map(c => c.category))) {
    const cells = fdcCells.filter(c => c.category === category).sort(byCdRelation)
    rows.push(...wrapCategory(labels.get(category) ?? category, cells))
  }

  // The lead row holds COPIES — the originals never move, so the category rows
  // stay complete. A param whose relationship is 평가 불가 is excluded outright:
  // ranking it would mean ranking on a number `assess()` refused to produce.
  //
  // Per the domain glossary (CONTEXT.md), FDC drift is 검토 근거 — evidence that
  // raises verification priority — never a verdict that a param is at fault.
  const evidence = fdcCells
    .filter(c => c.rState === 'value')
    .sort(byCdRelation)
    .slice(0, Math.min(MAX_EVIDENCE, MAX_COLUMNS))
    .map(c => ({ ...c, duplicated: true }))

  if (evidence.length) {
    rows.splice(1, 0, { kind: 'evidence', label: '주요 검토 근거', cells: evidence })
  }

  // No clamp needed here: categories are wrapped at MAX_COLUMNS and the evidence
  // row is capped by it too, so the width is bounded by construction.
  const widest = rows
    .filter(r => r.kind !== 'cd')
    .reduce((max, r) => Math.max(max, r.cells.length), 0)

  return { columns: Math.max(1, widest), rows, sequences, hiddenUnavailable }
}
