// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildCascadedOptions, pruneCascadedFilters } from './measHistCascade.ts'
import type { SemListRow } from '~/composables/useSemListApi'

const sem = (eqp_id: string, eqp_model_cd: string, fab_name: string): SemListRow => ({
  fac_id: fab_name.startsWith('R') ? 'R3' : 'M16',
  eqp_id,
  eqp_model_cd,
  eqp_grp_id: 'GRP',
  // CD-SEM (CG/GT) and HV-SEM (TP) are both Hitachi; AMAT is VerityCEM and
  // Provision only, neither of which appears in this fleet.
  vendor_nm: eqp_model_cd.startsWith('VERITYSEM') || eqp_model_cd.startsWith('PROVISION')
    ? 'AMAT'
    : 'HITACHI',
  eqp_ip: '10.0.0.1',
  fab_name,
  updt_dt: '2026-07-01',
  available: 'On',
  version: '1A'
})

// Fleet: R3 has CD-SEM (CG6300) + HV-SEM (TP3000); M16A is CD-SEM only.
const FLEET = [
  sem('ECDX100', 'CG6300', 'R3'),
  sem('ECDX200', 'CG6360', 'M16A'),
  sem('PCD300', 'TP3000', 'R3')
]

const FACETS = {
  model: [
    { value: 'CG6300', count: 50 },
    { value: 'CG6360', count: 30 },
    { value: 'TP3000', count: 20 }
  ],
  eq: [
    { value: 'ECDX100', count: 50 },
    { value: 'ECDX200', count: 30 },
    { value: 'PCD300', count: 20 },
    // Retired tool: inside retention but no longer in sem_list.
    { value: 'ECDX999', count: 5 }
  ]
}

const NO_PICKS = { fab: [], category: [], model: [] }

test('no picks: everything offered, category counts sum model doc counts', () => {
  const r = buildCascadedOptions(FACETS, FLEET, NO_PICKS)
  assert.deepEqual(r.category, [
    { value: 'CD-SEM', count: 80 },
    { value: 'HV-SEM', count: 20 }
  ])
  assert.deepEqual(r.model.map(o => o.value), ['CG6300', 'CG6360', 'TP3000'])
  // Retired ECDX999 stays offered while no pick requires mapping it.
  assert.deepEqual(r.eq.map(o => o.value), ['ECDX100', 'ECDX200', 'PCD300', 'ECDX999'])
})

test('category pick narrows models statically and eqs via the fleet', () => {
  const r = buildCascadedOptions(FACETS, FLEET, { ...NO_PICKS, category: ['CD-SEM'] })
  assert.deepEqual(r.model.map(o => o.value), ['CG6300', 'CG6360'])
  // ECDX999 is unmapped -> dropped once a pick requires the fleet join.
  assert.deepEqual(r.eq.map(o => o.value), ['ECDX100', 'ECDX200'])
})

test('both categories picked behaves like a family-complete pick', () => {
  const r = buildCascadedOptions(FACETS, FLEET, { ...NO_PICKS, category: ['CD-SEM', 'HV-SEM'] })
  assert.deepEqual(r.model.map(o => o.value), ['CG6300', 'CG6360', 'TP3000'])
  assert.deepEqual(r.eq.map(o => o.value), ['ECDX100', 'ECDX200', 'PCD300'])
})

test('fab pick narrows models and eqs through sem_list', () => {
  const r = buildCascadedOptions(FACETS, FLEET, { ...NO_PICKS, fab: ['R3'] })
  assert.deepEqual(r.model.map(o => o.value), ['CG6300', 'TP3000'])
  assert.deepEqual(r.eq.map(o => o.value), ['ECDX100', 'PCD300'])
})

test('fab + category compose', () => {
  const r = buildCascadedOptions(FACETS, FLEET, { fab: ['R3'], category: ['CD-SEM'], model: [] })
  assert.deepEqual(r.model.map(o => o.value), ['CG6300'])
  assert.deepEqual(r.eq.map(o => o.value), ['ECDX100'])
})

test('model pick narrows eq', () => {
  const r = buildCascadedOptions(FACETS, FLEET, { ...NO_PICKS, model: ['CG6360'] })
  assert.deepEqual(r.eq.map(o => o.value), ['ECDX200'])
})

test('empty sem_list skips fleet constraints but keeps the static category rule', () => {
  const r = buildCascadedOptions(FACETS, [], { fab: ['R3'], category: ['HV-SEM'], model: [] })
  // fab constraint unenforceable -> skipped; category rule still applies to models.
  assert.deepEqual(r.model.map(o => o.value), ['TP3000'])
  // eq cannot be mapped at all without the fleet -> left un-narrowed.
  assert.deepEqual(r.eq.map(o => o.value), ['ECDX100', 'ECDX200', 'PCD300', 'ECDX999'])
  // Both categories stay offered even when the fleet table is empty.
  assert.deepEqual(r.category.map(o => o.value), ['CD-SEM', 'HV-SEM'])
})

test('prune drops picks the narrowed options no longer offer', () => {
  const options = buildCascadedOptions(FACETS, FLEET, { ...NO_PICKS, category: ['HV-SEM'] })
  const filters = { fab: [], category: ['HV-SEM'], model: ['CG6300'], eq: ['ECDX100', 'PCD300'], from: '', to: '' }
  const pruned = pruneCascadedFilters(filters, options)
  assert.ok(pruned)
  assert.deepEqual(pruned.model, [])
  assert.deepEqual(pruned.eq, ['PCD300'])
  // Untouched fields survive the spread.
  assert.deepEqual(pruned.category, ['HV-SEM'])
})

test('prune returns null when nothing changed', () => {
  const options = buildCascadedOptions(FACETS, FLEET, NO_PICKS)
  const filters = { fab: [], category: [], model: ['CG6300'], eq: ['ECDX999'], from: '', to: '' }
  assert.equal(pruneCascadedFilters(filters, options), null)
})
