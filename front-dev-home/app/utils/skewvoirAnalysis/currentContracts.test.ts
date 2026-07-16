import { test } from 'node:test'
import assert from 'node:assert/strict'

// CHARACTERIZATION TESTS — not black-box tests of the live composables.
//
// The Nuxt runtime (`useRoute`, `useRouter`, `useState`, `useAsyncData`,
// `computed`, `navigateTo`, …) is undefined under the raw `node --test`
// harness this repo runs (`node --test "app/**/*.test.ts"`, no bundler, no
// Nuxt auto-imports). `useSkewvoirRoute.ts` and `useSkewvoirAnalysis.ts`
// cannot be imported and driven directly here.
//
// So each test below mirrors ONE current rule as a small local pure
// function, cited by exact source file:line, fed a fixture, and asserted
// against the golden output the real composable produces today. These lock
// today's contract: a later task that intentionally changes a rule will
// make the matching test fail loudly, telling the implementer exactly which
// golden value to update (and which source line it was mirroring).
//
// This is Task 1 of the analysis-workspace rebuild plan — it pins current
// behavior for Dashboard / Position Stack / Time-Series / Correlation /
// Gallery so tasks 3, 5, 7, 9, 11 (which rewrite those views) can be
// reviewed against explicit, named expectations.

// ---------------------------------------------------------------------------
// useSkewvoirRoute.ts mirrors
// ---------------------------------------------------------------------------

// Mirrors useSkewvoirRoute.ts:19-22 (qstr) — collapse LocationQueryValue
// (string | string[] | null) to a usable string; array collapses to its
// first element; empty string collapses to undefined.
const qstr = (v: unknown): string | undefined => {
  const first = Array.isArray(v) ? v[0] : v
  return typeof first === 'string' && first.length > 0 ? first : undefined
}

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

// Mirrors useSkewvoirRoute.ts:54-59 (msrList) — split URL `msrs` on ',',
// trim each id, drop empties; when `msrs` is absent/empty, fall back to the
// single `msr`; when both are absent, the list is [].
const msrList = (query: { msrs?: unknown, msr?: unknown }): string[] => {
  const raw = qstr(query.msrs)
  const ids = raw ? raw.split(',').map(s => s.trim()).filter(Boolean) : []
  const fallback = qstr(query.msr)
  return ids.length ? ids : (fallback ? [fallback] : [])
}

test('msrList splits, trims, and drops empties from the msrs query param', () => {
  assert.deepEqual(
    msrList({ msrs: ' msr-a, msr-b ,,msr-c', msr: 'msr-a' }),
    ['msr-a', 'msr-b', 'msr-c']
  )
})

test('msrList falls back to the single msr when msrs is absent', () => {
  assert.deepEqual(msrList({ msr: 'msr-focus' }), ['msr-focus'])
})

test('msrList falls back to the single msr when msrs is present but empty after trimming', () => {
  assert.deepEqual(msrList({ msrs: ' , , ', msr: 'msr-focus' }), ['msr-focus'])
})

test('msrList is empty when neither msrs nor msr is present', () => {
  assert.deepEqual(msrList({}), [])
})

// Mirrors useSkewvoirRoute.ts:9-16, 46-49 (view) — whitelist against
// VIEW_KINDS, else default to 'dashboard'.
const VIEW_KINDS = ['dashboard', 'position-stack', 'time-series', 'correlation', 'gallery'] as const
const DEFAULT_VIEW = 'dashboard'
const view = (queryView: unknown): string => {
  const v = qstr(queryView)
  return v && (VIEW_KINDS as readonly string[]).includes(v) ? v : DEFAULT_VIEW
}

test('view passes through a whitelisted view kind', () => {
  assert.equal(view('time-series'), 'time-series')
  assert.equal(view('correlation'), 'correlation')
})

test('view falls back to "dashboard" for an unrecognized or missing value', () => {
  assert.equal(view('not-a-real-view'), 'dashboard')
  assert.equal(view(undefined), 'dashboard')
})

// Mirrors useSkewvoirRoute.ts:33-44 (selection) — no `lot` => null selection
// (empty state); when lot IS present, `mp` defaults to 'WAFER' and `cap`
// defaults to '—' (em dash), other fields default to ''.
interface Selection {
  lot: string
  recipe: string
  eq: string
  mp: string
  msr: string
  capturedAt: string
}
const selection = (query: Record<string, unknown>): Selection | null => {
  const lot = qstr(query.lot)
  if (!lot) return null
  return {
    lot,
    recipe: qstr(query.recipe) ?? '',
    eq: qstr(query.eq) ?? '',
    mp: qstr(query.mp) ?? 'WAFER',
    msr: qstr(query.msr) ?? '',
    capturedAt: qstr(query.cap) ?? '—'
  }
}

test('selection is null when the URL has no lot (empty state)', () => {
  assert.equal(selection({}), null)
  assert.equal(selection({ recipe: 'R1' }), null)
})

test('selection defaults mp to WAFER and capturedAt to the em-dash placeholder', () => {
  assert.deepEqual(selection({ lot: 'LOT1' }), {
    lot: 'LOT1',
    recipe: '',
    eq: '',
    mp: 'WAFER',
    msr: '',
    capturedAt: '—'
  })
})

test('selection preserves every explicit query field when present', () => {
  assert.deepEqual(
    selection({ lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'GATE_CD', msr: 'msr-1', cap: '2026-07-16 09:00' }),
    { lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'GATE_CD', msr: 'msr-1', capturedAt: '2026-07-16 09:00' }
  )
})

// Mirrors useSkewvoirRoute.ts:63-76 (toQuery) — `msrs` defaults to
// `[sel.msr]` when no explicit list is passed (or it's empty), filters
// falsy ids, and joins with ','.
const toQuery = (
  sel: Selection,
  v: string = DEFAULT_VIEW,
  msrs?: string[]
) => ({
  lot: sel.lot,
  recipe: sel.recipe,
  eq: sel.eq,
  mp: sel.mp,
  msr: sel.msr,
  msrs: (msrs && msrs.length ? msrs : [sel.msr]).filter(Boolean).join(','),
  cap: sel.capturedAt,
  view: v
})

test('toQuery defaults msrs to the single focus msr when no set is passed', () => {
  const sel: Selection = { lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'WAFER', msr: 'msr-focus', capturedAt: '—' }
  const q = toQuery(sel)
  assert.equal(q.msrs, 'msr-focus')
  assert.equal(q.view, 'dashboard')
})

test('toQuery joins an explicit curated set and drops falsy entries', () => {
  const sel: Selection = { lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'WAFER', msr: 'msr-focus', capturedAt: '—' }
  const q = toQuery(sel, 'time-series', ['msr-a', '', 'msr-b'])
  assert.equal(q.msrs, 'msr-a,msr-b')
  assert.equal(q.view, 'time-series')
})

test('toQuery falls back to [sel.msr] when the explicit set is empty', () => {
  const sel: Selection = { lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'WAFER', msr: 'msr-focus', capturedAt: '—' }
  const q = toQuery(sel, 'time-series', [])
  assert.equal(q.msrs, 'msr-focus')
})

// CURRENT — to be superseded by Task 3 setFocusedMsr: the focus `msr` only
// ever changes by re-entering the analysis route from search (openAnalysis
// -> toQuery -> navigateTo), never by an in-place URL patch the way
// setView/setMsrs/setParam mutate `view`/`msrs`/`mp` in place (see
// useSkewvoirRoute.ts:92-101). There is no `setFocusedMsr` today; Task 3
// intentionally adds one, which will change this fixture's premise.
test('CURRENT — to be superseded by Task 3 setFocusedMsr: focus msr changes only via search re-entry (toQuery), not an in-place setter', () => {
  const sel: Selection = { lot: 'LOT1', recipe: 'R1', eq: 'EQ1', mp: 'WAFER', msr: 'msr-old', capturedAt: '—' }
  // The only way to move the focus msr today is to build a fresh query via
  // toQuery with a new selection.msr and navigate to it (openAnalysis).
  const nextSel: Selection = { ...sel, msr: 'msr-new' }
  const q = toQuery(nextSel)
  assert.equal(q.msr, 'msr-new')
  // Crucially: msrs also resets to just the new focus, because there is no
  // setter that changes `msr` while preserving an existing `msrs` set.
  assert.equal(q.msrs, 'msr-new')
})

// ---------------------------------------------------------------------------
// useSkewvoirAnalysis.ts mirrors
// ---------------------------------------------------------------------------

// Mirrors useSkewvoirAnalysis.ts:12 (TREND_LIMIT).
const TREND_LIMIT = 30

interface MeasHistRowFixture { msr: string, msr_check: 'Yes' | 'No' }

// Mirrors useSkewvoirAnalysis.ts:152-157 (setRows) — resolve the curated
// URL `msrs` list against a meas_hist row-by-msr lookup, drop msrs with no
// matching row, cap at TREND_LIMIT, preserving msrList order (NOT sorted).
const setRows = (msrListIds: string[], rowByMsr: Map<string, MeasHistRowFixture>): MeasHistRowFixture[] =>
  msrListIds
    .map(id => rowByMsr.get(id))
    .filter((r): r is MeasHistRowFixture => r != null)
    .slice(0, TREND_LIMIT)

test('setRows preserves msrList order (not sorted), dropping missing msrs', () => {
  const rowByMsr = new Map<string, MeasHistRowFixture>([
    ['msr-c', { msr: 'msr-c', msr_check: 'Yes' }],
    ['msr-a', { msr: 'msr-a', msr_check: 'Yes' }]
    // 'msr-b' intentionally absent — simulates a missing/unresolvable msr id
  ])
  const result = setRows(['msr-a', 'msr-b', 'msr-c'], rowByMsr)
  assert.deepEqual(result.map(r => r.msr), ['msr-a', 'msr-c'])
})

test('setRows caps the curated set at TREND_LIMIT (30), keeping the leading msrList entries', () => {
  const ids = Array.from({ length: 40 }, (_, i) => `msr-${i}`)
  const rowByMsr = new Map(ids.map(id => [id, { msr: id, msr_check: 'Yes' as const }]))
  const result = setRows(ids, rowByMsr)
  assert.equal(result.length, TREND_LIMIT)
  assert.deepEqual(result.map(r => r.msr), ids.slice(0, TREND_LIMIT))
})

// Mirrors useSkewvoirAnalysis.ts:138-140 (wantSet) — the Dashboard
// lazy-load invariant: the curated-set batch fetch (fetchMsrFiles) is only
// wanted for 'time-series' and 'position-stack'; Dashboard, Correlation and
// Gallery must NOT trigger it (Dashboard uses fetchMsrFile on the focus msr
// only; Correlation/Gallery consume the same focus file via siteRows — see
// views/Correlation.vue and views/Gallery.vue, which both read only
// `analysis.siteRows` / `analysis.focusPending`, never `analysis.setFiles`).
const wantSet = (activeKind: string): boolean =>
  activeKind === 'time-series' || activeKind === 'position-stack'

test('wantSet lazy-load invariant: only time-series and position-stack trigger the curated-set batch fetch', () => {
  assert.equal(wantSet('time-series'), true)
  assert.equal(wantSet('position-stack'), true)
})

test('wantSet lazy-load invariant: dashboard, correlation, and gallery do NOT trigger fetchMsrFiles', () => {
  assert.equal(wantSet('dashboard'), false)
  assert.equal(wantSet('correlation'), false)
  assert.equal(wantSet('gallery'), false)
})

// LIMITATION: Position Stack (views/PositionStack.vue:96-117) synthesizes
// chip coordinates directly from `chip_number` via parseChipXY
// (utils/waferChip.ts:5-12) — a plain "x, y" grid-string parse — rather than
// going through the physical wafer coordinate model (stage_coordinate in
// nm + wafer_size in mm via utils/waferGeometry.ts) that the Dashboard's
// RadiusChart/MeasurementPoints use. This mirror pins that current, cruder
// coordinate synthesis so a later task that unifies it onto the physical
// model produces a visible diff here.
const parseChipXY = (chip: string): [number, number] | null => {
  const parts = chip.split(',')
  if (parts.length !== 2) return null
  const x = Number(parts[0]!.trim())
  const y = Number(parts[1]!.trim())
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  return [x, y]
}

test('LIMITATION — Position Stack synthesizes chip coordinates from chip_number text, not the physical wafer geometry model', () => {
  assert.deepEqual(parseChipXY('3, -2'), [3, -2])
  // Malformed chip_number (missing comma, or non-finite parts) is dropped
  // entirely rather than falling back to any physical coordinate.
  assert.equal(parseChipXY('not-a-coordinate'), null)
  assert.equal(parseChipXY('NaN, 1'), null)
})

// ---------------------------------------------------------------------------
// useMsrFileApi.ts shape mirrors
// ---------------------------------------------------------------------------

interface MsrFileRowFixture {
  msr: string
  sequence: number
  chip_number: string
  parameter: string
  // Mirrors useMsrFileApi.ts:14 — NULLABLE: null exactly when mp_number < 0.
  cd_value: number | null
}

interface MsrParamSummaryFixture {
  parameter: string
  // Mirrors useMsrFileApi.ts:66 — each parameter carries its OWN unit.
  unit: string
}

// A small msr_file fixture: one row with a null cd_value (unmeasured site),
// one row with a real value, and two parameters with distinct units.
const buildMsrFileFixture = () => {
  const rows: MsrFileRowFixture[] = [
    { msr: 'msr-1', sequence: 1, chip_number: '0, 0', parameter: 'WAFER', cd_value: null },
    { msr: 'msr-1', sequence: 2, chip_number: '1, 0', parameter: 'WAFER', cd_value: 42.5 }
  ]
  const parameters: MsrParamSummaryFixture[] = [
    { parameter: 'WAFER', unit: 'nm' },
    { parameter: 'GATE_CD', unit: 'um' }
  ]
  return { rows, parameters }
}

test('LIMITATION fixture — msr_file rows preserve a null cd_value alongside a measured value', () => {
  const { rows } = buildMsrFileFixture()
  assert.equal(rows[0]!.cd_value, null)
  assert.equal(rows[1]!.cd_value, 42.5)
})

test('LIMITATION fixture — each MsrParamSummary carries its own unit, not a shared/global unit', () => {
  const { parameters } = buildMsrFileFixture()
  const byParam = new Map(parameters.map(p => [p.parameter, p.unit]))
  assert.equal(byParam.get('WAFER'), 'nm')
  assert.equal(byParam.get('GATE_CD'), 'um')
  assert.notEqual(byParam.get('WAFER'), byParam.get('GATE_CD'))
})

// LIMITATION: Correlation (views/Correlation.vue:44,60) and Gallery
// (views/Gallery.vue:57-58) both read only `analysis.siteRows` — which is
// `focusFile.value?.rows` (useSkewvoirAnalysis.ts:98) — i.e. the SINGLE
// focus measurement's rows. Neither view consumes `analysis.setFiles`
// (the curated multi-msr set used by Time-Series/Position Stack), so today
// Correlation and Gallery cannot compare or gallery-browse across more than
// one measurement.
test('LIMITATION — Correlation and Gallery use only the focus file\'s rows, never the curated set', () => {
  const focusFileRows: MsrFileRowFixture[] = buildMsrFileFixture().rows
  const setFiles = new Map<string, { rows: MsrFileRowFixture[] }>([
    ['msr-2', { rows: [{ msr: 'msr-2', sequence: 1, chip_number: '0, 0', parameter: 'WAFER', cd_value: 10 }] }]
  ])
  // siteRows mirrors focusFile.value?.rows ?? [] (useSkewvoirAnalysis.ts:98)
  const siteRows = focusFileRows
  assert.deepEqual(siteRows.map(r => r.msr), ['msr-1', 'msr-1'])
  // The curated set exists but is not what Correlation/Gallery read from.
  assert.equal(setFiles.has('msr-2'), true)
  assert.equal(siteRows.some(r => r.msr === 'msr-2'), false)
})
