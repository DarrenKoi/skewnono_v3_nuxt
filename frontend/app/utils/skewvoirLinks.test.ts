// Run: node --test app/utils/skewvoirLinks.test.ts
import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { MeasHistRow } from '../composables/useMeasHistApi.ts'
import {
  hasSkewvoir,
  measHistRowToSelection,
  skewvoirAnalysisRouteForRow,
  skewvoirSearchRoute
} from './skewvoirLinks.ts'
import { parseMsrList, parseScope, parseSelection } from './skewvoirAnalysis/routeQuery.ts'

const row: MeasHistRow = {
  id: 'measurement-1',
  fac_id: 'R3',
  fab_name: 'R3',
  vendor_nm: 'HITACHI',
  eqp_id: 'ECXDX925',
  eqp_ip: '192.0.2.1',
  eqp_model_cd: 'CG6300',
  tool_type: 'cd-sem',
  lot_cd: 'LOT001',
  lot_id: 'LOT001-01',
  class_name: 'ADI',
  recipe_name: 'ADI_CD_BIAS_001',
  full_name: 'ADI/ADI_CD_BIAS_001',
  timestamp: '2026-10-06T10:00:00',
  start_time: '2026-10-06T09:59:00',
  end_time: '2026-10-06T10:00:00',
  meastime: 60,
  msr: 'msr-1234567890',
  msr_check: 'Yes',
  align_fail: 'Pass',
  total_images: 10,
  fail_images: 0,
  fail_ratio: 0,
  idp_name: 'ADI_CD_BIAS_001.idp',
  idw_name: 'LOT001.idw'
}

test('builds eq + recipe tokens and an uppercase fab', () => {
  assert.deepEqual(
    skewvoirSearchRoute('cd-sem', { eq: ' ECXDX925 ', recipe: 'ADI/ADI_CD_BIAS_001', fab: 'r3' }),
    { path: '/ebeam/cd-sem/skewvoir', query: { q: 'eq:ECXDX925 recipe:ADI/ADI_CD_BIAS_001', fab: 'R3' } }
  )
})

test('omits absent parts so the URL stays clean', () => {
  assert.deepEqual(skewvoirSearchRoute('hv-sem', { eq: 'TP001' }), {
    path: '/ebeam/hv-sem/skewvoir', query: { q: 'eq:TP001' }
  })
  assert.deepEqual(skewvoirSearchRoute('hv-sem', {}).query, {})
})

test('only the two SEM families have 스큐보아', () => {
  assert.equal(hasSkewvoir('cd-sem'), true)
  assert.equal(hasSkewvoir('provision'), false)
})

test('maps a measurement row to the selection used by search and analysis links', () => {
  assert.deepEqual(measHistRowToSelection(row), {
    lot: 'LOT001-01',
    recipe: 'ADI_CD_BIAS_001',
    eq: 'ECXDX925',
    mp: 'WAFER',
    msr: 'msr-1234567890',
    capturedAt: '2026-10-06T10:00:00'
  })
})

test('analysis links round-trip the measurement identity and capture timestamp', () => {
  const route = skewvoirAnalysisRouteForRow('cd-sem', row)
  assert.ok(route)
  assert.deepEqual(parseSelection(route.query), {
    lot: 'LOT001-01',
    recipe: 'ADI_CD_BIAS_001',
    eq: 'ECXDX925',
    mp: 'WAFER',
    msr: 'msr-1234567890',
    capturedAt: '2026-10-06T10:00:00'
  })
})

test('analysis links reject empty and whitespace-only MSR ids', () => {
  for (const msr of ['', '   ', '\t\n']) {
    assert.equal(skewvoirAnalysisRouteForRow('cd-sem', { ...row, msr }), null)
  }
})

test('analysis links keep slashes in recipe names verbatim', () => {
  const route = skewvoirAnalysisRouteForRow('cd-sem', { ...row, recipe_name: 'ADI/ADI_CD_BIAS_001' })
  assert.ok(route)
  assert.equal(route.query.recipe, 'ADI/ADI_CD_BIAS_001')
  assert.equal(parseSelection(route.query)?.recipe, 'ADI/ADI_CD_BIAS_001')
})

test('analysis links use the requested SEM family path', () => {
  assert.equal(skewvoirAnalysisRouteForRow('cd-sem', row)?.path, '/ebeam/cd-sem/skewvoir/analysis')
  assert.equal(skewvoirAnalysisRouteForRow('hv-sem', { ...row, tool_type: 'hv-sem' })?.path, '/ebeam/hv-sem/skewvoir/analysis')
})

test('analysis links reject tool families without skewvoir', () => {
  assert.equal(skewvoirAnalysisRouteForRow('provision', row), null)
})

test('analysis links read back as a single-MSR selection', () => {
  const route = skewvoirAnalysisRouteForRow('cd-sem', row)
  assert.ok(route)
  assert.equal(route.query.msrs, 'msr-1234567890')
  assert.deepEqual(parseMsrList(route.query), ['msr-1234567890'])
  assert.equal(parseScope(route.query), 'single')
})
