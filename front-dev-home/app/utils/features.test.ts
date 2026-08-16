// Pure-logic tests for features. Run: node --test app/utils/features.test.ts
// Feature slugs are the segment after the tool type in `/ebeam/{toolType}/…`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  FEATURE_SLUGS,
  FEATURE_SLUG_REGEX,
  FEATURE_SLUG_SUFFIX_REGEX,
  FABLESS_FEATURES,
  isFablessFeature,
  matchFeatureFromPath
} from './features.ts'

// Widened view of the tuple, so retired slugs can be checked for absence
// without a cast that would itself assert them into the type.
const slugStrings: readonly string[] = FEATURE_SLUGS

test('the slug list is the live set, with the merged legacy routes excluded', () => {
  assert.deepEqual([...FEATURE_SLUGS], [
    'storage',
    'recipe-search',
    'recipe-status',
    'hardware',
    'live-alarm',
    'device-statistics',
    'skewvoir',
    'tttm'
  ])
  // recipe-tat / fail-issue merged into recipe-status and are redirected by
  // route middleware before any layout reads route.path, so listing them would
  // make a legacy URL look like a live feature.
  assert.ok(!slugStrings.includes('recipe-tat'))
  assert.ok(!slugStrings.includes('fail-issue'))
})

test('no slug is a prefix of another, so alternation order cannot mis-match', () => {
  for (const a of FEATURE_SLUGS) {
    for (const b of FEATURE_SLUGS) {
      if (a === b) continue
      assert.ok(!b.startsWith(a), `${a} is a prefix of ${b} — regex order would decide the match`)
    }
  }
})

test('matchFeatureFromPath finds the feature with and without a fab segment', () => {
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/storage'), 'storage')
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/recipe-status'), 'recipe-status')
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/skewvoir'), 'skewvoir')
  assert.equal(matchFeatureFromPath('/ebeam/hvsem/m14/hardware'), 'hardware')
})

test('matchFeatureFromPath keeps matching past deeper sub-routes', () => {
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/recipe-search/open'), 'recipe-search')
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/recipe-search/meas-hist'), 'recipe-search')
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/skewvoir/workspace'), 'skewvoir')
})

test('matchFeatureFromPath distinguishes the two skew- slugs', () => {
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/tttm'), 'tttm')
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/skewvoir'), 'skewvoir')
})

test('matchFeatureFromPath returns empty when no feature segment is present', () => {
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3'), '')
  assert.equal(matchFeatureFromPath('/ebeam/cdsem'), '')
  assert.equal(matchFeatureFromPath('/'), '')
  assert.equal(matchFeatureFromPath(''), '')
  // A retired slug resolves to no feature, not to a stale tab.
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/recipe-tat'), '')
})

test('a slug must be a whole segment — no partial-word matches', () => {
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/storages'), '')
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/my-storage'), '')
  assert.ok(!FEATURE_SLUG_REGEX.test('/ebeam/cdsem/r3/storages'))
})

test('FEATURE_SLUG_REGEX accepts the segment at the end or mid-path', () => {
  assert.ok(FEATURE_SLUG_REGEX.test('/ebeam/cdsem/r3/storage'))
  assert.ok(FEATURE_SLUG_REGEX.test('/ebeam/cdsem/r3/storage/'))
  assert.ok(FEATURE_SLUG_REGEX.test('/ebeam/cdsem/r3/recipe-search/open'))
})

test('FEATURE_SLUG_SUFFIX_REGEX strips the feature segment and everything after it', () => {
  assert.equal('/ebeam/cdsem/r3/storage'.replace(FEATURE_SLUG_SUFFIX_REGEX, ''), '/ebeam/cdsem/r3')
  assert.equal(
    '/ebeam/cdsem/r3/recipe-search/open'.replace(FEATURE_SLUG_SUFFIX_REGEX, ''),
    '/ebeam/cdsem/r3'
  )
  assert.equal('/ebeam/cdsem/skewvoir'.replace(FEATURE_SLUG_SUFFIX_REGEX, ''), '/ebeam/cdsem')
})

test('FEATURE_SLUG_SUFFIX_REGEX leaves a path with no feature segment alone', () => {
  assert.equal('/ebeam/cdsem/r3'.replace(FEATURE_SLUG_SUFFIX_REGEX, ''), '/ebeam/cdsem/r3')
})

test('the fabless set is exactly the two pages that ignore the URL fab', () => {
  assert.deepEqual([...FABLESS_FEATURES].sort(), ['device-statistics', 'skewvoir'])
})

test('isFablessFeature answers for live slugs and unknown strings alike', () => {
  assert.equal(isFablessFeature('device-statistics'), true)
  assert.equal(isFablessFeature('skewvoir'), true)
  assert.equal(isFablessFeature('storage'), false)
  assert.equal(isFablessFeature('recipe-search'), false)
  assert.equal(isFablessFeature('tttm'), false)
  assert.equal(isFablessFeature('not-a-feature'), false)
  assert.equal(isFablessFeature(''), false)
})

test('every fabless entry is a real slug', () => {
  for (const slug of FABLESS_FEATURES) {
    assert.ok(FEATURE_SLUGS.includes(slug), `${slug} is fabless but not a feature slug`)
  }
})
