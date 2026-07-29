// Pure-logic tests for recipeView. Run: node --test app/utils/recipeView.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  recipeTableUi, IMAGE_SLOTS, IMAGE_ONLY_SLOTS, EMPTY_SLOT, isEmptySlot,
  formatSettingValue, recipeDetailRoute, RECIPE_ROW_ACTIONS, buildRecipeDetailNavItems,
  readRecipeNameQuery, readRecipeSourceQuery, formatRecipeTimestamp
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
  assert.deepEqual(IMAGE_ONLY_SLOTS.map(s => s.key), ['img_add1', 'image_add3', 'img_meas1'])
  assert.deepEqual(
    IMAGE_SLOTS.filter(s => !s.hasImage).map(s => s.key),
    ['img_add2', 'img_meas2']
  )
})

test('IMAGE_ONLY_SLOTS keeps the raw-folder order', () => {
  const order = IMAGE_SLOTS.filter(s => s.hasImage)
  assert.deepEqual(IMAGE_ONLY_SLOTS.map(s => s.key), order.map(s => s.key))
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
