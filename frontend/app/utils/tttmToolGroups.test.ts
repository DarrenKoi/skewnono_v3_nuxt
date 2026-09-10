// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupToolsByModel, orderSelection } from './tttmToolGroups.ts'

const fleet = [
  { eqp_id: 'ECDX172', eqp_model_cd: 'CG6300' },
  { eqp_id: 'HCDX439', eqp_model_cd: 'GT2000S' },
  { eqp_id: 'ECDX614', eqp_model_cd: 'CG6300' },
  { eqp_id: 'ECDX261', eqp_model_cd: 'CG6360' }
]

test('groupToolsByModel: buckets by model code, groups in model order', () => {
  const groups = groupToolsByModel(fleet)
  assert.deepEqual(groups.map(g => g.model), ['CG6300', 'CG6360', 'GT2000S'])
  assert.deepEqual(groups[0]!.tools.map(t => t.eqp_id), ['ECDX172', 'ECDX614'])
})

test('groupToolsByModel: keeps fleet order inside a group', () => {
  const reversed = [...fleet].reverse()
  const groups = groupToolsByModel(reversed)
  const cg = groups.find(g => g.model === 'CG6300')!
  assert.deepEqual(cg.tools.map(t => t.eqp_id), ['ECDX614', 'ECDX172'])
})

test('groupToolsByModel: a blank model code is filed, not dropped', () => {
  // A tool the picker cannot reach is a tool that cannot be compared, so an
  // unknown model must still get a chip.
  const groups = groupToolsByModel([...fleet, { eqp_id: 'XCD001', eqp_model_cd: '  ' }])
  const other = groups.find(g => g.model === '기타')
  assert.deepEqual(other?.tools.map(t => t.eqp_id), ['XCD001'])
  assert.equal(groups.flatMap(g => g.tools).length, 5)
})

test('orderSelection: re-expresses a selection in fleet order', () => {
  const ids = fleet.map(t => t.eqp_id)
  assert.deepEqual(
    orderSelection(ids, new Set(['ECDX261', 'ECDX172'])),
    ['ECDX172', 'ECDX261']
  )
})

test('orderSelection: drops ids that are not in the fleet', () => {
  assert.deepEqual(orderSelection(['A', 'B'], new Set(['B', 'GONE'])), ['B'])
})
