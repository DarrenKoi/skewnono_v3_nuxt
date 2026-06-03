// Pure-logic tests for pmPlanning. Zero deps - run with Node's built-in runner:
//   node --test app/utils/pmPlanning.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  maxAxisSkew, rankFocusTargets, gateVerdict,
  type ToolCells, type GateInputs
} from './pmPlanning.ts'

const cells = (sx500: number, sy500: number, sx800: number, sy800: number): ToolCells['cells'] => [
  { beam: '500V', axis: 'X', skew: sx500, current_value: 16 + sx500, median: 16, gap: sx500 },
  { beam: '500V', axis: 'Y', skew: sy500, current_value: 16 + sy500, median: 16, gap: sy500 },
  { beam: '800V', axis: 'X', skew: sx800, current_value: 16 + sx800, median: 16, gap: sx800 },
  { beam: '800V', axis: 'Y', skew: sy800, current_value: 16 + sy800, median: 16, gap: sy800 }
]

test('maxAxisSkew picks the worst axis by absolute skew, keeping its axis label', () => {
  const c = cells(0.5, -0.2, 0.1, 0.1)
  assert.deepEqual(maxAxisSkew(c, '500V'), { score: 0.5, axis: 'X' })

  const c2 = cells(0.1, -0.6, 0.1, 0.1)
  assert.deepEqual(maxAxisSkew(c2, '500V'), { score: 0.6, axis: 'Y' })
})

test('rankFocusTargets gates by threshold then takes bottom-N, sorted desc', () => {
  const tools: ToolCells[] = [
    { eqp_id: 'T1', cells: cells(0.62, 0.1, 0.1, 0.1) },
    { eqp_id: 'T2', cells: cells(0.55, 0.1, 0.1, 0.1) },
    { eqp_id: 'T3', cells: cells(0.47, 0.1, 0.1, 0.1) },
    { eqp_id: 'T4', cells: cells(0.38, 0.1, 0.1, 0.1) },
    { eqp_id: 'T5', cells: cells(0.10, 0.1, 0.1, 0.1) }
  ]
  const ranked = rankFocusTargets(tools, '500V', 0.40, 3)

  assert.deepEqual(ranked.map(r => r.eqp_id), ['T1', 'T2', 'T3'])
  assert.deepEqual(ranked.map(r => r.nominated), [true, true, true])
  assert.equal(ranked[0]?.score, 0.62)
  assert.equal(ranked[0]?.axis, 'X')
})

test('rankFocusTargets self-limits: fewer than N candidates when fleet is tight', () => {
  const tools: ToolCells[] = [
    { eqp_id: 'T1', cells: cells(0.45, 0.1, 0.1, 0.1) },
    { eqp_id: 'T2', cells: cells(0.20, 0.1, 0.1, 0.1) },
    { eqp_id: 'T3', cells: cells(0.10, 0.1, 0.1, 0.1) }
  ]
  const ranked = rankFocusTargets(tools, '500V', 0.40, 3)
  assert.deepEqual(ranked.map(r => r.eqp_id), ['T1'])
})

test('rankFocusTargets returns empty when the whole fleet is inside the line', () => {
  const tools: ToolCells[] = [
    { eqp_id: 'T1', cells: cells(0.10, 0.1, 0.1, 0.1) },
    { eqp_id: 'T2', cells: cells(0.20, 0.1, 0.1, 0.1) }
  ]
  assert.deepEqual(rankFocusTargets(tools, '500V', 0.40, 3), [])
})

test('gateVerdict is up only when both CD and BSM are in spec', () => {
  const base: GateInputs = { cd_in_spec: true, bsm_in_spec: true }
  assert.equal(gateVerdict(base), 'up')
  assert.equal(gateVerdict({ cd_in_spec: false, bsm_in_spec: true }), 'hold')
  assert.equal(gateVerdict({ cd_in_spec: true, bsm_in_spec: false }), 'hold')
})
