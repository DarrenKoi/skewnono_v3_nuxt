// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupReadyRowsByVersion, UNKNOWN_VERSION_KEY } from './lateralVersionGroups.ts'
import type { LateralRecipeRow, LateralRecipeVersion } from '~/composables/useLateralRecipeApi'

const tool = (
  eqp_id: string,
  recipe_version: number | null,
  recipe_ready = true,
  recipe_generated_at: string | null = null
): LateralRecipeRow => ({
  eqp_id,
  eqp_model_cd: 'CG6300',
  vendor_nm: 'HITACHI',
  available: 'On',
  recipe_ready,
  recipe_version,
  recipe_generated_at
})

const version = (recipe_version: number, generated_at: string, ready_count: number): LateralRecipeVersion => ({
  recipe_version,
  generated_at,
  ready_count
})

const VERSIONS = [
  version(3, '2026-07-20T09:00:00+09:00', 1),
  version(2, '2026-07-10T09:00:00+09:00', 2),
  version(1, '2026-06-01T09:00:00+09:00', 0)
]

test('splits ready tools into one group per version, latest first', () => {
  const groups = groupReadyRowsByVersion(
    [tool('ECDX200', 2), tool('ECDX100', 3), tool('ECDX300', 2)],
    VERSIONS
  )

  assert.deepEqual(groups.map(g => g.version), [3, 2])
  assert.deepEqual(groups[0]?.rows.map(r => r.eqp_id), ['ECDX100'])
  assert.deepEqual(groups[1]?.rows.map(r => r.eqp_id), ['ECDX200', 'ECDX300'])
})

test('takes generated_at from the version metadata', () => {
  const groups = groupReadyRowsByVersion([tool('ECDX100', 2)], VERSIONS)

  assert.equal(groups[0]?.generatedAt, '2026-07-10T09:00:00+09:00')
})

test('backfills generated_at from a row when versions[] omits the revision', () => {
  const groups = groupReadyRowsByVersion([tool('ECDX100', 9, true, '2026-07-21T08:00:00+09:00')], VERSIONS)

  assert.equal(groups[0]?.version, 9)
  assert.equal(groups[0]?.generatedAt, '2026-07-21T08:00:00+09:00')
})

test('drops not-ready tools — those belong to the 미보유 tab', () => {
  const groups = groupReadyRowsByVersion(
    [tool('ECDX100', 3), tool('ECDX200', null, false)],
    VERSIONS
  )

  assert.equal(groups.length, 1)
  assert.deepEqual(groups[0]?.rows.map(r => r.eqp_id), ['ECDX100'])
})

test('a version with no holder produces no group at all', () => {
  const groups = groupReadyRowsByVersion([tool('ECDX100', 3)], VERSIONS)

  assert.deepEqual(groups.map(g => g.version), [3])
})

test('sinks version-less ready tools into a trailing unknown group', () => {
  const groups = groupReadyRowsByVersion(
    [tool('ECDX900', null), tool('ECDX100', 2)],
    VERSIONS
  )

  assert.deepEqual(groups.map(g => g.key), ['2', UNKNOWN_VERSION_KEY])
  assert.equal(groups[1]?.generatedAt, null)
})

test('returns nothing for an empty fleet', () => {
  assert.deepEqual(groupReadyRowsByVersion([], VERSIONS), [])
})
