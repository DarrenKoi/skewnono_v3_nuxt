import assert from 'node:assert/strict'
import test from 'node:test'
import type { MeasHistRow } from '../composables/useMeasHistApi.ts'
import {
  addMeasHistSelection,
  hasMsrIdentity,
  measHistRowKey,
  removeMeasHistSelection,
  setMeasHistSelections,
  toggleMeasHistSelection
} from './measHistSelection.ts'

const row = (msr: string, recipeName: string): MeasHistRow => ({
  id: msr,
  fac_id: 'M11',
  fab_name: 'M11A',
  vendor_nm: 'HITACHI',
  eqp_id: 'ECXDX925',
  eqp_ip: '10.41.12.87',
  eqp_model_cd: 'CG6300',
  tool_type: 'cd-sem',
  lot_cd: '6LD257421',
  lot_id: '6LD257421',
  class_name: 'CD',
  recipe_name: recipeName,
  full_name: `M11A/${recipeName}`,
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

test('adds selections from separate search result sets without dropping earlier rows', () => {
  const firstSearch = row('MSR-001', 'ADI_CD_BIAS_001')
  const secondSearch = row('MSR-002', 'AEI_GATE_002')

  const selected = addMeasHistSelection(
    addMeasHistSelection([], firstSearch),
    secondSearch
  )

  assert.deepEqual(selected.map(item => item.msr), ['MSR-001', 'MSR-002'])
})

test('deduplicates by MSR and keeps the newest row payload', () => {
  const original = row('MSR-001', 'OLD_RECIPE')
  const refreshed = row('MSR-001', 'CURRENT_RECIPE')

  const selected = addMeasHistSelection([original], refreshed)

  assert.equal(selected.length, 1)
  assert.equal(selected[0]?.recipe_name, 'CURRENT_RECIPE')
})

test('toggle and remove only affect the chosen MSR', () => {
  const first = row('MSR-001', 'ADI_CD_BIAS_001')
  const second = row('MSR-002', 'AEI_GATE_002')
  const selected = [first, second]

  assert.deepEqual(toggleMeasHistSelection(selected, first), [second])
  assert.deepEqual(removeMeasHistSelection(selected, 'MSR-002'), [first])
})

test('selecting every row in a new result set preserves earlier selections', () => {
  const earlier = row('MSR-001', 'EARLIER_SEARCH')
  const current = [
    row('MSR-002', 'CURRENT_SEARCH_A'),
    row('MSR-003', 'CURRENT_SEARCH_B')
  ]

  const selected = setMeasHistSelections([earlier], current, true)
  assert.deepEqual(selected.map(item => item.msr), ['MSR-001', 'MSR-002', 'MSR-003'])

  const clearedCurrent = setMeasHistSelections(selected, current, false)
  assert.deepEqual(clearedCurrent, [earlier])
})

// --- msr-less rows (office value domain: msr_check "No" 문서에는 msr 필드가
// 없어 어댑터의 _text() 가 '' 를 내보냅니다) ---

test('hasMsrIdentity rejects blank and whitespace msr values', () => {
  assert.equal(hasMsrIdentity(row('MSR-001', 'ADI_CD_BIAS_001')), true)
  assert.equal(hasMsrIdentity(row('', 'ADI_CD_BIAS_001')), false)
  assert.equal(hasMsrIdentity(row('   ', 'ADI_CD_BIAS_001')), false)
})

test('measHistRowKey keeps the msr as key and never collides for msr-less rows', () => {
  const real = row('MSR-001', 'ADI_CD_BIAS_001')
  assert.equal(measHistRowKey(real, 0), 'MSR-001')

  const a = { ...row('', 'ADI_CD_BIAS_001'), timestamp: '2026-05-09T12:00:00' }
  const b = { ...row('', 'ADI_CD_BIAS_001'), timestamp: '2026-05-09T12:00:00' }
  const keyA = measHistRowKey(a, 3)
  const keyB = measHistRowKey(b, 4)
  assert.notEqual(keyA, keyB)
  assert.notEqual(keyA, '')
})

// Regression (2026-08-20): the office reported every 검색 결과 row dead while
// MinIO held the data. msr_check must never be what disables a row -- the
// office adapter maps EVERY unrecognized value to "No" (providers/
// office_example.py `_text(src.get("msr_check")).lower() == "yes"`), so one
// unexpected value shape blanks the whole table with no error anywhere.
// Opening needs the msr and nothing else; a measurement whose raw data really
// is missing renders an empty analysis screen, which is the recoverable error.
test('msr_check never decides whether a row can be opened', () => {
  const fileMissing = { ...row('MSR-002', 'ADI_CD_BIAS_001'), msr_check: 'No' as const }
  assert.equal(hasMsrIdentity(fileMissing), true)
  assert.deepEqual(addMeasHistSelection([], fileMissing), [fileMissing])
  assert.deepEqual(toggleMeasHistSelection([], fileMissing), [fileMissing])
})
