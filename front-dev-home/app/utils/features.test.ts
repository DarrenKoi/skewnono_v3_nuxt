// Pure-logic tests for features. Run: node --test app/utils/features.test.ts
// Feature slugs are the segment after the tool type in `/ebeam/{toolType}/…`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  FEATURE_SLUGS,
  FEATURE_SLUG_REGEX,
  FEATURE_SLUG_SUFFIX_REGEX,
  FABLESS_FEATURES,
  HEADER_INFO_PATHS,
  isFablessFeature,
  isHeaderInfoPath,
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
    'skew-check'
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
  assert.equal(matchFeatureFromPath('/ebeam/cdsem/r3/skew-check'), 'skew-check')
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
  assert.equal(isFablessFeature('skew-check'), false)
  assert.equal(isFablessFeature('not-a-feature'), false)
  assert.equal(isFablessFeature(''), false)
})

test('every fabless entry is a real slug', () => {
  for (const slug of FABLESS_FEATURES) {
    assert.ok(FEATURE_SLUGS.includes(slug), `${slug} is fabless but not a feature slug`)
  }
})

test('isHeaderInfoPath covers every page the header icons lead to', () => {
  for (const path of HEADER_INFO_PATHS) {
    assert.equal(isHeaderInfoPath(path), true, `${path} should keep the feature tabs`)
  }
  // /chat regressed twice: it is reachable only from the header icon, so losing
  // the tabs there leaves no way back to the main pages without the browser's back button.
  assert.equal(isHeaderInfoPath('/chat'), true)
})

test('isHeaderInfoPath matches sub-routes but not partial segments', () => {
  assert.equal(isHeaderInfoPath('/settings/profile'), true)
  assert.equal(isHeaderInfoPath('/chat/'), true)
  assert.equal(isHeaderInfoPath('/chatroom'), false)
  assert.equal(isHeaderInfoPath('/intro-video'), false)
})

test('isHeaderInfoPath excludes the hub index and the ebeam tree', () => {
  // The hub index and ebeam routes have their own tab handling — the hub shows none,
  // ebeam routes match on isEbeamRoute instead.
  assert.equal(isHeaderInfoPath('/'), false)
  assert.equal(isHeaderInfoPath('/ebeam/cd-sem/r3'), false)
  assert.equal(isHeaderInfoPath('/afm'), false)
})

// Guard against the drift that caused this bug three times: AppHeader's icon row and
// HEADER_INFO_PATHS are separate lists, so a new header icon silently loses its tabs.
test('every static header-icon target is a header info path', () => {
  const header = readFileSync(
    join(import.meta.dirname, '..', 'components', 'nav', 'AppHeader.vue'),
    'utf8'
  )
  // Static `to="/x"` only — the logo's `/` and the computed `:to` live-alarm target are
  // ebeam routes or the hub, both of which resolve their tabs elsewhere.
  const targets = [...header.matchAll(/\bto="(\/[^"]*)"/g)]
    .map(m => m[1]!)
    .filter(path => path !== '/')

  assert.ok(targets.length > 0, 'found no header icon targets — did the regex go stale?')
  for (const path of targets) {
    assert.equal(
      isHeaderInfoPath(path),
      true,
      `${path} is a header icon target but is missing from HEADER_INFO_PATHS, so its page renders no feature tabs`
    )
  }
})
