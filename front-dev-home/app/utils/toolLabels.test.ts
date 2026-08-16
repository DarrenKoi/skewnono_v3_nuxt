// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toolLabels } from './toolLabels.ts'

const fleet = [
  { eqp_id: 'EQP01', label: 'CD-SEM 01' },
  { eqp_id: 'EQP02', label: 'CD-SEM 02' },
  { eqp_id: 'EQP03', label: 'CD-SEM 03' },
  { eqp_id: 'EQP04', label: 'CD-SEM 04' },
  { eqp_id: 'EQP05', label: 'CD-SEM 05' }
]

test('toolLabels: labelFor returns the full label', () => {
  const { labelFor } = toolLabels(fleet)
  assert.equal(labelFor('EQP01'), 'CD-SEM 01')
  assert.equal(labelFor('EQP05'), 'CD-SEM 05')
})

test('toolLabels: an unknown id falls back to the raw id, not to empty', () => {
  const { labelFor, shortLabel } = toolLabels(fleet)
  assert.equal(labelFor('EQP99'), 'EQP99')
  assert.equal(shortLabel('EQP99'), 'EQP99')
})

test('toolLabels: shortLabel strips the shared prefix at a word boundary', () => {
  const { shortLabel } = toolLabels(fleet)
  // NOT "1" — the raw common prefix is "CD-SEM 0", and cutting there would
  // renumber the fleet. This is the case the boundary trim exists for.
  assert.equal(shortLabel('EQP01'), '01')
  assert.equal(shortLabel('EQP05'), '05')
})

test('toolLabels: shortLabel works for a non-CD-SEM family without changes', () => {
  const hv = [
    { eqp_id: 'A', label: 'HV-SEM 11' },
    { eqp_id: 'B', label: 'HV-SEM 12' }
  ]
  const { shortLabel } = toolLabels(hv)
  assert.equal(shortLabel('A'), '11')
  assert.equal(shortLabel('B'), '12')
})

test('toolLabels: labels sharing no prefix are left whole', () => {
  const mixed = [
    { eqp_id: 'A', label: 'CD-SEM 01' },
    { eqp_id: 'B', label: 'HV-SEM 11' }
  ]
  const { shortLabel } = toolLabels(mixed)
  assert.equal(shortLabel('A'), 'CD-SEM 01')
  assert.equal(shortLabel('B'), 'HV-SEM 11')
})

test('toolLabels: a single tool keeps its whole label', () => {
  const { shortLabel, labelFor } = toolLabels([{ eqp_id: 'A', label: 'CD-SEM 01' }])
  assert.equal(shortLabel('A'), 'CD-SEM 01')
  assert.equal(labelFor('A'), 'CD-SEM 01')
})

test('toolLabels: a label equal to the shared prefix never shortens to empty', () => {
  const odd = [
    { eqp_id: 'A', label: 'CD-SEM ' },
    { eqp_id: 'B', label: 'CD-SEM 02' }
  ]
  const { shortLabel } = toolLabels(odd)
  assert.equal(shortLabel('A'), 'CD-SEM ')
  assert.equal(shortLabel('B'), '02')
})

test('toolLabels: an empty fleet answers with the id', () => {
  const { labelFor, shortLabel } = toolLabels([])
  assert.equal(labelFor('EQP01'), 'EQP01')
  assert.equal(shortLabel('EQP01'), 'EQP01')
})

test('toolLabels: labels with no space are returned whole', () => {
  const nospace = [
    { eqp_id: 'A', label: 'SEM01' },
    { eqp_id: 'B', label: 'SEM02' }
  ]
  const { shortLabel } = toolLabels(nospace)
  assert.equal(shortLabel('A'), 'SEM01')
  assert.equal(shortLabel('B'), 'SEM02')
})
