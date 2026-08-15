// front-dev-home/app/utils/skewvoirAnalysis/fdcSet.test.ts
// Pure-logic tests for the set-scope run × FDC-channel status matrix.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/fdcSet.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { buildFdcSetMatrix, type FdcSetRunSource } from './fdcSet.ts'
import type { FdcParamSummary } from '~/composables/useMsrFileApi'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const fdcParam = (over: Partial<FdcParamSummary>): FdcParamSummary => ({
  name: 'StigmaX', category: 'astigmatism', category_label: '비점수차', unit: '%',
  nominal: 0, mean: 1, std: 0.4, min: 0, max: 2, drift_sigma: 1.3, status: 'ok',
  ...over
})

const run = (msr: string, params: FdcParamSummary[]): FdcSetRunSource => ({
  msr, label: `EQ · ${msr}`, fdc_params: params
})

// ---------------------------------------------------------------------------
// Run columns
// ---------------------------------------------------------------------------

test('one run column per source, in the caller-supplied order', () => {
  const m = buildFdcSetMatrix([
    run('M2', [fdcParam({})]),
    run('M1', [fdcParam({})])
  ])
  assert.deepEqual(m.runs.map(r => r.msr), ['M2', 'M1'])
  assert.deepEqual(m.runs.map(r => r.label), ['EQ · M2', 'EQ · M1'])
})

// ---------------------------------------------------------------------------
// Cells — presence is reported, never imputed
// ---------------------------------------------------------------------------

test('a channel one run does not carry is blank there, never zero', () => {
  const stigma = fdcParam({ name: 'StigmaX', drift_sigma: 0.4, status: 'ok' })
  const focus = fdcParam({
    name: 'DefocusZ', category: 'defocus', category_label: '초점', drift_sigma: 2.7, status: 'bad'
  })
  const m = buildFdcSetMatrix([run('M1', [stigma, focus]), run('M2', [stigma])])

  const cells = channel(m, 'DefocusZ').cells
  assert.equal(cells.length, 2)
  assert.deepEqual(cells[0], { present: true, status: 'bad', driftSigma: 2.7 })
  assert.deepEqual(cells[1], { present: false, status: null, driftSigma: null })
})

// ---------------------------------------------------------------------------
// Grouping — the single-scope matrix's rule, reused verbatim
// ---------------------------------------------------------------------------

test('group headers use the Korean label the backend sent, first occurrence winning', () => {
  const m = buildFdcSetMatrix([
    run('M1', [
      fdcParam({ name: 'StigmaX', category: 'astigmatism', category_label: '비점수차' }),
      fdcParam({ name: 'DefocusZ', category: 'defocus', category_label: '초점' })
    ]),
    // A later run disagreeing on the label must not relabel the group.
    run('M2', [fdcParam({ name: 'DefocusZ', category: 'defocus', category_label: 'defocus' })])
  ])
  assert.deepEqual(
    m.groups.map(g => [g.category, g.label]),
    [['astigmatism', '비점수차'], ['defocus', '초점']]
  )
})

test('a category the backend left unlabelled falls back to its code', () => {
  const m = buildFdcSetMatrix([
    run('M1', [fdcParam({ name: 'Src', category: 'source', category_label: '' })])
  ])
  assert.deepEqual(m.groups.map(g => g.label), ['source'])
})

// ---------------------------------------------------------------------------
// Ranking
// ---------------------------------------------------------------------------

/** Params sharing one category, so ordering within a group is observable. */
const oneCategory = (specs: Partial<FdcParamSummary>[]) =>
  specs.map(s => fdcParam({ category: 'defocus', category_label: '초점', ...s }))

test('within a category the worst status leads, then the largest drift', () => {
  const m = buildFdcSetMatrix([
    run('M1', oneCategory([
      { name: 'Calm', status: 'ok', drift_sigma: 0.2 },
      { name: 'Drifting', status: 'warning', drift_sigma: 1.5 },
      { name: 'Broken', status: 'bad', drift_sigma: 3.1 },
      { name: 'Noisy', status: 'warning', drift_sigma: 2.4 }
    ]))
  ])
  assert.deepEqual(
    m.groups[0]?.channels.map(c => c.name),
    ['Broken', 'Noisy', 'Drifting', 'Calm']
  )
})

test('a channel is ranked by its WORST run, not by the first one listed', () => {
  const m = buildFdcSetMatrix([
    run('M1', oneCategory([
      { name: 'LateBad', status: 'ok', drift_sigma: 0.1 },
      { name: 'AlwaysWarn', status: 'warning', drift_sigma: 1.2 }
    ])),
    run('M2', oneCategory([
      { name: 'LateBad', status: 'bad', drift_sigma: 4.0 },
      { name: 'AlwaysWarn', status: 'warning', drift_sigma: 1.2 }
    ]))
  ])
  assert.deepEqual(m.groups[0]?.channels.map(c => c.name), ['LateBad', 'AlwaysWarn'])
  assert.equal(channel(m, 'LateBad').worstStatus, 'bad')
  assert.equal(channel(m, 'LateBad').maxDriftSigma, 4.0)
})

test('equal severity and drift tie-break on name, so renders never reorder', () => {
  const m = buildFdcSetMatrix([
    run('M1', oneCategory([
      { name: 'Zeta', status: 'ok', drift_sigma: 1 },
      { name: 'Alpha', status: 'ok', drift_sigma: 1 }
    ]))
  ])
  assert.deepEqual(m.groups[0]?.channels.map(c => c.name), ['Alpha', 'Zeta'])
})

// ---------------------------------------------------------------------------
// Roll-ups
// ---------------------------------------------------------------------------

test('each run column counts its own statuses and its missing channels', () => {
  const m = buildFdcSetMatrix([
    run('M1', oneCategory([
      { name: 'A', status: 'bad', drift_sigma: 3 },
      { name: 'B', status: 'warning', drift_sigma: 1 },
      { name: 'C', status: 'ok', drift_sigma: 0.1 }
    ])),
    run('M2', oneCategory([{ name: 'A', status: 'ok', drift_sigma: 0.2 }]))
  ])
  assert.deepEqual(m.runs[0], { msr: 'M1', label: 'EQ · M1', bad: 1, warning: 1, ok: 1, missing: 0 })
  assert.deepEqual(m.runs[1], { msr: 'M2', label: 'EQ · M2', bad: 0, warning: 0, ok: 1, missing: 2 })
})

test('the matrix reports how many channels are not shared by every run', () => {
  const m = buildFdcSetMatrix([
    run('M1', oneCategory([{ name: 'Shared' }, { name: 'OnlyHere' }])),
    run('M2', oneCategory([{ name: 'Shared' }]))
  ])
  assert.equal(m.channelCount, 2)
  assert.equal(m.partialChannelCount, 1)
})

test('an empty set yields an empty matrix rather than throwing', () => {
  const m = buildFdcSetMatrix([])
  assert.deepEqual(m.runs, [])
  assert.deepEqual(m.groups, [])
  assert.equal(m.channelCount, 0)
  assert.equal(m.partialChannelCount, 0)
})

test('a set whose runs carry no FDC channels at all yields no groups', () => {
  const m = buildFdcSetMatrix([run('M1', []), run('M2', [])])
  assert.equal(m.runs.length, 2)
  assert.deepEqual(m.groups, [])
  assert.equal(m.channelCount, 0)
})

// ---------------------------------------------------------------------------
// Research integrity
// ---------------------------------------------------------------------------

test('fdcSet.ts reads neither the mock health scalar, spm_dict, nor dynamic_fdc', () => {
  const src = readFileSync(fileURLToPath(new URL('./fdcSet.ts', import.meta.url)), 'utf8')
  // Strip comments so a caveat mentioning the words in prose does not trip this.
  const code = src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .map(l => l.replace(/\/\/.*$/, ''))
    .join('\n')
  assert.ok(!/\bhealth\b/.test(code), 'fdcSet.ts must not read the mock health scalar')
  assert.ok(!/spm_dict/.test(code), 'fdcSet.ts must not read the placeholder spm_dict')
  // Not a ban on the field, a ban on the GRAIN: dynamic_fdc is per sequence, and
  // folding sequences into a per-run cell here would silently mix two grains.
  // fdc_params is already one summary per run, which is why this view needs no
  // reduction at all.
  assert.ok(!/dynamic_fdc/.test(code), 'fdcSet.ts must stay at MSR grain')
})

/** Locate a channel row across every group. */
const channel = (m: ReturnType<typeof buildFdcSetMatrix>, name: string) => {
  const hit = m.groups.flatMap(g => g.channels).find(c => c.name === name)
  assert.ok(hit, `no channel row for ${name}`)
  return hit
}
