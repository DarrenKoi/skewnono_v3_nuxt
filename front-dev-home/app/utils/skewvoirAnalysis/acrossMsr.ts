// Skewvoir Correlation — Across-MSR Outcome mode (set scope).
//
// ONE MSR IS ONE POINT. The within-MSR explorer (relationships.ts) pairs sites
// inside a single measurement; this module pairs whole measurements against each
// other, so the row unit is the MSR and the columns are the per-MSR features
// features.ts already derived. Nothing is recomputed here — every value on a
// point traces back to an MsrFeatureRow's DerivedValue, which is what keeps the
// provenance drawer able to explain any dot on the chart.
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import type {
  FeatureDefinition,
  FeatureFamily,
  MsrFeatureRow,
  DerivedValue,
  DynamicFdcSummary
} from './features.ts'
import { fitLine, pearson, spearman } from '../stats.ts'

/** One selectable X or Y column. `label`/`unit` come from the feature registry
 *  verbatim — this module never invents a unit. */
export interface AcrossMsrAxis {
  id: string
  label: string
  unit: string
  family: FeatureFamily
}

/** The statistics of a sequence-reduced dynamic FDC channel that stay in the
 *  channel's OWN unit, so the registry unit can be reused as-is.
 *
 *  `slope` is deliberately absent: it is param-unit PER SEQUENCE STEP, and the
 *  registry carries no such unit. Offering it would mean either mislabelling it
 *  with the plain unit or fabricating one. */
const DYNAMIC_STATS = [
  { key: 'mean', suffix: '평균' },
  { key: 'std', suffix: '산포' },
  { key: 'range', suffix: '범위' }
] as const

/** The registry, flattened into columns that can actually be plotted: scalar
 *  features pass through unchanged, and each dynamic FDC channel expands into
 *  its unit-preserving statistics (`<id>#mean` and friends). */
export const acrossMsrAxes = (registry: readonly FeatureDefinition[]): AcrossMsrAxis[] => {
  const axes: AcrossMsrAxis[] = []
  for (const def of registry) {
    if (def.family === 'dynamic_fdc') {
      for (const stat of DYNAMIC_STATS) {
        axes.push({
          id: `${def.id}#${stat.key}`,
          label: `${def.label} ${stat.suffix}`,
          unit: def.unit,
          family: def.family
        })
      }
      continue
    }
    axes.push({ id: def.id, label: def.label, unit: def.unit, family: def.family })
  }
  return axes
}

const SCALAR_FEATURES = ['level', 'spread', 'coverage', 'failure', 'spatial'] as const
type ScalarFeatureId = (typeof SCALAR_FEATURES)[number]

const isScalarFeature = (id: string): id is ScalarFeatureId =>
  (SCALAR_FEATURES as readonly string[]).includes(id)

const isDynamicStat = (key: string): key is (typeof DYNAMIC_STATS)[number]['key'] =>
  DYNAMIC_STATS.some(s => s.key === key)

/** The DerivedValue an axis id names on ONE feature row, or null when this MSR
 *  carries no such value.
 *
 *  Null is the honest answer for four distinct absences — a null `spatial`, an
 *  FDC channel this MSR never recorded, a non-finite statistic (a single-sequence
 *  range has no value), and an unknown id. Every one of them must stay OUT of a
 *  correlation rather than enter it as a zero. */
export const acrossMsrAxisValue = (
  row: MsrFeatureRow,
  axisId: string
): DerivedValue<number> | null => {
  const finite = (v: DerivedValue<number> | null | undefined): DerivedValue<number> | null =>
    v != null && Number.isFinite(v.value) ? v : null

  if (isScalarFeature(axisId)) return finite(row[axisId])

  if (axisId.startsWith('fixed_fdc.')) {
    return finite(row.fixedFdc[axisId.slice('fixed_fdc.'.length)])
  }

  if (axisId.startsWith('dynamic_fdc.')) {
    const [key, stat] = axisId.slice('dynamic_fdc.'.length).split('#')
    if (!key || !stat || !isDynamicStat(stat)) return null
    const summary: DerivedValue<DynamicFdcSummary> | undefined = row.dynamicFdc[key]
    if (!summary) return null
    // The statistic replaces the object; every provenance field the sequence
    // reduction recorded (n, missing, transform, reference, version) is carried
    // through unchanged, so the value stays traceable to the same reduction.
    return finite({ ...summary, value: summary.value[stat] })
  }

  return null
}

// ── Correlation over MSR-grain points ───────────────────────────────────────

/** The floor below which no coefficient is published. At n = 2 any two distinct
 *  points are perfectly collinear, so r is trivially ±1 and means nothing; this
 *  is the same floor `pearson`/`spearman` already enforce, restated here so the
 *  suppression can carry an explicit reason instead of a bare null. */
export const MIN_CORRELATION_N = 3

/** Who a point belongs to. `eqpId` stratifies (and colors); `label` is what the
 *  tooltip shows. Both come from the set's MeasHistRow — this module does not
 *  reach for them itself. */
export interface AcrossMsrIdentity {
  eqpId: string
  label: string
}

/** One MSR — one point. */
export interface AcrossMsrPoint {
  msr: string
  label: string
  eqpId: string
  x: number
  y: number
}

/** A correlation over some subset of the points. `pearson`/`spearman` are null
 *  whenever `reason` is set — the two are never both meaningful. */
export interface AcrossMsrCorrelation {
  n: number
  pearson: number | null
  spearman: number | null
  reason: string | null
}

export interface AcrossMsrStratum extends AcrossMsrCorrelation {
  eqpId: string
}

export interface AcrossMsrResult {
  x: AcrossMsrAxis | null
  y: AcrossMsrAxis | null
  points: AcrossMsrPoint[]
  pooled: AcrossMsrCorrelation
  /** Per-tool correlations, ranked by point count (desc), ties by id — the
   *  stratified half of the Simpson's-paradox check. */
  strata: AcrossMsrStratum[]
  /** Loaded MSRs excluded from the pairing because one of the two axes had no
   *  value for them. Counted, never silently absorbed. */
  droppedN: number
}

// The one place a correlation is published or suppressed. Kept private so no
// caller can publish a coefficient without also publishing its reason.
const correlate = (pairs: [number, number][]): AcrossMsrCorrelation => {
  const n = pairs.length
  if (n === 0) {
    return { n, pearson: null, spearman: null, reason: '두 축 모두에 값이 있는 MSR 이 없습니다 — 평가 불가' }
  }
  if (n < MIN_CORRELATION_N) {
    return { n, pearson: null, spearman: null, reason: `MSR ${n}개 — ${MIN_CORRELATION_N}개 미만이라 계수를 내지 않습니다` }
  }
  const r = pearson(pairs)
  if (r == null) {
    return { n, pearson: null, spearman: null, reason: '한쪽 축의 분산이 없습니다 — 평가 불가' }
  }
  return { n, pearson: r, spearman: spearman(pairs), reason: null }
}

/**
 * One point per loaded MSR, plus the pooled and per-tool correlations side by
 * side.
 *
 * BOTH are reported on purpose. A pooled coefficient over measurements from
 * several tools can carry — or reverse — a sign that no single tool shows
 * (Simpson's paradox), so the stratified view is not a refinement of the pooled
 * one, it is the check on it. Benchmark research §7.3 asks for exactly this
 * pairing.
 */
export const buildAcrossMsrOutcome = (
  rows: readonly MsrFeatureRow[],
  x: AcrossMsrAxis | null,
  y: AcrossMsrAxis | null,
  identity: ReadonlyMap<string, AcrossMsrIdentity>
): AcrossMsrResult => {
  const points: AcrossMsrPoint[] = []
  let droppedN = 0

  if (x && y) {
    for (const row of rows) {
      const vx = acrossMsrAxisValue(row, x.id)
      const vy = acrossMsrAxisValue(row, y.id)
      if (!vx || !vy) {
        droppedN++
        continue
      }
      const who = identity.get(row.msr)
      points.push({
        msr: row.msr,
        label: who?.label ?? row.msr,
        eqpId: who?.eqpId ?? '',
        x: vx.value,
        y: vy.value
      })
    }
  }

  const pooled = correlate(points.map(p => [p.x, p.y] as [number, number]))

  // Only named tools form a stratum: a point whose measurement carries no
  // eqp_id cannot be attributed to equipment, and lumping those together would
  // invent a tool that does not exist.
  const byTool = new Map<string, [number, number][]>()
  for (const p of points) {
    if (!p.eqpId) continue
    const arr = byTool.get(p.eqpId) ?? []
    arr.push([p.x, p.y])
    byTool.set(p.eqpId, arr)
  }
  const strata: AcrossMsrStratum[] = [...byTool.entries()]
    .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
    .map(([eqpId, pairs]) => ({ eqpId, ...correlate(pairs) }))

  return { x, y, points, pooled, strata, droppedN }
}

/** The pooled trend line, as the two endpoints of a segment spanning the drawn
 *  x-range. Empty when there is no line to honestly draw.
 *
 *  A fit line IS a claim about the relationship, so it lives or dies by the same
 *  gate the coefficient does: when `correlate` withheld the number and gave a
 *  reason, a line through the same points would state exactly the claim the
 *  suppression refused to make — louder than the number would have, because a
 *  line reads as a trend without any `n` beside it. This decision sits here
 *  rather than in the chart so it is tested, and so the two FDC/CD screens
 *  cannot answer it differently. */
export const pooledFitLine = (result: AcrossMsrResult): [number, number][] => {
  if (result.pooled.reason !== null) return []
  return fitLine(result.points.map(p => [p.x, p.y] as [number, number])) ?? []
}
