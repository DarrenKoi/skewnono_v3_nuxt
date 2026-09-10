import assert from 'node:assert/strict'
import test from 'node:test'
import type { MeasHistRow } from '../composables/useMeasHistApi.ts'
import type { ParsedQuery } from './measHistQuery.ts'
import {
  buildSearchScopeSummary,
  summarizeRecentValues,
  summarizeSelectionCoverage
} from './skewvoirSearchUi.ts'

const parsed: ParsedQuery = {
  eq: [],
  lot: [],
  recipe: [],
  msr: [],
  date: [],
  q: ['ECXDX'],
  unknown: []
}

const row = (msr: string, recipe: string, lot: string, eq: string): MeasHistRow => ({
  id: msr,
  fac_id: 'M11',
  fab_name: 'M11A',
  vendor_nm: 'HITACHI',
  eqp_id: eq,
  eqp_ip: '10.41.12.87',
  eqp_model_cd: 'CG6300',
  tool_type: 'cd-sem',
  lot_cd: lot,
  lot_id: lot,
  class_name: 'CD',
  recipe_name: recipe,
  full_name: `M11A/${recipe}`,
  timestamp: '2026-05-09T12:00:00',
  start_time: '2026-05-09T12:00:00',
  end_time: '2026-05-09T12:01:00',
  meastime: 60,
  msr,
  msr_check: 'Yes',
  align_fail: 'Pass',
  total_images: 10,
  fail_images: 0,
  fail_ratio: 0,
  idp_name: 'IDP',
  idw_name: 'IDW'
})

test('search scope exposes parsed fallback, effective range, retention, and hits', () => {
  assert.deepEqual(buildSearchScopeSummary({
    parsed,
    range: { start: '2026-04-10', end: '2026-05-09' },
    retentionDays: 60,
    searched: true,
    total: 129,
    capped: false
  }), [
    { label: 'ANY', value: 'ECXDX' },
    { label: 'RANGE', value: '2026-04-10 → 2026-05-09' },
    { label: 'RETENTION', value: '60일' },
    { label: 'HITS', value: '129' }
  ])
})

test('selection coverage deduplicates recipes, lots, and equipment', () => {
  const rows = [
    row('MSR-1', 'RECIPE-A', 'LOT-1', 'EQ-1'),
    row('MSR-2', 'RECIPE-A', 'LOT-2', 'EQ-1'),
    row('MSR-3', 'RECIPE-B', 'LOT-2', 'EQ-2')
  ]

  assert.deepEqual(summarizeSelectionCoverage(rows), {
    measurements: 3,
    recipes: 2,
    lots: 2,
    equipment: 2
  })
})

test('recent value summary stays compact in a narrow rail', () => {
  assert.equal(summarizeRecentValues(['LOT-1', 'LOT-1', 'LOT-2']), 'LOT-1, LOT-2')
  assert.equal(summarizeRecentValues(['A', 'B', 'C']), 'A 외 2')
  assert.equal(summarizeRecentValues([]), '—')
})
