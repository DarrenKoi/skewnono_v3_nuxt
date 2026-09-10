// Pure-logic tests for recipeView. Run: node --test app/utils/recipeView.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  recipeTableUi, IMAGE_SLOTS, EMPTY_SLOT, isEmptySlot,
  formatSettingValue, recipeDetailRoute, recipeDetailId, RECIPE_ROW_ACTIONS, buildRecipeDetailNavItems,
  readRecipeNameQuery, readRecipeSourceQuery, readRecipeOwnerFabQuery, formatRecipeTimestamp,
  isSequenceSection, splitSequenceSections, splitAfPrSectionsByDomain, formatFixed
} from './recipeView.ts'
import type { LocationQuery, RouteLocationNormalizedLoaded } from 'vue-router'
import type { IdpImageInfoRow } from '../composables/useRecipeSearchApi.ts'

// Minimal loaded route — only `query` is read, the rest satisfies the type.
const routeWith = (query: LocationQuery): RouteLocationNormalizedLoaded => ({
  name: undefined,
  path: '/ebeam/cdsem/r3/recipe-search/open',
  fullPath: '/ebeam/cdsem/r3/recipe-search/open',
  params: {},
  meta: {},
  hash: '',
  query,
  redirectedFrom: undefined,
  matched: []
})

// --- static UI tables ---

test('recipeTableUi keeps every slot the tables bind, each a real class string', () => {
  assert.deepEqual(Object.keys(recipeTableUi).sort(), ['td', 'th', 'tr'])
  // A slot that lost its value would bind `undefined` and silently unstyle a
  // whole column rather than fail.
  for (const value of Object.values(recipeTableUi)) assert.ok(value.length > 0)
})

// --- image slots ---

test('IMAGE_SLOTS covers three addressing plus two measure images', () => {
  assert.equal(IMAGE_SLOTS.length, 5)
  assert.deepEqual(IMAGE_SLOTS.filter(s => s.role === 'address').map(s => s.stage), [
    'Addressing 1', 'Addressing 2', 'Addressing 3'
  ])
  assert.deepEqual(IMAGE_SLOTS.filter(s => s.role === 'measure').map(s => s.stage), [
    'Measure 1', 'Measure 2'
  ])
})

test('IMAGE_SLOTS keys match the backend column names, third addressing included', () => {
  // The office schema is asymmetric: img_add1 / img_add2 but image_add3. A
  // "tidied" img_add3 would read undefined off every row.
  assert.deepEqual(IMAGE_SLOTS.map(s => s.key), [
    'img_add1', 'img_add2', 'image_add3', 'img_meas1', 'img_meas2'
  ])
})

test('every IMAGE_SLOTS key resolves on a real idp_image_info row', () => {
  const row: IdpImageInfoRow = {
    Parameter: 'CD_X',
    img_add1: 'a1.jpg', img_add2: 'a2.jpg', image_add3: 'a3.jpg',
    img_meas1: 'm1.jpg', img_meas2: 'm2.jpg',
    SEQ: 1, Last_SEQ: 3, Region: 0,
    Addressing: true, Mother_Para: true, Double_Addressing: false,
    Meas_Counting: 2, dnumber_removed: false
  }
  assert.deepEqual(IMAGE_SLOTS.map(s => row[s.key]), [
    'a1.jpg', 'a2.jpg', 'a3.jpg', 'm1.jpg', 'm2.jpg'
  ])
})

test('the slot label is the raw column name, so the UI names what it read', () => {
  for (const slot of IMAGE_SLOTS) assert.equal(slot.label, slot.key)
})

// --- image slots vs setting slots ---

test('only three slots name an image; img_add2 and img_meas2 name settings', () => {
  // img_add2 is PRMP0000 (-> ENMP0000, the AF/PR condition) and img_meas2 is
  // PRMS0000 (the AMP file itself). Neither has a .jpeg. image_add3 breaks the
  // img_* naming run but IS an image. (user-confirmed 2026-07-29)
  assert.deepEqual(
    IMAGE_SLOTS.filter(s => s.hasImage).map(s => s.key),
    ['img_add1', 'image_add3', 'img_meas1']
  )
  assert.deepEqual(
    IMAGE_SLOTS.filter(s => !s.hasImage).map(s => s.key),
    ['img_add2', 'img_meas2']
  )
})

// --- the empty-slot sentinel ---

test('the sentinel is the French "non", not "none"', () => {
  assert.equal(EMPTY_SLOT, 'non')
  assert.ok(isEmptySlot('non'))
  assert.ok(isEmptySlot('NON'))
  assert.ok(isEmptySlot('  non  '))
  assert.ok(isEmptySlot(''))
  assert.ok(isEmptySlot(null))
  assert.ok(isEmptySlot(undefined))
})

test('"none" is an ordinary value, not the sentinel', () => {
  assert.equal(isEmptySlot('none'), false)
  assert.equal(isEmptySlot('IMMP0001'), false)
})

// --- formatSettingValue ---

test('formatAmpValue renders an em-dash placeholder for every empty form', () => {
  assert.equal(formatSettingValue(null), '—')
  assert.equal(formatSettingValue(undefined), '—')
  assert.equal(formatSettingValue(''), '—')
})

test('formatAmpValue passes real values through as text', () => {
  assert.equal(formatSettingValue('120000'), '120000')
  assert.equal(formatSettingValue('0'), '0') // a real zero is not "empty"
})

// --- routes ---

test('recipeDetailRoute lower-cases the fab and carries the recipe as a query', () => {
  assert.deepEqual(recipeDetailRoute('cdsem', 'R3', 'open', 'CD_RECIPE_A'), {
    path: '/ebeam/cdsem/r3/recipe-search/open',
    query: { recipe_name: 'CD_RECIPE_A' }
  })
  assert.deepEqual(recipeDetailRoute('hvsem', 'M14', 'meas-hist', 'X').path,
    '/ebeam/hvsem/m14/recipe-search/meas-hist')
})

test('recipeDetailRoute leaves the tool type and recipe name untouched', () => {
  const route = recipeDetailRoute('cdsem', 'R3', 'lateral', 'Mixed_Case_Recipe')
  assert.equal(route.query.recipe_name, 'Mixed_Case_Recipe')
  assert.ok(route.path.includes('/ebeam/cdsem/'))
})

test('OpenSearch detail routes carry source while Redis routes keep legacy URLs', () => {
  assert.deepEqual(
    recipeDetailRoute('cdsem', 'R3', 'lateral', 'CD_A', 'opensearch'),
    {
      path: '/ebeam/cdsem/r3/recipe-search/lateral',
      query: { recipe_name: 'CD_A', source: 'opensearch' }
    }
  )
  assert.deepEqual(
    recipeDetailRoute('cdsem', 'R3', 'lateral', 'CD_A', 'redis').query,
    { recipe_name: 'CD_A' }
  )
})

test('recipeDetailRoute keeps the multi-fab segment and carries the owner fab', () => {
  const route = recipeDetailRoute('cd-sem', 'R3,M16B', 'open', 'A/B_1', 'redis', 'M16B')
  assert.equal(route.path, '/ebeam/cd-sem/r3,m16b/recipe-search/open')
  assert.equal(route.query.fab_name, 'M16B')
  assert.equal(route.query.recipe_name, 'A/B_1')
})

test('recipeDetailRoute omits fab_name when no owner is given', () => {
  const route = recipeDetailRoute('cd-sem', 'r3', 'lateral', 'A/B_1')
  assert.equal('fab_name' in route.query, false)
})

test('recipeDetailRoute uppercases the owner fab regardless of input casing', () => {
  const route = recipeDetailRoute('cd-sem', 'r3', 'open', 'A', 'redis', 'm16b')
  assert.equal(route.query.fab_name, 'M16B')
})

// --- the identifier the detail screens are addressed by ---

test('recipeDetailId qualifies an analytics ranking row with its class', () => {
  // A recipe-tat / fail-issue row as the backend sends it: the two names are
  // separate fields there, and only `full_name` is the key recipe_search knows.
  assert.equal(
    recipeDetailId({ recipe_name: 'GATE_CD_045', full_name: 'GATE/GATE_CD_045' }),
    'GATE/GATE_CD_045'
  )
})

test('recipeDetailId passes a recipe-search row through unchanged', () => {
  // recipe_search's own rows carry no `full_name` — their `recipe_name`
  // already IS `class/recipe`, so there is nothing to qualify.
  assert.equal(recipeDetailId({ recipe_name: 'ADI/ADI_CD_BIAS_001' }), 'ADI/ADI_CD_BIAS_001')
})

test('recipeDetailId falls back to the bare name when full_name is absent', () => {
  // Preferable to routing to an empty recipe_name: the bare name at least
  // reaches meas-hist, which matches either field.
  assert.equal(recipeDetailId({ recipe_name: 'GATE_CD_045', full_name: '' }), 'GATE_CD_045')
  assert.equal(recipeDetailId({ recipe_name: 'GATE_CD_045', full_name: null }), 'GATE_CD_045')
  assert.equal(recipeDetailId({ recipe_name: '  GATE_CD_045  ' }), 'GATE_CD_045')
})

test('a ranking row routed to 열어 보기 carries the class-qualified name', () => {
  // The regression this file exists to hold. Handing the BARE `recipe_name`
  // here is a fabricated 200 against the mock and a 502 at the office: the
  // adapter takes the class from the prefix and term-matches
  // `full_name.keyword`, so an unqualified name locates no .idp at all.
  const row = { recipe_name: 'GATE_CD_045', full_name: 'GATE/GATE_CD_045' }
  const route = recipeDetailRoute('cd-sem', 'R3,M16B', 'open', recipeDetailId(row), 'redis', 'M16B')
  assert.equal(route.query.recipe_name, 'GATE/GATE_CD_045')
})

test('OpenSearch cannot construct an unsupported open detail route', () => {
  assert.throws(
    () => recipeDetailRoute('cdsem', 'R3', 'open', 'CD_A', 'opensearch'),
    /OpenSearch recipes do not support the open detail view/
  )
  assert.deepEqual(
    recipeDetailRoute('cdsem', 'R3', 'open', 'CD_A', 'redis').query,
    { recipe_name: 'CD_A' }
  )
  assert.deepEqual(
    recipeDetailRoute('cdsem', 'R3', 'meas-hist', 'CD_A', 'opensearch').query,
    { recipe_name: 'CD_A', source: 'opensearch' }
  )
})

test('the row actions are the three detail screens, each with a label and icon', () => {
  assert.deepEqual(RECIPE_ROW_ACTIONS.map(a => a.screen), ['open', 'lateral', 'meas-hist'])
  for (const action of RECIPE_ROW_ACTIONS) {
    assert.ok(action.label.length > 0)
    assert.ok(action.icon.startsWith('i-lucide-'))
  }
})

// --- nav items ---

test('buildRecipeDetailNavItems marks exactly the active screen', () => {
  const items = buildRecipeDetailNavItems('cdsem', 'R3', 'CD_A', 'lateral', undefined)
  assert.equal(items.length, 3)
  assert.deepEqual(items.filter(i => i.active).map(i => i.screen), ['lateral'])
})

test('buildRecipeDetailNavItems targets each screen under the fab path', () => {
  const items = buildRecipeDetailNavItems('cdsem', 'R3', 'CD_A', 'open', undefined)
  assert.deepEqual(items.map(i => i.to.path), [
    '/ebeam/cdsem/r3/recipe-search/open',
    '/ebeam/cdsem/r3/recipe-search/lateral',
    '/ebeam/cdsem/r3/recipe-search/meas-hist'
  ])
  for (const item of items) assert.deepEqual(item.to.query, { recipe_name: 'CD_A' })
})

test('buildRecipeDetailNavItems forwards the set flag only when it is "1"', () => {
  const withFlag = buildRecipeDetailNavItems('cdsem', 'R3', 'CD_A', 'open', '1')
  for (const item of withFlag) {
    assert.deepEqual(item.to.query, { recipe_name: 'CD_A', set: '1' })
  }
  // Anything else (absent, array, another value) must not leak into the link.
  for (const flag of [undefined, '', '0', ['1'], 1]) {
    const items = buildRecipeDetailNavItems('cdsem', 'R3', 'CD_A', 'open', flag)
    for (const item of items) assert.deepEqual(item.to.query, { recipe_name: 'CD_A' })
  }
})

test('buildRecipeDetailNavItems keeps each action label and icon', () => {
  const items = buildRecipeDetailNavItems('cdsem', 'R3', 'CD_A', 'open', undefined)
  assert.deepEqual(items.map(i => i.label), RECIPE_ROW_ACTIONS.map(a => a.label))
  assert.deepEqual(items.map(i => i.icon), RECIPE_ROW_ACTIONS.map(a => a.icon))
})

test('OpenSearch detail navigation excludes open and preserves source plus set', () => {
  const items = buildRecipeDetailNavItems(
    'cdsem', 'R3', 'CD_A', 'lateral', '1', 'opensearch'
  )
  assert.deepEqual(items.map(item => item.screen), ['lateral', 'meas-hist'])
  assert.deepEqual(items.map(item => item.to.query), [
    { recipe_name: 'CD_A', source: 'opensearch', set: '1' },
    { recipe_name: 'CD_A', source: 'opensearch', set: '1' }
  ])
})

// --- readRecipeNameQuery ---

test('readRecipeNameQuery reads and trims the recipe_name query', () => {
  assert.equal(readRecipeNameQuery(routeWith({ recipe_name: 'CD_A' })), 'CD_A')
  assert.equal(readRecipeNameQuery(routeWith({ recipe_name: '  CD_A  ' })), 'CD_A')
})

test('readRecipeNameQuery takes the first value of a repeated query key', () => {
  assert.equal(readRecipeNameQuery(routeWith({ recipe_name: ['CD_A', 'CD_B'] })), 'CD_A')
})

test('readRecipeNameQuery is empty when the query is missing or valueless', () => {
  assert.equal(readRecipeNameQuery(routeWith({})), '')
  assert.equal(readRecipeNameQuery(routeWith({ recipe_name: null })), '') // `?recipe_name`
  assert.equal(readRecipeNameQuery(routeWith({ recipe_name: [] })), '')
  assert.equal(readRecipeNameQuery(routeWith({ recipe_name: [null] })), '')
  assert.equal(readRecipeNameQuery(routeWith({ other: 'CD_A' })), '')
})

// --- readRecipeOwnerFabQuery ---

test('readRecipeOwnerFabQuery reads, trims, and uppercases the fab_name query', () => {
  assert.equal(readRecipeOwnerFabQuery(routeWith({ fab_name: 'm16b' })), 'M16B')
  assert.equal(readRecipeOwnerFabQuery(routeWith({ fab_name: '  r3  ' })), 'R3')
})

test('readRecipeOwnerFabQuery takes the first value of a repeated query key', () => {
  assert.equal(readRecipeOwnerFabQuery(routeWith({ fab_name: ['R3', 'M16B'] })), 'R3')
})

test('readRecipeOwnerFabQuery is empty when the query is missing or valueless', () => {
  assert.equal(readRecipeOwnerFabQuery(routeWith({})), '')
  assert.equal(readRecipeOwnerFabQuery(routeWith({ fab_name: null })), '')
  assert.equal(readRecipeOwnerFabQuery(routeWith({ fab_name: [] })), '')
  assert.equal(readRecipeOwnerFabQuery(routeWith({ fab_name: [null] })), '')
  assert.equal(readRecipeOwnerFabQuery(routeWith({ other: 'R3' })), '')
})

test('readRecipeSourceQuery accepts only the explicit OpenSearch marker', () => {
  assert.equal(readRecipeSourceQuery(routeWith({ source: 'opensearch' })), 'opensearch')
  assert.equal(readRecipeSourceQuery(routeWith({ source: 'redis' })), 'redis')
  assert.equal(readRecipeSourceQuery(routeWith({ source: ['opensearch'] })), 'redis')
  assert.equal(readRecipeSourceQuery(routeWith({})), 'redis')
})

// --- formatRecipeTimestamp ---
// The ISO literals below carry no offset, so Date reads them as local time and
// the assertions hold in any TZ.

test('formatRecipeTimestamp renders local date and time, zero-padded', () => {
  assert.equal(formatRecipeTimestamp('2026-07-25T14:03:07'), '2026-07-25 14:03')
  assert.equal(formatRecipeTimestamp('2026-01-02T03:04:05'), '2026-01-02 03:04')
})

test('formatRecipeTimestamp appends seconds on request', () => {
  assert.equal(formatRecipeTimestamp('2026-07-25T14:03:07', { withSeconds: true }), '2026-07-25 14:03:07')
  assert.equal(formatRecipeTimestamp('2026-01-02T03:04:05', { withSeconds: true }), '2026-01-02 03:04:05')
})

test('formatRecipeTimestamp defaults to no seconds when opts omit the flag', () => {
  assert.equal(formatRecipeTimestamp('2026-07-25T14:03:07', {}), '2026-07-25 14:03')
  assert.equal(formatRecipeTimestamp('2026-07-25T14:03:07', { withSeconds: false }), '2026-07-25 14:03')
})

test('formatRecipeTimestamp echoes an unparseable timestamp instead of "Invalid Date"', () => {
  assert.equal(formatRecipeTimestamp(''), '')
  assert.equal(formatRecipeTimestamp('not-a-timestamp'), 'not-a-timestamp')
  assert.equal(formatRecipeTimestamp('0000-00-00'), '0000-00-00')
})

// --- the sequence / settings split of one ENMP block ---
// Section names and order are the office's own (office 확인 2026-07-30).

const afPrBlock = {
  source: 'ENMP0007',
  rows: [
    { key: 'Pre Dose', value: 'a1', section: 'sequence_addressing' },
    { key: 'Auto Focus1', value: 'a2', section: 'sequence_addressing' },
    { key: 'Focusing', value: 'b1', section: 'sequence_measurement' },
    { key: 'Image Save', value: 'b2', section: 'sequence_measurement' },
    { key: 'Acceptance', value: 'c1', section: 'measurement_pattern_recognition' },
    { key: 'Method', value: 'Fast2', section: 'measurement_focusing' },
    { key: 'Method', value: 'Fast2', section: 'addressing_auto_focus1' }
  ]
}

test('splitAfPrSectionsByDomain separates addressing, measurement and unknown rows', () => {
  const settings = splitSequenceSections({
    source: 'ENMP0012',
    rows: [
      { key: 'Address Method 1', value: 'A1', section: 'addressing_auto_focus1' },
      { key: 'Measure PR', value: 'M1', section: 'measurement_pattern_recognition' },
      { key: 'Address Method 2', value: 'A2', section: 'addressing_auto_focus2' },
      { key: 'Measure Focus', value: 'M2', section: '  MEASUREMENT_Focusing  ' },
      { key: 'Vendor Flag', value: 'V', section: 'vendor_extension' },
      { key: 'Version', value: '3' },
      { key: 'Image Save', value: 'yes', section: 'sequence_measurement' }
    ]
  }).settings

  const grouped = splitAfPrSectionsByDomain(settings)

  assert.deepEqual(
    grouped.addressing?.rows.map(row => row.key),
    ['Address Method 1', 'Address Method 2']
  )
  assert.deepEqual(
    grouped.measurement?.rows.map(row => row.key),
    ['Measure PR', 'Measure Focus']
  )
  assert.deepEqual(
    grouped.other?.rows.map(row => row.key),
    ['Vendor Flag', 'Version']
  )
  assert.equal(grouped.addressing?.source, 'ENMP0012')
  assert.equal(grouped.measurement?.source, 'ENMP0012')
  assert.equal(grouped.other?.source, 'ENMP0012')
})

test('splitAfPrSectionsByDomain preserves empty blocks for domains absent from a file', () => {
  assert.deepEqual(
    splitAfPrSectionsByDomain({
      source: 'ENMP0013',
      rows: [
        { key: 'Method', value: 'Fast2', section: 'measurement_focusing' }
      ]
    }),
    {
      addressing: { source: 'ENMP0013', rows: [] },
      measurement: {
        source: 'ENMP0013',
        rows: [
          { key: 'Method', value: 'Fast2', section: 'measurement_focusing' }
        ]
      },
      other: { source: 'ENMP0013', rows: [] }
    }
  )
})

test('splitAfPrSectionsByDomain passes a missing file through as null', () => {
  assert.deepEqual(splitAfPrSectionsByDomain(null), {
    addressing: null,
    measurement: null,
    other: null
  })
})

test('splitSequenceSections sends only the sequence_* groups to the sequence half', () => {
  const { sequence, settings } = splitSequenceSections(afPrBlock)
  assert.deepEqual(
    sequence?.rows.map(r => `${r.section}/${r.key}`),
    [
      'sequence_addressing/Pre Dose',
      'sequence_addressing/Auto Focus1',
      'sequence_measurement/Focusing',
      'sequence_measurement/Image Save'
    ]
  )
  assert.deepEqual(
    settings?.rows.map(r => `${r.section}/${r.key}`),
    [
      'measurement_pattern_recognition/Acceptance',
      'measurement_focusing/Method',
      'addressing_auto_focus1/Method'
    ]
  )
})

test('splitSequenceSections keeps the source file on both halves', () => {
  const { sequence, settings } = splitSequenceSections(afPrBlock)
  assert.equal(sequence?.source, 'ENMP0007')
  assert.equal(settings?.source, 'ENMP0007')
})

test('splitSequenceSections keeps an absent group as EMPTY, not null', () => {
  // No addressing pass ran, so the file has no sequence_addressing. The file
  // itself was still read — "설정이 없습니다" is true, "파일 없음" would not be.
  const { sequence, settings } = splitSequenceSections({
    source: 'ENMP0008',
    rows: [{ key: 'Focusing', value: 'x', section: 'sequence_measurement' }]
  })
  assert.equal(sequence?.rows.length, 1)
  assert.deepEqual(settings, { source: 'ENMP0008', rows: [] })
})

test('splitSequenceSections passes a missing file through as null on both halves', () => {
  assert.deepEqual(splitSequenceSections(null), { sequence: null, settings: null })
})

test('splitSequenceSections leaves the four flat readers whole — no section, no sequence', () => {
  // cond.txt / AMP / ENAP rows carry no section at all; every row is a setting.
  const { sequence, settings } = splitSequenceSections({
    source: 'PRMS0000',
    rows: [{ key: 'Measurement', value: 'Width' }, { key: 'Method', value: 'Linear' }]
  })
  assert.deepEqual(sequence?.rows, [])
  assert.equal(settings?.rows.length, 2)
})

test('isSequenceSection matches the prefix, tolerates case and padding, ignores lookalikes', () => {
  assert.ok(isSequenceSection('sequence_addressing'))
  assert.ok(isSequenceSection('sequence_measurement'))
  assert.ok(isSequenceSection('  SEQUENCE_Measurement  '))
  // A group that merely mentions a sequence is a settings group.
  assert.equal(isSequenceSection('measurement_sequence'), false)
  assert.equal(isSequenceSection('measurement_focusing'), false)
  assert.equal(isSequenceSection(null), false)
  assert.equal(isSequenceSection(undefined), false)
  assert.equal(isSequenceSection(''), false)
})

test('formatFixed prints a number at the requested precision', () => {
  assert.equal(formatFixed(52.676, 3), '52.676')
  assert.equal(formatFixed(-25.24, 3), '-25.240')
  assert.equal(formatFixed(0, 3), '0.000')
})

test('formatFixed accepts the STRING the office parser sent on 2026-08-05', () => {
  // The bug: `row['Coordinate.X'].toFixed(3)` on "52.676" threw
  // "toFixed is not a function" inside a computed, so the align table never
  // rendered and the modal could not be closed.
  assert.equal(formatFixed('52.676', 3), '52.676')
  assert.equal(formatFixed('-25.240', 3), '-25.240')
})

test('formatFixed renders missing data as a dash, never as 0.000', () => {
  // Number(null) and Number('') are both 0. A coordinate that reads 0.000
  // puts a measurement point at the wafer centre — absent must look absent.
  assert.equal(formatFixed(null, 3), '—')
  assert.equal(formatFixed(undefined, 3), '—')
  assert.equal(formatFixed('', 3), '—')
})

test('formatFixed falls back rather than throwing on anything unparseable', () => {
  assert.equal(formatFixed('n/a', 3), '—')
  assert.equal(formatFixed(Number.NaN, 3), '—')
  assert.equal(formatFixed(Infinity, 3), '—')
  assert.equal(formatFixed({}, 3), '—')
  assert.equal(formatFixed('n/a', 3, ''), '')
})
