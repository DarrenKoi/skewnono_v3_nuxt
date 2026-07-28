// Pure-logic tests for recipeCompare. Run: node --test app/utils/recipeCompare.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildOverlap,
  classifyCoverage,
  filterOverlap,
  commonParameters,
  buildIdpRows, buildAmpRows, cellsDiffer, imageFilenames,
  groupFieldValues,
  buildCompareWorkbook
} from './recipeCompare.ts'
import type { CompareRecipe, CompareParameter } from '../composables/useRecipeCompareApi.ts'
import type { AmpRow } from '../composables/useRecipeSearchApi.ts'

const param = (name: string): CompareParameter => ({
  Parameter: name,
  idp: {
    Addressing: true, Double_Addressing: false, Mother_Para: true,
    Region: 1, Meas_Counting: 1, dnumber_removed: false
  },
  images: { img_add1: 'a1', img_add2: 'a2', image_add3: 'a3', img_meas1: 'm1', img_meas2: 'm2' },
  amp: []
})

const recipe = (id: string, params: string[]): CompareRecipe => ({
  recipe_id: id, fac_id: 'R3', parameters: params.map(param)
})

test('classifyCoverage: all / unique / partial', () => {
  assert.equal(classifyCoverage(3, 3), 'all')
  assert.equal(classifyCoverage(1, 3), 'unique')
  assert.equal(classifyCoverage(2, 3), 'partial')
})

test('buildOverlap marks shared, partial, unique parameters', () => {
  const rows = buildOverlap([
    recipe('A', ['WAFER', 'P5', 'P8']),
    recipe('B', ['WAFER', 'P5']),
    recipe('C', ['WAFER', 'P12'])
  ])
  // `!` throughout: Object.fromEntries widens the key set to `string`, so every
  // lookup reads as possibly-undefined. The row type itself is still checked.
  const byName = Object.fromEntries(rows.map(r => [r.parameter, r]))
  assert.equal(byName.WAFER!.coverage, 'all')
  assert.deepEqual(byName.WAFER!.presentIn, ['A', 'B', 'C'])
  assert.equal(byName.P5!.coverage, 'partial')
  assert.equal(byName.P8!.coverage, 'unique')
  assert.equal(byName.P12!.coverage, 'unique')
})

test('buildOverlap dedupes a repeated parameter within one recipe', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'WAFER'])])
  assert.equal(rows.length, 1)
  assert.equal(rows[0]?.count, 1)
})

test('filterOverlap + commonParameters', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'P5']), recipe('B', ['WAFER'])])
  assert.deepEqual(filterOverlap(rows, 'common').map(r => r.parameter), ['WAFER'])
  assert.deepEqual(filterOverlap(rows, 'unique').map(r => r.parameter), ['P5'])
  assert.deepEqual(filterOverlap(rows, 'all').map(r => r.parameter), ['WAFER', 'P5'])
  assert.deepEqual(commonParameters(rows), ['WAFER'])
})

const measAmp = (over: Partial<AmpRow>): AmpRow => ({
  parameter: 'WAFER', slot: 'img_meas1', role: 'measure', stage: 'Measure 1',
  Mag: '50.0K', Vacc: '800', I_probe: '200', Frame: '8', Scan: 'TV', WD: '5.0', Det: 'SE',
  Template: null, MatchScore: null, SearchArea: null, Rotation: null,
  Algo: 'Linear', ROI: '512', EdgeThr: '50', EdgeDir: 'L->R', Smooth: 'Off', ...over
})

const recipeWithAmp = (id: string, amp: AmpRow[]): CompareRecipe => ({
  recipe_id: id, fac_id: 'R3',
  parameters: [{
    Parameter: 'WAFER',
    idp: { Addressing: true, Double_Addressing: false, Mother_Para: true, Region: 5, Meas_Counting: 3, dnumber_removed: false },
    images: { img_add1: 'a1', img_add2: 'a2', image_add3: 'a3', img_meas1: `${id}_m1`, img_meas2: 'm2' },
    amp
  }]
})

test('cellsDiffer: equal values agree, one different differs', () => {
  assert.equal(cellsDiffer(['50K', '50K', '50K']), false)
  assert.equal(cellsDiffer(['50K', '80K', '50K']), true)
  assert.equal(cellsDiffer(['x']), false)
})

test('buildAmpRows aligns values per recipe and flags differing rows', () => {
  const rows = buildAmpRows([
    recipeWithAmp('A', [measAmp({ Mag: '50.0K', Algo: 'Linear' })]),
    recipeWithAmp('B', [measAmp({ Mag: '80.0K', Algo: 'Linear' })])
  ], 'WAFER', 'img_meas1')
  const mag = rows.find(r => r.key === 'Mag')!
  const algo = rows.find(r => r.key === 'Algo')!
  assert.deepEqual(mag.values, ['50.0K', '80.0K'])
  assert.equal(mag.differs, true)
  assert.equal(algo.differs, false)
})

test('buildAmpRows shows 없음 when a recipe lacks the parameter', () => {
  const withWafer = recipeWithAmp('A', [measAmp({})])
  const without: CompareRecipe = { recipe_id: 'B', fac_id: 'R3', parameters: [] }
  const rows = buildAmpRows([withWafer, without], 'WAFER', 'img_meas1')
  assert.equal(rows.find(r => r.key === 'Mag')!.values[1], '없음')
})

test('buildIdpRows compares per-parameter fields', () => {
  const rows = buildIdpRows([
    recipeWithAmp('A', []),
    { recipe_id: 'B', fac_id: 'R3', parameters: [{
      Parameter: 'WAFER',
      idp: { Addressing: true, Double_Addressing: false, Mother_Para: true, Region: 8, Meas_Counting: 3, dnumber_removed: false },
      images: { img_add1: '', img_add2: '', image_add3: '', img_meas1: '', img_meas2: '' },
      amp: []
    }] }
  ], 'WAFER')
  assert.equal(rows.find(r => r.key === 'Region')!.differs, true)
  assert.equal(rows.find(r => r.key === 'Addressing')!.differs, false)
})

test('buildIdpRows spells booleans the way BoolPill does, not as String(true)', () => {
  const rows = buildIdpRows([recipeWithAmp('A', [])], 'WAFER')
  assert.deepEqual(rows.find(r => r.key === 'Addressing')!.values, ['True'])
  assert.deepEqual(rows.find(r => r.key === 'dnumber_removed')!.values, ['False'])
})

test('imageFilenames returns per-recipe slot filename or null', () => {
  const files = imageFilenames([
    recipeWithAmp('A', []),
    { recipe_id: 'B', fac_id: 'R3', parameters: [] }
  ], 'WAFER', 'img_meas1')
  assert.deepEqual(files, ['A_m1', null])
})

test('groupFieldValues sorts buckets by count desc', () => {
  const buckets = groupFieldValues([
    { recipeId: 'A', value: '50K' }, { recipeId: 'B', value: '80K' },
    { recipeId: 'C', value: '50K' }, { recipeId: 'D', value: '50K' }
  ])
  assert.deepEqual(buckets.map(b => b.value), ['50K', '80K'])
  assert.deepEqual(buckets[0]?.recipeIds, ['A', 'C', 'D'])
})

test('groupFieldValues flags a small minority as outlier', () => {
  const pairs = [
    ...Array.from({ length: 62 }, (_, i) => ({ recipeId: `a${i}`, value: '50K' })),
    ...Array.from({ length: 31 }, (_, i) => ({ recipeId: `b${i}`, value: '80K' })),
    ...Array.from({ length: 7 }, (_, i) => ({ recipeId: `c${i}`, value: '100K' }))
  ]
  const buckets = groupFieldValues(pairs)
  const byValue = Object.fromEntries(buckets.map(b => [b.value, b]))
  assert.equal(byValue['50K']!.isOutlier, false) // largest
  assert.equal(byValue['80K']!.isOutlier, false) // 0.31 share > 0.25
  assert.equal(byValue['100K']!.isOutlier, true) // 0.07 share <= 0.25
})

test('groupFieldValues flags nothing on a tie for largest', () => {
  const buckets = groupFieldValues([
    { recipeId: 'A', value: 'x' }, { recipeId: 'B', value: 'y' }
  ])
  assert.equal(buckets.every(b => !b.isOutlier), true)
})

test('groupFieldValues: single value is never an outlier', () => {
  const buckets = groupFieldValues([{ recipeId: 'A', value: 'x' }, { recipeId: 'B', value: 'x' }])
  assert.equal(buckets[0]?.isOutlier, false)
})

test('buildCompareWorkbook emits Overlap + IDP + one sheet per slot', () => {
  const wb = buildCompareWorkbook([
    recipeWithAmp('A', [measAmp({ Mag: '50.0K' })]),
    recipeWithAmp('B', [measAmp({ Mag: '80.0K' })])
  ], ['WAFER'])

  const names = wb.sheets.map(s => s.name)
  assert.deepEqual(names, ['Overlap', 'IDP', 'Addressing 1', 'Addressing 2', 'Addressing 3', 'Measure 1', 'Measure 2'])

  const overlap = wb.sheets.find(s => s.name === 'Overlap')!
  assert.deepEqual(overlap.rows[0], ['parameter', 'coverage', 'A', 'B'])
  assert.deepEqual(overlap.rows[1], ['WAFER', 'all', '✓', '✓'])

  const meas1 = wb.sheets.find(s => s.name === 'Measure 1')!
  assert.deepEqual(meas1.rows[0], ['parameter', 'attr', 'A', 'B'])
  const magRow = meas1.rows.find(r => r[1] === 'Mag')!
  assert.deepEqual(magRow, ['WAFER', 'Mag', '50.0K', '80.0K'])
})
