// Pure-logic tests for ruleMatrix (D13 presentation helpers).
// Run: node --test app/utils/ruleMatrix.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CAP_COLUMNS, fixedCaps, familyLabel, vehicleLabel, isExpandedCell,
  memoryOf, capValue, collectOverrides, overrideLabel
} from './ruleMatrix.ts'
import type { NameOverride, RuleCell } from './ruleEngine.ts'

// --- fixtures ---
// R3 Core, EV-and-earlier, DRAM — the matrix baseline row.
const cell = (over: Partial<RuleCell> = {}): RuleCell => ({
  id: 'r3-core-ev-dram',
  selector: {
    fab: 'R3', recipe_class: 'Main', family: 'Core',
    phase_in: ['t-EV', 'EV'], memory_class: 'DRAM'
  },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [],
  ...over
})

const wfOverride: NameOverride = { patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains', cap: 13 }
const exemptOverride: NameOverride = { patterns: ['WAFER', 'WF'], match: 'affix', cap: null }

// --- columns ---

test('the varying cap columns are EDGE, EDGE_EX and the OTHER bucket', () => {
  assert.deepEqual(CAP_COLUMNS.map(c => c.key), ['EDGE', 'EDGE_EX', '_other'])
  assert.equal(CAP_COLUMNS.find(c => c.key === '_other')?.label, '기타')
})

// --- fixedCaps ---

test('fixedCaps lifts WAFER and LEVEL out when every cell agrees', () => {
  assert.deepEqual(fixedCaps([cell(), cell({ id: 'b' }), cell({ id: 'c' })]), [
    { key: 'WAFER', value: 13 },
    { key: 'LEVEL', value: 4 }
  ])
})

test('fixedCaps drops a key that diverges anywhere, so a per-cell split is never masked', () => {
  const split = cell({ id: 'split', caps: { WAFER: 26, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 } })
  assert.deepEqual(fixedCaps([cell(), split]), [{ key: 'LEVEL', value: 4 }])
})

test('fixedCaps keeps a uniform zero (a falsy cap is still a cap)', () => {
  const zeroLevel = (id: string) =>
    cell({ id, caps: { WAFER: 13, LEVEL: 0, EDGE: 10, EDGE_EX: 0, _other: 9 } })
  assert.deepEqual(fixedCaps([zeroLevel('a'), zeroLevel('b')]), [
    { key: 'WAFER', value: 13 },
    { key: 'LEVEL', value: 0 }
  ])
})

test('fixedCaps skips a key the first cell does not carry', () => {
  const noWafer = cell({ id: 'no-wafer', caps: { LEVEL: 4, EDGE: 10, _other: 9 } })
  assert.deepEqual(fixedCaps([noWafer, cell()]), [{ key: 'LEVEL', value: 4 }])
})

test('fixedCaps on no cells yields no strip', () => {
  assert.deepEqual(fixedCaps([]), [])
})

// --- familyLabel ---

test('familyLabel prettifies the compound family and passes others through', () => {
  assert.equal(familyLabel('VG_RTC_Cubic'), 'VG·RTC·Cubic')
  assert.equal(familyLabel('Core'), 'Core')
  assert.equal(familyLabel('Pool'), 'Pool')
  assert.equal(familyLabel('SomethingNew'), 'SomethingNew')
})

test('familyLabel renders a missing family as empty, not "undefined"', () => {
  assert.equal(familyLabel(undefined), '')
  assert.equal(familyLabel(''), '')
})

// --- vehicleLabel ---

test('vehicleLabel collapses a Core phase set to EV or TV', () => {
  assert.deepEqual(vehicleLabel(cell()), { main: 'EV', hint: '포함 이전' })
  assert.deepEqual(
    vehicleLabel(cell({ selector: { fab: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['TV', 'PV'] } })),
    { main: 'TV', hint: '포함 이후' }
  )
})

test('vehicleLabel reads PV alone as TV-and-after', () => {
  const pvOnly = cell({ selector: { fab: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['PV'] } })
  assert.deepEqual(vehicleLabel(pvOnly), { main: 'TV', hint: '포함 이후' })
})

test('vehicleLabel keeps the Pool yield split', () => {
  const pool = (yieldCheck: 'before' | 'after') => cell({
    selector: { fab: 'R3', recipe_class: 'Main', family: 'Pool', yield_check: yieldCheck }
  })
  assert.deepEqual(vehicleLabel(pool('before')), { main: '수율 전' })
  assert.deepEqual(vehicleLabel(pool('after')), { main: '수율 후' })
})

test('vehicleLabel prefers the phase set when a cell carries both axes', () => {
  const both = cell({
    selector: { fab: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['TV'], yield_check: 'before' }
  })
  assert.deepEqual(vehicleLabel(both), { main: 'TV', hint: '포함 이후' })
})

test('vehicleLabel is blank when neither axis keys the cell (Sample)', () => {
  assert.deepEqual(
    vehicleLabel(cell({ selector: { fab: 'R3', recipe_class: 'Sample', memory_class: 'DRAM' } })),
    { main: '' }
  )
  // An empty phase_in array must fall through rather than claim EV.
  assert.deepEqual(
    vehicleLabel(cell({ selector: { fab: 'R3', recipe_class: 'Main', family: 'Core', phase_in: [] } })),
    { main: '' }
  )
})

// --- isExpandedCell ---

test('isExpandedCell highlights the phases and yield state that open the caps', () => {
  const sel = (over: Partial<RuleCell['selector']>): RuleCell =>
    cell({ selector: { fab: 'R3', recipe_class: 'Main', family: 'Core', ...over } })
  assert.equal(isExpandedCell(sel({ phase_in: ['TV', 'PV'] })), true)
  assert.equal(isExpandedCell(sel({ phase_in: ['PV'] })), true)
  assert.equal(isExpandedCell(sel({ phase_in: ['t-EV', 'EV'] })), false)
  assert.equal(isExpandedCell(sel({ yield_check: 'after' })), true)
  assert.equal(isExpandedCell(sel({ yield_check: 'before' })), false)
  assert.equal(isExpandedCell(sel({})), false)
})

// --- memoryOf ---

test('memoryOf returns the split class, or null for an unsplit cell', () => {
  assert.equal(memoryOf(cell()), 'DRAM')
  assert.equal(memoryOf(cell({ selector: { fab: 'R3', recipe_class: 'Main', memory_class: 'NAND' } })), 'NAND')
  assert.equal(memoryOf(cell({ selector: { fab: 'R3', recipe_class: 'Main' } })), null)
})

// --- capValue ---

test('capValue reads each column, including a zero cap', () => {
  assert.equal(capValue(cell(), 'EDGE'), 10)
  assert.equal(capValue(cell(), 'EDGE_EX'), 0) // 0 must survive, not read as "n/a"
  assert.equal(capValue(cell(), '_other'), 9)
})

test('capValue is undefined for a cap type that does not apply to the cell', () => {
  const noEdgeEx = cell({ caps: { WAFER: 13, LEVEL: 4, EDGE: 10, _other: 9 } })
  assert.equal(capValue(noEdgeEx, 'EDGE_EX'), undefined)
})

// --- collectOverrides ---

test('collectOverrides de-duplicates identical overrides across cells', () => {
  const cells = [cell({ name_overrides: [wfOverride] }), cell({ id: 'b', name_overrides: [wfOverride] })]
  assert.deepEqual(collectOverrides(cells), [wfOverride])
})

test('collectOverrides keeps distinct overrides in first-seen order', () => {
  const cells = [
    cell({ name_overrides: [wfOverride] }),
    cell({ id: 'b', name_overrides: [exemptOverride, wfOverride] })
  ]
  assert.deepEqual(collectOverrides(cells), [wfOverride, exemptOverride])
})

test('collectOverrides yields nothing when no cell carries one', () => {
  assert.deepEqual(collectOverrides([cell(), cell({ id: 'b' })]), [])
  assert.deepEqual(collectOverrides([]), [])
})

// --- overrideLabel ---

test('overrideLabel summarises patterns, match mode and target cap', () => {
  assert.equal(overrideLabel(wfOverride), 'DSPT | WF | WAFER (contains) → cap 13')
  assert.equal(overrideLabel(exemptOverride), 'WAFER | WF (affix) → 면제')
})

test('overrideLabel shows a zero cap as a cap, not as an exemption', () => {
  // Only `cap === null` means 면제 — cap 0 is "no points allowed".
  assert.equal(
    overrideLabel({ patterns: ['WF'], match: 'contains', cap: 0 }),
    'WF (contains) → cap 0'
  )
})
