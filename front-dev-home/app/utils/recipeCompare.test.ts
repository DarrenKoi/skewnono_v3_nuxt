// Pure-logic tests for recipeCompare. Run: node --test app/utils/recipeCompare.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildOverlap,
  classifyCoverage,
  filterOverlap,
  commonParameters,
  buildIdpRows, buildSettingRows, blockForSlot, cellsDiffer, imageFilenames,
  displayedVariant,
  groupFieldValues,
  buildCompareWorkbook, compareDetailKey, compareRecipeLabels,
  type CompareParamDetail, type CompareDetailIndex
} from './recipeCompare.ts'
import type { CompareRecipe, CompareParameter } from '../composables/useRecipeCompareApi.ts'

const param = (name: string): CompareParameter => ({
  Parameter: name,
  idp: {
    Addressing: true, Double_Addressing: false, Mother_Para: true,
    Region: 1, Meas_Counting: 1, dnumber_removed: false
  },
  images: { img_add1: 'a1', img_add2: 'a2', image_add3: 'a3', img_meas1: 'm1', img_meas2: 'm2' }
})

const LOCATOR = { eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B' }

const recipe = (id: string, params: string[], fabName = 'R3'): CompareRecipe => ({
  recipe_id: id, fab_name: fabName, locator: LOCATOR, parameters: params.map(param)
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
  // presentIn is fab-qualified (`${fab_name}|${recipe_id}`), not bare ids —
  // see the same-name-two-fabs tests below for why.
  assert.deepEqual(byName.WAFER!.presentIn, ['R3|A', 'R3|B', 'R3|C'])
  assert.equal(byName.P5!.coverage, 'partial')
  assert.equal(byName.P8!.coverage, 'unique')
  assert.equal(byName.P12!.coverage, 'unique')
})

test('buildOverlap dedupes a repeated parameter within one recipe', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'WAFER'])])
  assert.equal(rows.length, 1)
  assert.equal(rows[0]?.count, 1)
})

test('buildOverlap keeps same-name recipes on different fabs distinct', () => {
  // Cross-fab compare can legitimately select the same recipe name from two
  // fabs. Keying presence on bare recipe_id would report the M16B copy as
  // having WAFER too, just because the R3 copy does — a wrong answer with no
  // error, since both recipes share the id 'A'.
  const rows = buildOverlap([
    recipe('A', ['WAFER'], 'R3'),
    recipe('A', [], 'M16B')
  ])
  const wafer = rows.find(r => r.parameter === 'WAFER')!
  assert.equal(wafer.count, 1)
  assert.equal(wafer.total, 2)
  // classifyCoverage treats any count <= 1 as 'unique', independent of total.
  assert.equal(wafer.coverage, 'unique')
  assert.deepEqual(wafer.presentIn, ['R3|A'])
})

test('buildOverlap counts a parameter once per (fab, recipe) even when ids match', () => {
  const rows = buildOverlap([
    recipe('A', ['WAFER'], 'R3'),
    recipe('A', ['WAFER'], 'M16B')
  ])
  const wafer = rows.find(r => r.parameter === 'WAFER')!
  // Both recipes genuinely carry WAFER, so count must be 2 — a Set keyed on
  // the bare id 'A' would collapse both additions into one entry and report
  // 'partial' (1/2) for a parameter both recipes actually have.
  assert.equal(wafer.count, 2)
  assert.equal(wafer.coverage, 'all')
  assert.deepEqual(wafer.presentIn, ['R3|A', 'M16B|A'])
})

test('filterOverlap + commonParameters', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'P5']), recipe('B', ['WAFER'])])
  assert.deepEqual(filterOverlap(rows, 'common').map(r => r.parameter), ['WAFER'])
  assert.deepEqual(filterOverlap(rows, 'unique').map(r => r.parameter), ['P5'])
  assert.deepEqual(filterOverlap(rows, 'all').map(r => r.parameter), ['WAFER', 'P5'])
  assert.deepEqual(commonParameters(rows), ['WAFER'])
})

/** A parsed .{IMMS0001.jpeg}/cond.txt as the office reader would hand it back. */
const detailWith = (rows: Record<string, string>): CompareParamDetail => ({
  parameter: 'WAFER',
  amp: { source: 'PRMS0001', rows: [{ key: 'AMP_FIELD_1', value: 'aa' }] },
  af_pr: { source: 'ENMP0001', rows: [{ key: 'AFPR_FIELD_1', value: 'bb' }] },
  images: [{
    slot: 'img_meas1',
    stage: 'Measure 1',
    name: 'IMMS0001.jpeg',
    cond: { source: '.IMMS0001.jpeg/cond.txt', rows: Object.entries(rows).map(([key, value]) => ({ key, value })) }
  }]
})

const recipeWithAmp = (id: string, _unused: unknown[] = []): CompareRecipe => ({
  recipe_id: id, fab_name: 'R3', locator: LOCATOR,
  parameters: [{
    Parameter: 'WAFER',
    idp: { Addressing: true, Double_Addressing: false, Mother_Para: true, Region: 5, Meas_Counting: 3, dnumber_removed: false },
    images: { img_add1: 'a1', img_add2: 'a2', image_add3: 'a3', img_meas1: `${id}_m1`, img_meas2: 'm2' }
  }]
})

test('cellsDiffer: equal values agree, one different differs', () => {
  assert.equal(cellsDiffer(['50K', '50K', '50K']), false)
  assert.equal(cellsDiffer(['50K', '80K', '50K']), true)
  assert.equal(cellsDiffer(['x']), false)
})

test('buildSettingRows aligns values per recipe and flags differing rows', () => {
  const rows = buildSettingRows([
    detailWith({ Mag: '50.0K', Algo: 'Linear' }),
    detailWith({ Mag: '80.0K', Algo: 'Linear' })
  ], 'img_meas1')
  const mag = rows.find(r => r.key === 'Mag')!
  const algo = rows.find(r => r.key === 'Algo')!
  assert.deepEqual(mag.values, ['50.0K', '80.0K'])
  assert.equal(mag.differs, true)
  assert.equal(algo.differs, false)
})

test('buildSettingRows shows 없음 when a recipe has no settings for the cell', () => {
  const rows = buildSettingRows([detailWith({ Mag: '50.0K' }), null], 'img_meas1')
  assert.equal(rows.find(r => r.key === 'Mag')!.values[1], '없음')
})

test('buildSettingRows unions keys so a field only one recipe carries still shows', () => {
  // The office field names are unverified, and two recipes may legitimately
  // carry different ones. Intersecting would hide exactly the difference the
  // compare screen exists to surface.
  const rows = buildSettingRows([
    detailWith({ Mag: '50.0K' }),
    detailWith({ Mag: '50.0K', OnlyInB: 'x' })
  ], 'img_meas1')
  const only = rows.find(r => r.key === 'OnlyInB')!
  assert.deepEqual(only.values, ['없음', 'x'])
  assert.equal(only.differs, true)
})

test('buildSettingRows keeps the readers key order, first seen first', () => {
  const rows = buildSettingRows([detailWith({ Zeta: '1', Alpha: '2' })], 'img_meas1')
  assert.deepEqual(rows.map(r => r.key), ['Zeta', 'Alpha'])
})

/** An ENMP block: nested groups, and pass 1 / pass 2 share their inner keys. */
const detailWithSections = (focus1: string, focus2: string): CompareParamDetail => ({
  parameter: 'WAFER',
  amp: null,
  af_pr: {
    source: 'ENMP0001',
    rows: [
      { key: 'Acceptance', value: focus1, section: 'addressing_auto_focus1' },
      { key: 'Acceptance', value: focus2, section: 'addressing_auto_focus2' },
      { key: 'Acceptance', value: 'm', section: 'measurement_focusing' }
    ]
  },
  images: []
})

test('buildSettingRows keeps two groups sharing an inner key apart', () => {
  // The bug this guards: identity used to be `row.key` alone, so addressing
  // pass 2 collapsed into pass 1 and the table showed pass 1's value twice —
  // no error, no blank cell, just a confidently wrong number.
  const rows = buildSettingRows([detailWithSections('p1', 'p2')], 'img_add2')

  assert.equal(rows.length, 3)
  assert.deepEqual(rows.map(r => r.section), [
    'addressing_auto_focus1', 'addressing_auto_focus2', 'measurement_focusing'
  ])
  assert.deepEqual(rows.map(r => r.values[0]), ['p1', 'p2', 'm'])
  // The label stays the bare key — the section is what disambiguates it.
  assert.deepEqual(rows.map(r => r.label), ['Acceptance', 'Acceptance', 'Acceptance'])
})

test('buildSettingRows matches grouped rows across recipes by group AND key', () => {
  const rows = buildSettingRows(
    [detailWithSections('p1', 'p2'), detailWithSections('p1', 'CHANGED')],
    'img_add2'
  )

  // Only pass 2 differs. Keyed by bare key, both recipes would have resolved
  // every row to their own pass 1 and nothing would have read as differing.
  assert.deepEqual(rows.map(r => r.differs), [false, true, false])
})

test('flat blocks are untouched by the section change', () => {
  const rows = buildSettingRows([detailWith({ Mag: '50.0K' })], 'img_meas1')
  assert.equal(rows[0]?.key, 'Mag')
  assert.equal(rows[0]?.section, null)
})

test('blockForSlot routes img_meas2 to amp and img_add2 to af_pr', () => {
  // Neither names an image: PRMS0000 IS the amp file, and PRMP0000 resolves
  // (PR -> EN) to the AF/PR condition. (user-confirmed 2026-07-29)
  const detail = detailWith({ Mag: '50.0K' })
  assert.equal(blockForSlot(detail, 'img_meas2')!.source, 'PRMS0001')
  assert.equal(blockForSlot(detail, 'img_add2')!.source, 'ENMP0001')
  assert.equal(blockForSlot(detail, 'img_meas1')!.source, '.IMMS0001.jpeg/cond.txt')
  assert.equal(blockForSlot(detail, 'img_add1'), null)
  assert.equal(blockForSlot(null, 'img_meas1'), null)
})

test('blockForSlot merges an HV-SEM slot\'s several files into one sectioned block', () => {
  // One slot, several stem-suffixed files, one cond each (2026-08-08). A bare
  // find() compared only the first file and silently ignored the rest.
  const detail: CompareParamDetail = {
    parameter: 'WAFER',
    amp: null,
    af_pr: null,
    images: [
      {
        slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0001-U.jpeg',
        cond: { source: '.IMMS0001-U.jpeg/cond.txt', rows: [{ key: 'Mag', value: '30000' }] }
      },
      {
        slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0001-L.jpeg',
        cond: { source: '.IMMS0001-L.jpeg/cond.txt', rows: [{ key: 'Mag', value: '50000' }] }
      }
    ]
  }
  const block = blockForSlot(detail, 'img_meas1')!

  // Same key in both variants — the section (variant label) keeps them apart,
  // exactly the (section, key) identity settingRowId already encodes.
  assert.deepEqual(block.rows, [
    { key: 'Mag', value: '30000', section: 'U' },
    { key: 'Mag', value: '50000', section: 'L' }
  ])
  assert.equal(block.source, '.IMMS0001-U.jpeg/cond.txt · .IMMS0001-L.jpeg/cond.txt')
})

test('displayedVariant names which of an HV-SEM slot\'s files the thumbnail shows', () => {
  // The compare matrix has ONE cell per recipe, so it can only render the first
  // of a multi-file slot. Unlabelled, two recipes differing solely in their -T
  // image would show identical -U thumbnails and read as agreeing.
  const detail: CompareParamDetail = {
    parameter: 'WAFER',
    amp: null,
    af_pr: null,
    images: [
      { slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0001-U.jpeg', cond: null },
      { slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0001-T.jpeg', cond: null },
      { slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0001-L.jpeg', cond: null }
    ]
  }
  assert.deepEqual(displayedVariant(detail, 'img_meas1'), { label: 'U', total: 3 })
})

test('displayedVariant labels are list-aware, so a repeated sub-position carries its rendition', () => {
  // One sub-position listed under two extensions (user-confirmed 2026-08-24):
  // a bare per-name label would read "U" for a file the neighbouring cell also
  // calls "U".
  const detail: CompareParamDetail = {
    parameter: 'WAFER',
    amp: null,
    af_pr: null,
    images: [
      { slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0001-U.jpeg', cond: null },
      { slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0001-U.TIF', cond: null }
    ]
  }
  assert.deepEqual(displayedVariant(detail, 'img_meas1'), { label: 'U\u00b7JPG', total: 2 })
})

test('displayedVariant stays silent when there is nothing to disambiguate', () => {
  // CD-SEM: one file per slot. A chip here would be noise on every cell.
  assert.equal(displayedVariant(detailWith({ Mag: '50.0K' }), 'img_meas1'), null)
  assert.equal(displayedVariant(detailWith({ Mag: '50.0K' }), 'img_add1'), null)
  assert.equal(displayedVariant(null, 'img_meas1'), null)
})

test('blockForSlot keeps a single-file slot\'s block untouched', () => {
  const block = blockForSlot(detailWith({ Mag: '50.0K' }), 'img_meas1')!
  assert.equal(block.source, '.IMMS0001.jpeg/cond.txt')
  assert.deepEqual(block.rows, [{ key: 'Mag', value: '50.0K' }])
})

test('buildIdpRows compares per-parameter fields', () => {
  const rows = buildIdpRows([
    recipeWithAmp('A', []),
    { recipe_id: 'B', fab_name: 'R3', locator: LOCATOR, parameters: [{
      Parameter: 'WAFER',
      idp: { Addressing: true, Double_Addressing: false, Mother_Para: true, Region: 8, Meas_Counting: 3, dnumber_removed: false },
      images: { img_add1: '', img_add2: '', image_add3: '', img_meas1: '', img_meas2: '' }
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
    { recipe_id: 'B', fab_name: 'R3', locator: LOCATOR, parameters: [] }
  ], 'WAFER', 'img_meas1')
  assert.deepEqual(files, ['A_m1', null])
})

test('groupFieldValues sorts buckets by count desc', () => {
  const buckets = groupFieldValues([
    { label: 'A', value: '50K' }, { label: 'B', value: '80K' },
    { label: 'C', value: '50K' }, { label: 'D', value: '50K' }
  ])
  assert.deepEqual(buckets.map(b => b.value), ['50K', '80K'])
  assert.deepEqual(buckets[0]?.labels, ['A', 'C', 'D'])
})

test('groupFieldValues flags a small minority as outlier', () => {
  const pairs = [
    ...Array.from({ length: 62 }, (_, i) => ({ label: `a${i}`, value: '50K' })),
    ...Array.from({ length: 31 }, (_, i) => ({ label: `b${i}`, value: '80K' })),
    ...Array.from({ length: 7 }, (_, i) => ({ label: `c${i}`, value: '100K' }))
  ]
  const buckets = groupFieldValues(pairs)
  const byValue = Object.fromEntries(buckets.map(b => [b.value, b]))
  assert.equal(byValue['50K']!.isOutlier, false) // largest
  assert.equal(byValue['80K']!.isOutlier, false) // 0.31 share > 0.25
  assert.equal(byValue['100K']!.isOutlier, true) // 0.07 share <= 0.25
})

test('groupFieldValues flags nothing on a tie for largest', () => {
  const buckets = groupFieldValues([
    { label: 'A', value: 'x' }, { label: 'B', value: 'y' }
  ])
  assert.equal(buckets.every(b => !b.isOutlier), true)
})

test('groupFieldValues: single value is never an outlier', () => {
  const buckets = groupFieldValues([{ label: 'A', value: 'x' }, { label: 'B', value: 'x' }])
  assert.equal(buckets[0]?.isOutlier, false)
})

test('compareRecipeLabels fab-qualifies only when the set spans fabs', () => {
  assert.deepEqual(
    compareRecipeLabels([recipe('A', []), recipe('B', [])]),
    ['A', 'B']
  )
  assert.deepEqual(
    compareRecipeLabels([recipe('A', [], 'R3'), recipe('A', [], 'M16B')]),
    ['A (R3)', 'A (M16B)']
  )
})

test('buildCompareWorkbook emits Overlap + IDP + one sheet per slot', () => {
  const details: CompareDetailIndex = new Map([
    [compareDetailKey('R3', 'A', 'WAFER'), detailWith({ Mag: '50.0K' })],
    [compareDetailKey('R3', 'B', 'WAFER'), detailWith({ Mag: '80.0K' })]
  ])
  const wb = buildCompareWorkbook([recipeWithAmp('A'), recipeWithAmp('B')], ['WAFER'], details)

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

test('buildCompareWorkbook keys per-recipe settings by (fab, recipe_id), not bare id', () => {
  // The bug this guards: with a bare-id key, `details.get('A::WAFER')` was
  // the SAME lookup for the R3 copy of recipe 'A' and the M16B copy, so the
  // second column silently rendered the first column's settings — on screen
  // and in this exported sheet, with no error.
  const details: CompareDetailIndex = new Map([
    [compareDetailKey('R3', 'A', 'WAFER'), detailWith({ Mag: '50.0K' })],
    [compareDetailKey('M16B', 'A', 'WAFER'), detailWith({ Mag: '80.0K' })]
  ])
  const wb = buildCompareWorkbook(
    [recipe('A', ['WAFER'], 'R3'), recipe('A', ['WAFER'], 'M16B')],
    ['WAFER'],
    details
  )

  // Column headers disambiguate the fab once the export spans more than one —
  // two columns both bare-labeled 'A' would be exactly as misleading as the
  // lookup collision itself.
  const overlap = wb.sheets.find(s => s.name === 'Overlap')!
  assert.deepEqual(overlap.rows[0], ['parameter', 'coverage', 'A (R3)', 'A (M16B)'])

  const meas1 = wb.sheets.find(s => s.name === 'Measure 1')!
  const magRow = meas1.rows.find(r => r[1] === 'Mag')!
  assert.deepEqual(magRow, ['WAFER', 'Mag', '50.0K', '80.0K'])
})
