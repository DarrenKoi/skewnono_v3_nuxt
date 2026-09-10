// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyTolerance,
  barFraction,
  cellLabel,
  countFailingPairs,
  excludedTools,
  rankCells,
  scoreCells,
  worstPairOf,
  TOLERANCE_MARK,
  type CellInput
} from './tttmCells.ts'
import type { SkewMatrix } from './tttmGrouping.ts'

// Three tools, one bad actor. C sits far from both A and B; A and B match well.
const matrix = (values: (number | null)[][], tools = ['A', 'B', 'C']): SkewMatrix =>
  ({ tools, values })

const cell = (over: Partial<CellInput> = {}): CellInput => ({
  cell_id: 'bc1-Y',
  beam_condition: 'BC1',
  axis: 'Y',
  median_cd_nm: 15,
  tier: 'direct',
  confidence: 'High',
  labels: [],
  matrix: matrix([
    [0, 0.02, 0.24],
    [0.02, 0, 0.13],
    [0.24, 0.13, 0]
  ]),
  ...over
})

test('worstPairOf: names both tools, not just the number', () => {
  // The whole reason this exists beside maxMeasuredPair: every 3a surface quotes
  // the pair, and an unnamed 0.240 cannot be acted on.
  const worst = worstPairOf(cell().matrix, 15)
  assert.equal(worst?.skewNm, 0.24)
  assert.deepEqual([worst?.a, worst?.b], ['A', 'C'])
  // 0.24 nm against a 0.15 nm limit — 1.6× over.
  assert.ok(Math.abs((worst?.index ?? 0) - 1.6) < 1e-9)
})

test('worstPairOf: an entirely unmeasured cell yields null, not zero', () => {
  const empty = matrix([[0, null], [null, 0]], ['A', 'B'])
  assert.equal(worstPairOf(empty, 15), null)
  assert.equal(worstPairOf(matrix([], []), 15), null)
  // The diagonal is 0 by contract and must not be mistaken for a measured pair
  // in a matrix that has none.
  assert.equal(worstPairOf(matrix([[0]], ['A']), 15), null)
})

// The four tests below moved here from tttmLimits.test.ts when worstPairOf
// replaced worstFractionOfLimit. They pin the ranking rule, not the function.

test('worstPairOf: takes the worst pair, not the average', () => {
  // A group is only as matched as its loosest pair. Averaging would let the one
  // bad pair hide behind the two good ones and rank this cell as clean.
  const values = matrix([
    [0, 0.02, 0.02],
    [0.02, 0, 0.30],
    [0.02, 0.30, 0]
  ])
  const worst = worstPairOf(values, 15)
  assert.equal(worst?.skewNm, 0.30)
  assert.ok((worst?.index ?? 0) > 1)
})

test('worstPairOf: skips null pairs rather than scoring them as zero', () => {
  // null means "this pair has no shared data", not "these tools match
  // perfectly". Treating it as 0 would rank an unmeasured cell as the best one.
  const values = matrix([
    [0, null, 0.08],
    [null, 0, null],
    [0.08, null, 0]
  ])
  assert.equal(worstPairOf(values, 15)?.skewNm, 0.08)
})

test('worstPairOf: a NaN pair is skipped, not ranked', () => {
  // With a `typeof v === "number"` gate this returned NaN, which then (a)
  // passed the `severity !== null` guard, (b) rendered as "CD 대비 NaN×", and
  // (c) made the sort comparator return NaN, so the ordering of the whole list
  // became implementation-defined. isMeasured is Number.isFinite for this.
  const values = matrix([
    [0, Number.NaN, 0.06],
    [Number.NaN, 0, null],
    [0.06, null, 0]
  ])
  const worst = worstPairOf(values, 15)
  assert.equal(Number.isNaN(worst?.index as number), false)
  assert.equal(worst?.skewNm, 0.06)
})

test('applyTolerance: worstExceeds is the one comparison four surfaces share', () => {
  // The bar colour, the value colour, the 초과 wording and the failing count are
  // four statements of this single test; computing it per call site is how they
  // start disagreeing.
  const [tight] = applyTolerance(scoreCells([cell()]), 0.1) // 0.015 nm at CD 15
  const [loose] = applyTolerance(scoreCells([cell()]), 2.0) // 0.300 nm at CD 15
  assert.equal(tight?.worstExceeds, true)
  assert.equal(loose?.worstExceeds, false)
  // And it agrees with the count beside it: the worst pair is over iff any is.
  assert.ok((tight?.failingPairs ?? 0) > 0)
  assert.equal(loose?.failingPairs, 0)
})

test('scoreCells: every field it returns survives a tolerance change untouched', () => {
  // The split exists so a slider drag re-runs only applyTolerance. If this ever
  // fails, something tolerance-dependent leaked into the memoised half.
  const cells = [cell(), cell({ cell_id: 'bc2-X', median_cd_nm: 68 })]
  assert.deepEqual(scoreCells(cells), scoreCells(cells))
  const ranked = (t: number) => rankCells(cells, t).map(r => [r.cell.cell_id, r.severity])
  assert.deepEqual(ranked(0.1), ranked(2.0))
})

test('countFailingPairs: counts the upper triangle once, not twice', () => {
  // Symmetric matrix: A·C and C·A are the same pair. Two pairs exceed 0.05.
  assert.equal(countFailingPairs(cell().matrix, 0.05), 2)
  assert.equal(countFailingPairs(cell().matrix, 0.3), 0)
})

test('rankCells: orders by CD-relative index, NOT by nanometres', () => {
  // The trap this guards: 0.30 nm at a 68 nm CD (0.44×) is comfortable, while
  // 0.24 nm on the monitor wafer (1.6×) is well past the limit. Sorting by nm
  // would put the harmless cell first.
  const wide = cell({
    cell_id: 'bc2-X',
    beam_condition: 'BC2',
    axis: 'X',
    median_cd_nm: 68,
    matrix: matrix([
      [0, 0.30, 0.10],
      [0.30, 0, 0.10],
      [0.10, 0.10, 0]
    ])
  })
  const ranked = rankCells([wide, cell()], 0.33)
  assert.deepEqual(ranked.map(r => r.cell.cell_id), ['bc1-Y', 'bc2-X'])
})

test('rankCells: a cell with nothing measured sorts last', () => {
  const blank = cell({ cell_id: 'blank', matrix: matrix([[0, null], [null, 0]], ['A', 'B']) })
  const ranked = rankCells([blank, cell()], 0.33)
  assert.deepEqual(ranked.map(r => r.cell.cell_id), ['bc1-Y', 'blank'])
  assert.equal(ranked[1]?.severity, null)
})

test('rankCells: the tolerance moves the threshold but never the order', () => {
  const wide = cell({ cell_id: 'bc2-X', median_cd_nm: 68 })
  const loose = rankCells([wide, cell()], 1.0)
  const tight = rankCells([wide, cell()], 0.1)
  assert.deepEqual(loose.map(r => r.cell.cell_id), tight.map(r => r.cell.cell_id))
  // Each cell converts the same knob against its OWN CD: 0.33 × 1% × 15 nm vs
  // × 68 nm. Same slider, four-and-a-half times the allowance.
  // Sorted worst-first, so the monitor-wafer cell (1.6×) leads the 68 nm one.
  const [monitorRow, wideRow] = rankCells([wide, cell()], 0.33)
  assert.ok(Math.abs((monitorRow?.thresholdNm ?? 0) - 0.0495) < 1e-9)
  assert.ok(Math.abs((wideRow?.thresholdNm ?? 0) - 0.2244) < 1e-9)
})

test('cellLabel: identity without the CD band', () => {
  assert.equal(cellLabel(cell()), 'BC1 · Y')
})

test('barFraction: the tolerance mark sits at a third for every row', () => {
  // Two cells at different CDs, each exactly on its own limit, must draw the
  // same bar — that is what makes the rows comparable at a glance.
  assert.ok(Math.abs(barFraction(0.05, 0.05) - TOLERANCE_MARK) < 1e-12)
  assert.ok(Math.abs(barFraction(0.225, 0.225) - TOLERANCE_MARK) < 1e-12)
  // 0.240 against 0.105 is 2.29× over → 76% of a track that spans 3×.
  assert.ok(Math.abs(barFraction(0.24, 0.105) - 0.7619047) < 1e-6)
})

test('barFraction: clamps past 3x, and survives a zero threshold', () => {
  assert.equal(barFraction(9, 0.05), 1)
  assert.equal(barFraction(0.1, 0), 0)
})

test('excludedTools: reports the pair against a GROUP MEMBER, not the worst overall', () => {
  // C's worst pair overall is with D (0.90), but D is excluded too — quoting it
  // would explain nothing. What kept C out of {A,B} is its 0.24 with A.
  const four = cell({
    matrix: matrix(
      [
        [0, 0.02, 0.24, 0.30],
        [0.02, 0, 0.13, 0.28],
        [0.24, 0.13, 0, 0.90],
        [0.30, 0.28, 0.90, 0]
      ],
      ['A', 'B', 'C', 'D']
    )
  })
  const ranked = rankCells([four], 0.33)
  const out = excludedTools(['A', 'B', 'C', 'D'], ['A', 'B'], ranked)

  assert.deepEqual(out.map(t => t.eqp_id), ['D', 'C'])
  const c = out.find(t => t.eqp_id === 'C')
  assert.equal(c?.blocker?.skewNm, 0.24)
  assert.equal(c?.blocker?.b, 'A')
  assert.equal(c?.cell?.cell_id, 'bc1-Y')
})

test('excludedTools: no group means nothing to be excluded FROM', () => {
  // Not "everything is excluded" — with no N배화 group at this tolerance the
  // statement has no referent, and a card listing all five tools would be a lie
  // dressed as a finding.
  assert.deepEqual(excludedTools(['A', 'B', 'C'], [], rankCells([cell()], 0.33)), [])
})

test('excludedTools: a tool can be excluded while every pair it HAS is in tolerance', () => {
  // The case the exclusion card must not describe as "tolerance 초과". N배화
  // needs a measured, in-tolerance pair with EVERY member, so C is dropped for
  // the missing B pair even though its 0.02 with A passes comfortably. Callers
  // compare blocker.skewNm against thresholdNm rather than assuming a breach.
  const sparse = cell({
    matrix: matrix([
      [0, 0.02, 0.02],
      [0.02, 0, null],
      [0.02, null, 0]
    ])
  })
  const ranked = rankCells([sparse], 1.0) // threshold 0.15 nm at CD 15
  const [c] = excludedTools(['A', 'B', 'C'], ['A', 'B'], ranked)
  assert.equal(c?.eqp_id, 'C')
  assert.equal(c?.blocker?.skewNm, 0.02)
  assert.ok((c?.blocker?.skewNm ?? 0) <= (c?.thresholdNm ?? 0))
})

test('excludedTools: a tool with no measured pair against the group still appears', () => {
  // It is out of the group and the card must say so; it simply has no number to
  // quote, which the null blocker is how the caller learns.
  const sparse = cell({
    matrix: matrix([
      [0, 0.02, null],
      [0.02, 0, null],
      [null, null, 0]
    ])
  })
  const out = excludedTools(['A', 'B', 'C'], ['A', 'B'], rankCells([sparse], 0.33))
  assert.equal(out.length, 1)
  assert.equal(out[0]?.eqp_id, 'C')
  assert.equal(out[0]?.blocker, null)
})
