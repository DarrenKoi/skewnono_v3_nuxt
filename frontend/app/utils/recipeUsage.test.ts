// Run: node --test app/utils/recipeUsage.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { RecipeUsageCatalogRow, RecipeUsageRankingRow } from '../composables/useRecipeUsageApi.ts'
import {
  clampDateRange,
  filterRecipeCatalog,
  rankRecipeFails,
  sortRecipeCatalog
} from './recipeUsage.ts'

const catalogRow = (recipe_id: string, over: Partial<RecipeUsageCatalogRow> = {}): RecipeUsageCatalogRow => ({
  recipe_id,
  fab_name: 'M14',
  product_id: '',
  layer_id: '',
  recipe_name: '',
  eqp_ids: ['EQP1'],
  n_uses: 1,
  first_used: '2026-08-01 09:00:00',
  last_used: '2026-11-01 09:00:00',
  source: 'both',
  ...over
})

const ids = (rows: { recipe_id: string }[]) => rows.map(row => row.recipe_id)

const CATALOG = [
  catalogRow('PRD/DRAM_A/GATE/JOB01', { source: 'mes', n_uses: 40, last_used: '2026-11-10 08:00:00' }),
  catalogRow('PRD/DRAM_B/GATE/JOB02', { source: 'both', n_uses: 7, last_used: '2026-11-11 23:10:00' }),
  catalogRow('ENG/NAND_A/ACT/JOB03', {
    source: 'tool', n_uses: 0, first_used: null, last_used: null, eqp_ids: ['EQP1', 'EQP2', 'EQP3']
  })
]

test('every space-separated token must match, in any order and any case', () => {
  assert.deepEqual(ids(filterRecipeCatalog(CATALOG, 'gate dram')), [
    'PRD/DRAM_A/GATE/JOB01',
    'PRD/DRAM_B/GATE/JOB02'
  ])
  assert.deepEqual(ids(filterRecipeCatalog(CATALOG, '  JOB02   prd ')), ['PRD/DRAM_B/GATE/JOB02'])
  assert.deepEqual(ids(filterRecipeCatalog(CATALOG, 'gate nand')), [])
})

test('an empty query keeps every row, and the source filter narrows it', () => {
  assert.equal(filterRecipeCatalog(CATALOG, '').length, 3)
  assert.deepEqual(ids(filterRecipeCatalog(CATALOG, '', 'tool')), ['ENG/NAND_A/ACT/JOB03'])
  assert.deepEqual(ids(filterRecipeCatalog(CATALOG, 'dram', 'mes')), ['PRD/DRAM_A/GATE/JOB01'])
})

test('a recipe that was never used sorts last in both directions', () => {
  assert.deepEqual(ids(sortRecipeCatalog(CATALOG, 'last_used', true)), [
    'PRD/DRAM_B/GATE/JOB02',
    'PRD/DRAM_A/GATE/JOB01',
    'ENG/NAND_A/ACT/JOB03'
  ])
  assert.deepEqual(ids(sortRecipeCatalog(CATALOG, 'last_used', false)), [
    'PRD/DRAM_A/GATE/JOB01',
    'PRD/DRAM_B/GATE/JOB02',
    'ENG/NAND_A/ACT/JOB03'
  ])
})

test('the catalogue sorts by use count and by tool count', () => {
  assert.deepEqual(ids(sortRecipeCatalog(CATALOG, 'n_uses', true)), [
    'PRD/DRAM_A/GATE/JOB01',
    'PRD/DRAM_B/GATE/JOB02',
    'ENG/NAND_A/ACT/JOB03'
  ])
  assert.deepEqual(ids(sortRecipeCatalog(CATALOG, 'tool_count', true)), [
    'ENG/NAND_A/ACT/JOB03',
    'PRD/DRAM_A/GATE/JOB01',
    'PRD/DRAM_B/GATE/JOB02'
  ])
})

const rankingRow = (recipe_id: string, runs: number, fail_runs: number): RecipeUsageRankingRow => ({
  recipe_id,
  runs,
  wafers: runs,
  meas_min: runs * 10,
  avg_meas_min: 10,
  fail_runs,
  fail_rate: runs ? fail_runs / runs : 0,
  eqp_ids: ['EQP1'],
  fab_names: ['M14'],
  last_start: '2026-11-11 10:00:00'
})

test('fails rank by count, then by rate, and a clean recipe is left out', () => {
  const ranked = rankRecipeFails([
    rankingRow('CLEAN', 50, 0),
    rankingRow('TWO_OF_100', 100, 2),
    rankingRow('TWO_OF_10', 10, 2),
    rankingRow('NINE_OF_30', 30, 9)
  ])
  assert.deepEqual(ids(ranked), ['NINE_OF_30', 'TWO_OF_10', 'TWO_OF_100'])
})

test('one failed run out of one does not lead its tie on rate', () => {
  const ranked = rankRecipeFails([
    rankingRow('ONE_OF_ONE', 1, 1),
    rankingRow('ONE_OF_20', 20, 1)
  ], 5)
  assert.deepEqual(ids(ranked), ['ONE_OF_20', 'ONE_OF_ONE'])
  assert.deepEqual(
    ranked.map(row => [row.low_sample, row.fail_rate_ranked, row.fail_rate]),
    [[false, 0.05, 0.05], [true, 0, 1]]
  )
})

test('a date range is pulled inside the loaded window', () => {
  assert.deepEqual(
    clampDateRange({ start: '2026-07-01', end: '2026-11-30' }, '2026-08-14', '2026-11-11'),
    { start: '2026-08-14', end: '2026-11-11' }
  )
  assert.deepEqual(
    clampDateRange({ start: '2026-10-01', end: '2026-10-14' }, '2026-08-14', '2026-11-11'),
    { start: '2026-10-01', end: '2026-10-14' }
  )
  assert.deepEqual(
    clampDateRange({ start: '2026-10-01', end: '2026-12-01' }, null, null),
    { start: '2026-10-01', end: '2026-12-01' }
  )
})
