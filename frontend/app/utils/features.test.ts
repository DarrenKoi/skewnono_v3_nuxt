// Pure-logic tests for features. Run: node --test app/utils/features.test.ts
// Feature slugs are the segment after the tool type in `/ebeam/{toolType}/…`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  FEATURE_SLUGS,
  FEATURE_SLUG_REGEX,
  FEATURE_SLUG_SUFFIX_REGEX,
  FEATURE_TOOL_TYPES,
  FABLESS_FEATURES,
  SINGLE_FAB_FEATURES,
  featureSupportsToolType,
  isFablessFeature,
  isSingleFabFeature,
  matchFeatureFromPath,
  activeFeatureTab
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
  // recipe-tat / fail-issue merged into recipe-status, pm-planning into tttm;
  // all three are redirected by route middleware before any layout reads
  // route.path, so listing them would make a legacy URL look like a live
  // feature.
  assert.ok(!slugStrings.includes('recipe-tat'))
  assert.ok(!slugStrings.includes('fail-issue'))
  assert.ok(!slugStrings.includes('pm-planning'))
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

test('the single-fab set is exactly the lab page that pins one fab', () => {
  assert.deepEqual([...SINGLE_FAB_FEATURES].sort(), ['tttm'])
})

test('isSingleFabFeature answers for live slugs and unknown strings alike', () => {
  assert.equal(isSingleFabFeature('tttm'), true)
  assert.equal(isSingleFabFeature('pm-planning'), false)
  assert.equal(isSingleFabFeature('storage'), false)
  assert.equal(isSingleFabFeature('not-a-feature'), false)
  assert.equal(isSingleFabFeature(''), false)
})

test('a single-fab feature is a real slug and never fabless — the two sets contradict', () => {
  for (const slug of SINGLE_FAB_FEATURES) {
    assert.ok(FEATURE_SLUGS.includes(slug), `${slug} is single-fab but not a feature slug`)
    assert.ok(!FABLESS_FEATURES.has(slug), `${slug} cannot be both single-fab and fabless`)
  }
})

test('every live slug declares its tool families, non-empty', () => {
  // The table gates navigation AND builds menu links; a slug missing from it
  // would make its page unreachable from the tool-type switcher.
  assert.deepEqual(Object.keys(FEATURE_TOOL_TYPES).sort(), [...FEATURE_SLUGS].sort())
  for (const [slug, toolTypes] of Object.entries(FEATURE_TOOL_TYPES)) {
    assert.ok(toolTypes.length > 0, `${slug} supports no tool type`)
  }
})

test('featureSupportsToolType answers for live slugs and unknown strings alike', () => {
  assert.equal(featureSupportsToolType('storage', 'cd-sem'), true)
  assert.equal(featureSupportsToolType('storage', 'hv-sem'), true)
  assert.equal(featureSupportsToolType('tttm', 'cd-sem'), true)
  assert.equal(featureSupportsToolType('tttm', 'hv-sem'), false)
  assert.equal(featureSupportsToolType('pm-planning', 'cd-sem'), false)
  assert.equal(featureSupportsToolType('storage', 'veritysem'), false)
  assert.equal(featureSupportsToolType('not-a-feature', 'cd-sem'), false)
})

// activeFeatureTab — which top nav pill lights up.
//
// 장비 상태 ('index') is the FALLBACK, so every page that is not 장비 상태 has
// to be recognised or it silently claims that tab. /pm-planning was not, and
// lit 장비 상태 while the user was on a 실험실 page (2026-08-30; that route was
// folded into /tttm on 2026-09-01 and now redirects before any tab is read).

test('each feature page highlights its own tab', () => {
  assert.equal(activeFeatureTab('/ebeam/cd-sem/m14a/recipe-status'), 'recipe-status')
  assert.equal(activeFeatureTab('/ebeam/cd-sem/m14a/recipe-search'), 'recipe-search')
  assert.equal(activeFeatureTab('/ebeam/cd-sem/m14a/hardware'), 'hardware')
  assert.equal(activeFeatureTab('/ebeam/cd-sem/device-statistics'), 'device-statistics')
  assert.equal(activeFeatureTab('/ebeam/cd-sem/skewvoir'), 'skewvoir')
})

test('장비 상태 and its storage sub-tab are the only pages that light 장비 상태', () => {
  assert.equal(activeFeatureTab('/ebeam/cd-sem/m14a'), 'index')
  // 스토리지 is a sub-tab OF 장비 상태 (EbeamEquipmentStatusSubTabs), so the
  // parent tab staying lit there is correct, not a second instance of the bug.
  assert.equal(activeFeatureTab('/ebeam/cd-sem/m14a/storage'), 'index')
})

test('실험실 pages claim no feature tab', () => {
  // Neither has a tab in the row, so the correct outcome is that NOTHING
  // highlights — which only holds if they are recognised rather than falling
  // through to the 장비 상태 default.
  assert.notEqual(activeFeatureTab('/ebeam/cd-sem/m14a/tttm'), 'index')
  assert.notEqual(activeFeatureTab('/ebeam/cd-sem/live-alarm'), 'index')
})

test('every feature slug is recognised — the fallback is never reached by one', () => {
  // The class of the bug: a slug added to FEATURE_SLUGS but not to whatever
  // decides the tab silently lights 장비 상태. Only 'storage' may map to it.
  for (const slug of FEATURE_SLUGS) {
    const tab = activeFeatureTab(`/ebeam/cd-sem/m14a/${slug}`)
    if (slug === 'storage') continue
    assert.notEqual(tab, 'index', `${slug} falls through to 장비 상태`)
  }
})

test('non-ebeam paths have no tab', () => {
  assert.equal(activeFeatureTab('/chat'), null)
  assert.equal(activeFeatureTab('/settings'), null)
})
