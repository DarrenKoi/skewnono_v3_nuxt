import assert from 'node:assert/strict'
import test from 'node:test'
import {
  addSkewvoirRecentItem,
  buildSkewvoirRecentItem,
  normalizeSkewvoirRecentItems,
  type SkewvoirRecentMeasurement
} from './skewvoirRecent.ts'

const measurement = (msr: string, recipe: string): SkewvoirRecentMeasurement => ({
  msr,
  lot: `LOT-${msr}`,
  recipe,
  eq: 'ECXDX925',
  fab: 'M11A',
  capturedAt: '2026-05-09T12:00:00'
})

test('builds distinct single and Time-Series recent entries', () => {
  const first = measurement('MSR-001', 'M11A/ADI_CD_BIAS_001')
  const second = measurement('MSR-002', 'M11A/AEI_GATE_002')

  const single = buildSkewvoirRecentItem('cd-sem', 'single', [first], '2026-05-10T01:00:00Z')
  const grouped = buildSkewvoirRecentItem('cd-sem', 'time-series', [first, second], '2026-05-10T02:00:00Z')

  assert.equal(single?.mode, 'single')
  assert.deepEqual(single?.measurements.map(item => item.msr), ['MSR-001'])
  assert.equal(grouped?.mode, 'time-series')
  assert.deepEqual(grouped?.measurements.map(item => item.msr), ['MSR-001', 'MSR-002'])
})

test('the same grouped selection is deduplicated regardless of member order', () => {
  const first = measurement('MSR-001', 'M11A/ADI_CD_BIAS_001')
  const second = measurement('MSR-002', 'M11A/AEI_GATE_002')
  const oldEntry = buildSkewvoirRecentItem('cd-sem', 'time-series', [first, second], '2026-05-10T01:00:00Z')!
  const newEntry = buildSkewvoirRecentItem('cd-sem', 'time-series', [second, first], '2026-05-10T02:00:00Z')!
  const otherEntry = buildSkewvoirRecentItem('cd-sem', 'single', [first], '2026-05-10T01:30:00Z')!

  const items = addSkewvoirRecentItem([otherEntry, oldEntry], newEntry, 15)

  assert.equal(items.length, 2)
  assert.equal(items[0]?.id, newEntry.id)
  assert.equal(items[0]?.viewedAt, '2026-05-10T02:00:00Z')
  assert.deepEqual(items[0]?.measurements.map(item => item.msr), ['MSR-002', 'MSR-001'])
})

test('migrates existing single-measurement localStorage records', () => {
  const items = normalizeSkewvoirRecentItems([{
    msr: 'MSR-LEGACY',
    toolType: 'hv-sem',
    lot: 'RKPB240012',
    recipe: 'M14B/INLINE_CD_002',
    eq: 'MCD018',
    fab: 'M14B',
    capturedAt: '2026-05-08T10:00:00',
    viewedAt: '2026-05-09T10:00:00Z'
  }])

  assert.equal(items.length, 1)
  assert.equal(items[0]?.mode, 'single')
  assert.equal(items[0]?.measurements[0]?.msr, 'MSR-LEGACY')
})
