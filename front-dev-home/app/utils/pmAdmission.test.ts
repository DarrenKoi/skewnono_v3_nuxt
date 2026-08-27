// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { admissionReport, pickDefaultTool } from './pmAdmission.ts'
import { applyTolerance, scoreCells, type CellInput } from './tttmCells.ts'
import type { SkewMatrix } from './tttmGrouping.ts'

// A·B is the group; C is the tool coming out of PM. At CD 15 the action limit
// is 0.15 nm, so a 0.05 tolerance index... — see each test for the knob used.
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

// tolerance index 1.0 → threshold = the full action limit = 0.15 nm at CD 15.
const ranked = (cells: CellInput[], tolerance = 1.0) =>
  applyTolerance(scoreCells(cells), tolerance)

test('admissionReport: a failing member pair becomes a per-cell tuning target', () => {
  // Threshold at index 1.0, CD 15 → 0.15 nm. C–A = 0.24 (over by 0.09),
  // C–B = 0.13 (passes). The card must name the worst pair and say how far
  // it has to come down — worked example, not recomputed from the code.
  const report = admissionReport('C', ['A', 'B'], ranked([cell()]))
  assert.ok(report)
  assert.equal(report.inGroup, false)
  assert.equal(report.admitted, false)
  assert.equal(report.blockedCells, 1)
  assert.equal(report.cells.length, 1)

  const row = report.cells[0]!
  assert.equal(row.thresholdNm, 0.15)
  assert.equal(row.worst?.a, 'C')
  assert.equal(row.worst?.b, 'A')
  assert.equal(row.worst?.skewNm, 0.24)
  assert.equal(row.failingPairs, 1)
  assert.ok(Math.abs(row.requiredNm - 0.09) < 1e-9)
  assert.equal(row.admitted, false)
})

test('admissionReport: a group member is already admitted, with nothing to tune', () => {
  const report = admissionReport('A', ['A', 'B'], ranked([cell()]))
  assert.ok(report)
  assert.equal(report.inGroup, true)
  assert.equal(report.admitted, true)
  assert.equal(report.blockedCells, 0)
  assert.deepEqual(report.cells, [])
})

test('admissionReport: an unmeasured member pair blocks admission without a violation', () => {
  // C–A passes comfortably, C–B was never measured. The clique requires a
  // MEASURED in-tolerance pair with every member, so the cell must not admit —
  // but there is no failing pair and nothing to "reduce", and the card must be
  // able to word that difference (same stance as ExcludedTool.exceeds).
  const report = admissionReport('C', ['A', 'B'], ranked([cell({
    matrix: matrix([
      [0, 0.02, 0.02],
      [0.02, 0, null],
      [0.02, null, 0]
    ])
  })]))
  assert.ok(report)
  const row = report.cells[0]!
  assert.deepEqual(row.unmeasured, ['B'])
  assert.equal(row.failingPairs, 0)
  assert.equal(row.requiredNm, 0)
  assert.equal(row.admitted, false)
  assert.equal(report.admitted, false)
})

test('admissionReport: cells sort worst-first by CD-relative index, and a clean pass admits', () => {
  // Two cells at different CDs. In the 60 nm cell C–A is 0.30 nm — big in nm
  // but only 0.5× its 0.60 nm limit. In the 15 nm cell C–A is 0.18 nm — 1.2×
  // its 0.15 nm limit. The 15 nm cell is the worse one and must lead.
  const wide = cell({
    cell_id: 'bc2-X',
    median_cd_nm: 60,
    matrix: matrix([
      [0, 0.02, 0.30],
      [0.02, 0, 0.10],
      [0.30, 0.10, 0]
    ])
  })
  const tight = cell({
    matrix: matrix([
      [0, 0.02, 0.18],
      [0.02, 0, 0.05],
      [0.18, 0.05, 0]
    ])
  })
  const report = admissionReport('C', ['A', 'B'], ranked([wide, tight]))
  assert.ok(report)
  assert.equal(report.cells[0]!.cell.cell_id, 'bc1-Y')
  assert.equal(report.cells[0]!.admitted, false)
  assert.equal(report.cells[1]!.cell.cell_id, 'bc2-X')
  assert.equal(report.cells[1]!.admitted, true)
  assert.equal(report.admitted, false)

  // Same fleet, every pair inside every cell's own allowance → admitted.
  const clean = admissionReport('C', ['A', 'B'], ranked([wide]))
  assert.ok(clean)
  assert.equal(clean.admitted, true)
  assert.equal(clean.cells[0]!.requiredNm, 0)
})

test('admissionReport: no group means no report', () => {
  assert.equal(admissionReport('C', [], ranked([cell()])), null)
})

test('pickDefaultTool: the most recent post-PM tool is the one being tuned now', () => {
  const picked = pickDefaultTool([
    { eqp_id: 'A', post_pm_at: '2026-05-01T10:00:00' },
    { eqp_id: 'B', post_pm_at: '2026-05-20T08:00:00' },
    { eqp_id: 'C', post_pm_at: null }
  ], ['C'])
  assert.equal(picked, 'B')
})

test('pickDefaultTool: with no PM dates, fall back to the worst-excluded tool, then the roster', () => {
  const noDates = [
    { eqp_id: 'A', post_pm_at: null },
    { eqp_id: 'B', post_pm_at: null },
    { eqp_id: 'C', post_pm_at: null }
  ]
  assert.equal(pickDefaultTool(noDates, ['C', 'B']), 'C')
  assert.equal(pickDefaultTool(noDates, []), 'A')
  assert.equal(pickDefaultTool([], []), null)
})
