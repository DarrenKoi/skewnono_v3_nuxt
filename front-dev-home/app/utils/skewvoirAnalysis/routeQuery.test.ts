import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  UNNAMED_PARAM,
  UNNAMED_PARAM_TOKEN,
  applyQueryPatch,
  decodeParam,
  encodeFdcAxis,
  encodeParam,
  focusIdentityFromRow,
  parseFdcAxis,
  parseMsrList,
  parseScope,
  parseSelection,
  parseView,
  qstr,
  toAnalysisQuery,
  type FocusIdentityRow
} from './routeQuery.ts'

test('qstr collapses an array query value to its first element', () => {
  assert.equal(qstr(['a', 'b']), 'a')
})

test('qstr collapses an empty string to undefined (not "")', () => {
  assert.equal(qstr(''), undefined)
  assert.equal(qstr([]), undefined)
})

test('qstr passes a plain string through unchanged', () => {
  assert.equal(qstr('msr-001'), 'msr-001')
})

test('qstr collapses null/undefined to undefined', () => {
  assert.equal(qstr(null), undefined)
  assert.equal(qstr(undefined), undefined)
})

test('parseMsrList splits, trims, and drops empties from the msrs query param', () => {
  assert.deepEqual(
    parseMsrList({ msrs: ' msr-a, msr-b ,,msr-c', msr: 'msr-a' }),
    ['msr-a', 'msr-b', 'msr-c']
  )
})

test('parseMsrList falls back to the single msr when msrs is absent', () => {
  assert.deepEqual(parseMsrList({ msr: 'msr-focus' }), ['msr-focus'])
})

test('parseMsrList falls back to the single msr when msrs is present but empty after trimming', () => {
  assert.deepEqual(parseMsrList({ msrs: ' , , ', msr: 'msr-focus' }), ['msr-focus'])
})

test('parseMsrList is empty when neither msrs nor msr is present', () => {
  assert.deepEqual(parseMsrList({}), [])
})

test('parseView passes through a whitelisted view kind', () => {
  assert.equal(parseView('time-series'), 'time-series')
  assert.equal(parseView('correlation'), 'correlation')
})

test('parseView falls back to "dashboard" for an unrecognized or missing value', () => {
  assert.equal(parseView('not-a-real-view'), 'dashboard')
  assert.equal(parseView(undefined), 'dashboard')
})

test('parseSelection is null when the URL has no lot (empty state)', () => {
  assert.equal(parseSelection({}), null)
  assert.equal(parseSelection({ recipe: 'R1' }), null)
})

test('parseSelection defaults mp to WAFER and capturedAt to the em-dash placeholder', () => {
  assert.deepEqual(parseSelection({ lot: 'LOT1' }), {
    lot: 'LOT1',
    recipe: '',
    eq: '',
    mp: 'WAFER',
    msr: '',
    capturedAt: '—'
  })
})

test('parseSelection preserves every explicit query field when present', () => {
  assert.deepEqual(
    parseSelection({ lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'GATE_CD', msr: 'msr-1', cap: '2026-07-16 09:00' }),
    { lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'GATE_CD', msr: 'msr-1', capturedAt: '2026-07-16 09:00' }
  )
})

test('parseScope honours an explicit scope param over the set size', () => {
  assert.equal(parseScope({ scope: 'set', msrs: 'msr-a' }), 'set')
  assert.equal(parseScope({ scope: 'single', msrs: 'msr-a,msr-b' }), 'single')
})

test('parseScope derives the scope from the set size for links with no scope param', () => {
  assert.equal(parseScope({ msrs: 'msr-a,msr-b' }), 'set')
  assert.equal(parseScope({ msrs: 'msr-a' }), 'single')
  assert.equal(parseScope({}), 'single')
})

const selection = {
  lot: 'LOT1',
  recipe: 'R1',
  eq: 'EQ1',
  mp: 'WAFER',
  msr: 'msr-focus',
  capturedAt: '—'
}

test('toAnalysisQuery defaults msrs to the single focus msr when no set is passed', () => {
  const q = toAnalysisQuery(selection)
  assert.equal(q.msrs, 'msr-focus')
  assert.equal(q.view, 'dashboard')
})

test('toAnalysisQuery joins an explicit curated set and drops falsy entries', () => {
  const q = toAnalysisQuery(selection, 'time-series', ['msr-a', '', 'msr-b'])
  assert.equal(q.msrs, 'msr-a,msr-b')
  assert.equal(q.view, 'time-series')
})

test('toAnalysisQuery falls back to [sel.msr] when the explicit set is empty', () => {
  const q = toAnalysisQuery(selection, 'time-series', [])
  assert.equal(q.msrs, 'msr-focus')
})

test('toAnalysisQuery emits scope only when one is given', () => {
  assert.equal('scope' in toAnalysisQuery(selection), false)
  assert.equal(toAnalysisQuery(selection, 'time-series', ['msr-a'], 'set').scope, 'set')
})

// The in-place focus move: applyQueryPatch(query, focusIdentityFromRow(msr,
// row)) is exactly what useSkewvoirAnalysis's setFocusedMsr → useSkewvoirRoute's
// setFocus → patchQuery does. Unlike the old search-re-entry path, the focus now
// moves via one router.replace (no history entry) that rewrites `msr` +
// `lot`/`eq`/`cap` while PRESERVING `msrs`/`view`/`mp` (and everything else).
// Per key a patch is three-valued: a string writes, `null` clears, `undefined`
// leaves the existing value UNTOUCHED.
const setFocusedMsr = (
  query: Record<string, string>,
  msr: string,
  row: FocusIdentityRow | undefined
) => applyQueryPatch(query, focusIdentityFromRow(msr, row))

test('setFocusedMsr rewrites msr + lot/eq/cap and PRESERVES msrs/view/mp (in-place, no history)', () => {
  const query = { lot: 'LOT-old', recipe: 'R1', eq: 'EQ-old', mp: 'GATE_CD', msr: 'msr-old', msrs: 'msr-old,msr-b,msr-c', cap: 'T-old', view: 'time-series' }
  const row: FocusIdentityRow = { lot_id: 'LOT-new', eqp_id: 'EQ-new', timestamp: 'T-new' }
  const next = setFocusedMsr(query, 'msr-b', row)
  // Focus + identity fields rewritten from the new focus row.
  assert.equal(next.msr, 'msr-b')
  assert.equal(next.lot, 'LOT-new')
  assert.equal(next.eq, 'EQ-new')
  assert.equal(next.cap, 'T-new')
  // Curated set, view, and parameter are PRESERVED (the whole point vs. re-entry).
  assert.equal(next.msrs, 'msr-old,msr-b,msr-c')
  assert.equal(next.view, 'time-series')
  assert.equal(next.mp, 'GATE_CD')
})

test('setFocusedMsr on a deep-link msr with no meas_hist row keeps the existing lot/eq/cap', () => {
  const query = { lot: 'LOT-old', eq: 'EQ-old', mp: 'WAFER', msr: 'msr-old', msrs: 'msr-old,msr-x', cap: 'T-old', view: 'gallery' }
  const next = setFocusedMsr(query, 'msr-x', undefined)
  assert.equal(next.msr, 'msr-x')
  // undefined identity fields are left UNTOUCHED, not blanked.
  assert.equal(next.lot, 'LOT-old')
  assert.equal(next.eq, 'EQ-old')
  assert.equal(next.cap, 'T-old')
  assert.equal(next.msrs, 'msr-old,msr-x')
  assert.equal(next.view, 'gallery')
})

test('applyQueryPatch clears a param on null and leaves untouched keys alone', () => {
  const next = applyQueryPatch(
    { site: 'S1', view: 'gallery', mp: 'WAFER' },
    { site: null, mp: undefined, filter: 'priority' }
  )
  assert.equal('site' in next, false)
  assert.equal(next.mp, 'WAFER')
  assert.equal(next.view, 'gallery')
  assert.equal(next.filter, 'priority')
})

// ── The unnamed dummy MP's URL sentinel ──────────────────────────────────────
// Its name is '', which qstr reads as absent, so without a sentinel the reviewer
// could never select it — and it has images worth reviewing.

test('encodeParam swaps the empty name for the sentinel and leaves names alone', () => {
  assert.equal(encodeParam(UNNAMED_PARAM), UNNAMED_PARAM_TOKEN)
  assert.equal(encodeParam('CD_TOP'), 'CD_TOP')
})

test('decodeParam turns the sentinel back into the empty name', () => {
  assert.equal(decodeParam(UNNAMED_PARAM_TOKEN), UNNAMED_PARAM)
  assert.equal(decodeParam('CD_TOP'), 'CD_TOP')
})

test('decodeParam keeps a genuinely absent mp absent (not the unnamed param)', () => {
  // The distinction the sentinel exists to preserve: "no selection" and "the
  // parameter whose name is empty" must not collapse into each other.
  assert.equal(decodeParam(undefined), undefined)
  assert.equal(decodeParam(''), undefined)
})

test('encode → decode round-trips the unnamed parameter', () => {
  assert.equal(decodeParam(encodeParam(UNNAMED_PARAM)), UNNAMED_PARAM)
  assert.equal(decodeParam(encodeParam('SIDEWALL_ANGLE')), 'SIDEWALL_ANGLE')
})

test('parseSelection resolves the sentinel to the unnamed parameter', () => {
  const sel = parseSelection({ lot: 'L1', mp: UNNAMED_PARAM_TOKEN })
  assert.equal(sel?.mp, UNNAMED_PARAM)
})

test('parseSelection still defaults a missing mp to WAFER', () => {
  assert.equal(parseSelection({ lot: 'L1' })?.mp, 'WAFER')
  // A blank mp is absent, not the unnamed parameter — only the sentinel means that.
  assert.equal(parseSelection({ lot: 'L1', mp: '' })?.mp, 'WAFER')
})

test('toAnalysisQuery writes the sentinel so an unnamed-MP link survives a share', () => {
  const sel = {
    lot: 'L1', recipe: 'R1', eq: 'EQ1', mp: UNNAMED_PARAM, msr: 'M1', capturedAt: '2026-05-09'
  }
  const query = toAnalysisQuery(sel)
  assert.equal(query.mp, UNNAMED_PARAM_TOKEN)
  assert.equal(parseSelection(query as never)?.mp, UNNAMED_PARAM)
})

test('fdcaxis defaults to the parameter-scoped axis and accepts only known modes', () => {
  assert.equal(parseFdcAxis(undefined), 'param')
  assert.equal(parseFdcAxis(''), 'param')
  assert.equal(parseFdcAxis('param'), 'param')
  assert.equal(parseFdcAxis('all'), 'all')
  // A hand-edited link must not render an axis nobody implemented.
  assert.equal(parseFdcAxis('whole-msr'), 'param')
})

test('clearing fdcaxis drops it from the query rather than writing the default', () => {
  const next = applyQueryPatch({ view: 'fdc', fdcaxis: 'all' }, { fdcaxis: null })
  assert.deepEqual(next, { view: 'fdc' })
})

test('encodeFdcAxis / parseFdcAxis round-trip, and the default stays out of the URL', () => {
  assert.equal(parseFdcAxis(encodeFdcAxis('all')), 'all')
  assert.equal(encodeFdcAxis('param'), null) // default stays out of the URL
  assert.equal(encodeFdcAxis('all'), 'all')
})

test('the fdc view kind parses and survives a round trip', () => {
  assert.equal(parseView('fdc'), 'fdc')
  assert.equal(parseView('time-series'), 'time-series')
  // Still whitelisted — a hand-edited link falls back to the Dashboard.
  assert.equal(parseView('fdc-analysis'), 'dashboard')
})
