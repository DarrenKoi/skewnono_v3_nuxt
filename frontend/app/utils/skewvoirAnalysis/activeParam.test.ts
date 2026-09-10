import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolveActiveParam, activeParamPool } from './activeParam.ts'

test('single scope honours a URL mp the focus file has', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'GATE_CD', focusParams: ['WAFER', 'GATE_CD'], setParams: []
  }), 'GATE_CD')
})

test('single scope falls back to the first NAMED param when the focus lacks the URL mp', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'GATE_CD', focusParams: ['', 'WAFER'], setParams: []
  }), 'WAFER')
})

test('set scope accepts a param the focus lacks but another set member has', () => {
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }), 'GATE_CD')
})

test('set scope with EMPTY setParams falls back to focus rules — the set files are not loaded yet', () => {
  // shouldLoadSet() excludes the dashboard view, so scope=set + view=dashboard
  // leaves setFiles empty. Judging against an empty pool would reject every
  // parameter and corrupt the URL.
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: []
  }), 'WAFER')
})

test('an explicit pick of the unnamed settling MP is honoured, but never defaulted to', () => {
  // The unnamed MP's name IS the empty string, so `urlMp != null` (not truthy).
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: '', focusParams: ['', 'WAFER'], setParams: ['', 'WAFER']
  }), '')
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: undefined, focusParams: ['', 'WAFER'], setParams: ['', 'WAFER']
  }), 'WAFER')
})

test('a file whose only parameter is the unnamed MP falls back to it', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: undefined, focusParams: [''], setParams: []
  }), '')
})

test('no parameters at all yields the URL mp, else the empty string', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'WAFER', focusParams: [], setParams: []
  }), 'WAFER')
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: undefined, focusParams: [], setParams: []
  }), '')
})

test('activeParamPool widens to the set only under set scope with a loaded set', () => {
  assert.deepEqual(activeParamPool({
    scope: 'set', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD'],
    setComplete: true
  }).params, ['WAFER', 'GATE_CD'])
  assert.deepEqual(activeParamPool({
    scope: 'single', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }).params, ['WAFER'])
})

// --- Pool authority: may this pool rewrite the URL, or only render? ---
// The pool answers two masters. Rendering may always fall back to a narrower
// pool; canonicalizing the URL may not, because a rewrite DESTROYS the user's
// pick. These assert the flag that keeps the second master honest.

test('single scope is always authoritative — the focus file is the whole subject', () => {
  assert.equal(activeParamPool({
    scope: 'single', urlMp: undefined, focusParams: ['WAFER'], setParams: []
  }).authoritative, true)
})

test('a fully loaded set is authoritative', () => {
  assert.equal(activeParamPool({
    scope: 'set', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD'],
    setComplete: true
  }).authoritative, true)
})

test('set scope with an unloaded set is NOT authoritative — the dashboard case', () => {
  // shouldLoadSet() excludes the dashboard, so setFiles is empty there and the
  // pool silently narrows to the focus file. Rewriting the URL from it would
  // discard a set-only parameter the moment the user opens the dashboard.
  assert.equal(activeParamPool({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: [], setComplete: false
  }).authoritative, false)
})

test('set scope with loaded files that carry NO parameters is NOT authoritative', () => {
  // setParams is the union over loaded files, so files with empty `parameters`
  // leave it empty and the pool falls back to focus — while a guard phrased as
  // "are any files loaded?" would wave this through.
  assert.equal(activeParamPool({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: [], setComplete: true
  }).authoritative, false)
})

test('a PARTIALLY loaded set is NOT authoritative', () => {
  // /api/msr-files returns found MSRs only and silently skips the rest, so a
  // 5-msr set can settle at 3 files. The union of 3 is right for rendering and
  // wrong as the authority for the URL: a parameter only the 2 missing
  // measurements carry would be rewritten away and lost.
  assert.equal(activeParamPool({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: ['WAFER', 'CD_BOT'],
    setComplete: false
  }).authoritative, false)
})

test('setComplete defaults to NOT authoritative when omitted', () => {
  // Fail-safe: forgetting the field can only suppress a URL write, never permit
  // a wrong one.
  assert.equal(activeParamPool({
    scope: 'set', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }).authoritative, false)
})

test('rendering still falls back while the pool is non-authoritative', () => {
  // The two masters stay separated: resolveActiveParam ignores authority, so a
  // dashboard under set scope keeps rendering the focus fallback even though
  // the URL is now left alone.
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: [], setComplete: false
  }), 'WAFER')
})

// --- Coverage-ranked default (the Time-Series "no trend" bug) -----------------
// A set assembled from different recipes shares only some parameters. The
// default has to land on one the set can actually COMPARE, or the view it was
// chosen for renders its own empty state.

test('set scope defaults to the param the MOST measurements share, not the first one seen', () => {
  // The union's insertion order is the first measurement's parameter list, so
  // ASPECT_RATIO leads it — and exactly one measurement carries it. CD_BOTTOM
  // is carried by two, so it is the only default that can draw a trend.
  assert.equal(resolveActiveParam({
    scope: 'set',
    urlMp: 'WAFER', // search's hardcoded hand-off; no measurement has it
    focusParams: ['ASPECT_RATIO', 'CONTACT_CD'],
    setParams: ['ASPECT_RATIO', 'CONTACT_CD', 'CD_BOTTOM', 'SIDEWALL_ANGLE'],
    setCoverage: new Map([['ASPECT_RATIO', 1], ['CONTACT_CD', 1], ['CD_BOTTOM', 2], ['SIDEWALL_ANGLE', 2]])
  }), 'CD_BOTTOM')
})

test('coverage ties keep the pool order, so the ranking stays deterministic', () => {
  assert.equal(resolveActiveParam({
    scope: 'set',
    urlMp: undefined,
    focusParams: [],
    setParams: ['SIDEWALL_ANGLE', 'CD_BOTTOM'],
    setCoverage: new Map([['CD_BOTTOM', 2], ['SIDEWALL_ANGLE', 2]])
  }), 'SIDEWALL_ANGLE')
})

test('the unnamed settling MP never wins the coverage ranking, however well covered', () => {
  // It is measured first in every recipe, so it is usually the BEST-covered
  // parameter in a mixed set — and it is never a default (isNamedParam).
  assert.equal(resolveActiveParam({
    scope: 'set',
    urlMp: undefined,
    focusParams: [],
    setParams: ['', 'CD_BOTTOM'],
    setCoverage: new Map([['', 4], ['CD_BOTTOM', 2]])
  }), 'CD_BOTTOM')
})

test('no shared param: the ranking still returns a drawable single-coverage param, not nothing', () => {
  // Nothing is comparable here. The view says so in its empty state; the
  // resolver must still name a parameter so the picker and panels have one.
  assert.equal(resolveActiveParam({
    scope: 'set',
    urlMp: undefined,
    focusParams: [],
    setParams: ['ASPECT_RATIO', 'GATE_CD'],
    setCoverage: new Map([['ASPECT_RATIO', 1], ['GATE_CD', 1]])
  }), 'ASPECT_RATIO')
})

test('coverage is OPTIONAL — omitting it keeps the first-named-param behaviour', () => {
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: undefined, focusParams: [], setParams: ['ASPECT_RATIO', 'CD_BOTTOM']
  }), 'ASPECT_RATIO')
})
