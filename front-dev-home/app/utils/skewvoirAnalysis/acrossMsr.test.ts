// front-dev-home/app/utils/skewvoirAnalysis/acrossMsr.test.ts
// Pure-logic tests — run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/acrossMsr.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { acrossMsrAxes, acrossMsrAxisValue, buildAcrossMsrOutcome, pooledFitLine } from './acrossMsr.ts'
import type { FeatureDefinition, MsrFeatureRow, DerivedValue, DynamicFdcSummary } from './features.ts'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const def = (over: Partial<FeatureDefinition> & Pick<FeatureDefinition, 'id'>): FeatureDefinition => ({
  label: over.id,
  unit: '',
  grain: 'msr',
  source: over.id,
  aggregation: '',
  family: 'level',
  ...over
})

const registry = (): FeatureDefinition[] => [
  def({ id: 'level', label: 'CD_TOP 평균', unit: 'nm', family: 'level' }),
  def({ id: 'coverage', label: '측정 커버리지', unit: 'ratio', family: 'coverage' }),
  def({ id: 'fixed_fdc.Vacc', label: 'Vacc', unit: 'V', family: 'fixed_fdc' }),
  def({ id: 'dynamic_fdc.StigmaX', label: 'StigmaX', unit: 'nm', family: 'dynamic_fdc' })
]

// ---------------------------------------------------------------------------
// acrossMsrAxes — the selectable X/Y axes, derived from the feature registry
// ---------------------------------------------------------------------------

test('scalar features become one axis each, carrying the registry label and unit', () => {
  const axes = acrossMsrAxes(registry())
  const level = axes.find(a => a.id === 'level')
  assert.deepEqual(level, { id: 'level', label: 'CD_TOP 평균', unit: 'nm', family: 'level' })
  const fixed = axes.find(a => a.id === 'fixed_fdc.Vacc')
  assert.equal(fixed?.unit, 'V')
  assert.equal(fixed?.label, 'Vacc')
})

test('a dynamic FDC feature expands into its unit-preserving statistics only', () => {
  const axes = acrossMsrAxes(registry())
  const dyn = axes.filter(a => a.family === 'dynamic_fdc')
  assert.deepEqual(dyn.map(a => a.id), [
    'dynamic_fdc.StigmaX#mean',
    'dynamic_fdc.StigmaX#std',
    'dynamic_fdc.StigmaX#range'
  ])
  // mean/std/range are all in the channel's own unit, so the registry unit is
  // reused verbatim. slope is NOT offered: it is per sequence step, a unit the
  // registry does not carry and this module must not invent.
  assert.ok(dyn.every(a => a.unit === 'nm'))
  assert.deepEqual(dyn.map(a => a.label), ['StigmaX 평균', 'StigmaX 산포', 'StigmaX 범위'])
  assert.ok(!axes.some(a => a.id.endsWith('#slope')))
})

test('an empty registry yields no axes', () => {
  assert.deepEqual(acrossMsrAxes([]), [])
})

// ---------------------------------------------------------------------------
// acrossMsrAxisValue — reading ONE axis off a feature row, provenance intact
// ---------------------------------------------------------------------------

const derived = (value: number, over: Partial<DerivedValue<number>> = {}): DerivedValue<number> => ({
  value, unit: 'nm', n: 3, missing: 0, transform: 't', reference: 'r', version: 'v', ...over
})

const dynDerived = (v: DynamicFdcSummary): DerivedValue<DynamicFdcSummary> => ({
  value: v, unit: 'nm', n: 3, missing: 1, transform: 'seq-reduced', reference: 'dynamic_fdc.*.StigmaX', version: 'v'
})

const featureRow = (over: Partial<MsrFeatureRow> = {}): MsrFeatureRow => ({
  msr: 'M1',
  parameter: 'CD_TOP',
  level: derived(105),
  spread: derived(5),
  coverage: derived(0.75, { unit: 'ratio' }),
  failure: derived(0.25, { unit: 'ratio' }),
  spatial: derived(10),
  fixedFdc: { Vacc: derived(500, { unit: 'V' }) },
  dynamicFdc: { StigmaX: dynDerived({ mean: 0.12, std: 0.02, range: 0.04, slope: 0.01 }) },
  ...over
})

test('a scalar axis returns the feature row DerivedValue itself', () => {
  assert.equal(acrossMsrAxisValue(featureRow(), 'level')?.value, 105)
  assert.equal(acrossMsrAxisValue(featureRow(), 'coverage')?.unit, 'ratio')
  assert.equal(acrossMsrAxisValue(featureRow(), 'fixed_fdc.Vacc')?.value, 500)
})

test('a dynamic FDC axis returns the named statistic, keeping n/missing/reference', () => {
  const v = acrossMsrAxisValue(featureRow(), 'dynamic_fdc.StigmaX#std')
  assert.equal(v?.value, 0.02)
  assert.equal(v?.n, 3)
  assert.equal(v?.missing, 1)
  assert.equal(v?.reference, 'dynamic_fdc.*.StigmaX')
})

test('an axis with no value on this row is null, never zero', () => {
  // spatial is legitimately null (fewer than 2 placeable sites).
  assert.equal(acrossMsrAxisValue(featureRow({ spatial: null }), 'spatial'), null)
  // a channel this MSR never carried.
  assert.equal(acrossMsrAxisValue(featureRow(), 'fixed_fdc.Missing'), null)
  assert.equal(acrossMsrAxisValue(featureRow(), 'dynamic_fdc.Missing#mean'), null)
  // a non-finite statistic (single-sequence range/slope) is not a value.
  const nan = featureRow({ dynamicFdc: { StigmaX: dynDerived({ mean: 0.1, std: Number.NaN, range: Number.NaN, slope: Number.NaN }) } })
  assert.equal(acrossMsrAxisValue(nan, 'dynamic_fdc.StigmaX#range'), null)
  assert.equal(acrossMsrAxisValue(featureRow(), 'nonsense'), null)
})

// ---------------------------------------------------------------------------
// buildAcrossMsrOutcome — one MSR per point, pooled correlation
// ---------------------------------------------------------------------------

const AX_LEVEL = { id: 'level', label: 'CD_TOP 평균', unit: 'nm', family: 'level' } as const
const AX_SPREAD = { id: 'spread', label: 'CD_TOP 산포', unit: 'nm', family: 'spread' } as const

// One feature row per MSR carrying just the two scalar axes under test.
const rowsOf = (spec: [msr: string, x: number, y: number | null][]): MsrFeatureRow[] =>
  spec.map(([msr, x, y]) => featureRow({
    msr,
    level: derived(x),
    spread: y == null ? derived(Number.NaN) : derived(y)
  }))

const identityOf = (spec: [msr: string, eqpId: string][]) =>
  new Map(spec.map(([msr, eqpId]) => [msr, { eqpId, label: `${eqpId} · ${msr}` }]))

test('every loaded MSR becomes exactly one point, carrying its tool identity', () => {
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, 4], ['M3', 3, 6]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP02']])
  )
  assert.deepEqual(out.points.map(p => p.msr), ['M1', 'M2', 'M3'])
  assert.deepEqual(out.points.map(p => [p.x, p.y]), [[1, 2], [2, 4], [3, 6]])
  assert.deepEqual(out.points.map(p => p.eqpId), ['TP01', 'TP01', 'TP02'])
  assert.equal(out.points[0]?.label, 'TP01 · M1')
  assert.equal(out.droppedN, 0)
})

test('a perfectly proportional set pools to r = 1 (both coefficients)', () => {
  // y = 2x exactly: Pearson and Spearman are both +1 by definition, so the
  // expectation comes from the maths, not from re-running the implementation.
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, 4], ['M3', 3, 6]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP01']])
  )
  assert.equal(out.pooled.n, 3)
  assert.equal(out.pooled.pearson, 1)
  assert.equal(out.pooled.spearman, 1)
  assert.equal(out.pooled.reason, null)
})

test('an MSR missing either axis is dropped from the pairing and counted', () => {
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, null], ['M3', 3, 6], ['M4', 4, 8]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP01'], ['M4', 'TP01']])
  )
  assert.deepEqual(out.points.map(p => p.msr), ['M1', 'M3', 'M4'])
  assert.equal(out.droppedN, 1)
  assert.equal(out.pooled.n, 3)
})

test('too few MSRs suppresses the coefficient and says why', () => {
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, 4]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP02']])
  )
  assert.equal(out.pooled.n, 2)
  assert.equal(out.pooled.pearson, null)
  assert.equal(out.pooled.spearman, null)
  assert.match(out.pooled.reason ?? '', /3/)
})

test('a constant axis is reported as no variance, not as r = 0', () => {
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 5, 2], ['M2', 5, 4], ['M3', 5, 6]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP01']])
  )
  assert.equal(out.pooled.n, 3)
  assert.equal(out.pooled.pearson, null)
  assert.match(out.pooled.reason ?? '', /분산/)
})

test('an unselected axis yields no points and an explicit reason', () => {
  const out = buildAcrossMsrOutcome(rowsOf([['M1', 1, 2]]), null, AX_SPREAD, identityOf([['M1', 'TP01']]))
  assert.deepEqual(out.points, [])
  assert.equal(out.pooled.n, 0)
  assert.ok(out.pooled.reason)
})

// ---------------------------------------------------------------------------
// Stratified vs pooled — the Simpson's-paradox check (benchmark research §7.3)
// ---------------------------------------------------------------------------

test('pooled and per-tool correlations can disagree in sign, and both are reported', () => {
  // Each tool rises (y = x + 9 within TP01, y = x + 1 within TP02) while the two
  // tool clusters sit on a falling diagonal — the textbook reversal. Pooled must
  // come out negative and each stratum exactly +1.
  const out = buildAcrossMsrOutcome(
    rowsOf([
      ['M1', 1, 10], ['M2', 2, 11], ['M3', 3, 12],
      ['M4', 4, 5], ['M5', 5, 6], ['M6', 6, 7]
    ]),
    AX_LEVEL, AX_SPREAD,
    identityOf([
      ['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP01'],
      ['M4', 'TP02'], ['M5', 'TP02'], ['M6', 'TP02']
    ])
  )
  assert.ok((out.pooled.pearson ?? 0) < 0, 'pooled correlation is negative')
  assert.deepEqual(out.strata.map(s => s.eqpId), ['TP01', 'TP02'])
  assert.deepEqual(out.strata.map(s => s.pearson), [1, 1])
  assert.deepEqual(out.strata.map(s => s.n), [3, 3])
})

test('a tool with too few points is listed with its reason, not with a coefficient', () => {
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, 4], ['M3', 3, 6], ['M4', 9, 1], ['M5', 8, 3]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP01'], ['M4', 'TP02'], ['M5', 'TP02']])
  )
  // Ranked by point count: the 3-point tool first.
  assert.deepEqual(out.strata.map(s => s.eqpId), ['TP01', 'TP02'])
  const thin = out.strata[1]
  assert.equal(thin?.n, 2)
  assert.equal(thin?.pearson, null)
  assert.match(thin?.reason ?? '', /3/)
  // A suppressed stratum still contributes its points to the pooled coefficient.
  assert.equal(out.pooled.n, 5)
})

test('a point whose measurement carries no tool id forms no stratum', () => {
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, 4], ['M3', 3, 6]]),
    AX_LEVEL, AX_SPREAD,
    new Map()
  )
  assert.equal(out.points.length, 3)
  assert.deepEqual(out.strata, [])
  assert.equal(out.pooled.pearson, 1)
})

// ---------------------------------------------------------------------------
// pooledFitLine — the trend line lives or dies by the coefficient's own gate
// ---------------------------------------------------------------------------

test('the pooled fit line spans the drawn x-range when the coefficient was published', () => {
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, 4], ['M3', 3, 6]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP01']])
  )
  assert.equal(out.pooled.reason, null)
  // y = 2x exactly, so the endpoints are the maths, not a re-run of the impl.
  assert.deepEqual(pooledFitLine(out), [[1, 2], [3, 6]])
})

test('a suppressed correlation draws no fit line', () => {
  // Two MSRs is below MIN_CORRELATION_N, so `correlate` withholds the
  // coefficient. A line through the points would state exactly the claim the
  // suppression refused to make.
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 1, 2], ['M2', 2, 4]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP02']])
  )
  assert.notEqual(out.pooled.reason, null)
  assert.deepEqual(pooledFitLine(out), [])
})

test('an unfittable set draws no fit line even when the coefficient published', () => {
  // Every x identical: there is no slope to fit, and `fitLine` returns null.
  const out = buildAcrossMsrOutcome(
    rowsOf([['M1', 5, 2], ['M2', 5, 4], ['M3', 5, 6]]),
    AX_LEVEL, AX_SPREAD,
    identityOf([['M1', 'TP01'], ['M2', 'TP01'], ['M3', 'TP01']])
  )
  assert.deepEqual(pooledFitLine(out), [])
})
