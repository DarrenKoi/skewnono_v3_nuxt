import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractSignature,
  compareToReference,
  buildAnalysisManifest,
  type SignatureSource
} from './compatibility.ts'
import type { CompatibilitySignature } from './types.ts'

// ---------------------------------------------------------------------------
// Fixture factory — a minimal MsrFileResponse-shaped source. The real mock
// response (MsrFileResponse) structurally satisfies SignatureSource, so these
// hand-crafted plain objects exercise the same extraction path.
// ---------------------------------------------------------------------------
interface Opts {
  recipe?: string
  unit?: string
  layoutHash?: string
  revision?: string
  mags?: number[]
  methods?: string[]
  parameter?: string
  noRecipe?: boolean
}

const source = (msr: string, opts: Opts = {}): SignatureSource => {
  const parameter = opts.parameter ?? 'CD_TOP'
  const mags = opts.mags ?? [200015, 200015]
  const methods = opts.methods ?? mags.map(() => 'Score')
  return {
    msr,
    exe_detail_info: {
      recipe_name: opts.noRecipe ? undefined : (opts.recipe ?? 'RCP_A'),
      idp_name: opts.noRecipe ? undefined : `/Recipe/${opts.recipe ?? 'RCP_A'}.idp`,
      idw_name: opts.noRecipe ? undefined : `/Recipe/${opts.recipe ?? 'RCP_A'}.idw`,
      wafer_size: '300000000',
      chip_array: '40,56',
      chip_pitch: '7500000,5357142',
      map_offset: '0,0',
      map_origin: '20,28',
      recipe_revision: opts.revision,
      site_layout_hash: opts.layoutHash
    },
    parameters: [{ parameter, unit: opts.unit ?? 'nm' }],
    rows: mags.map((m, i) => ({
      parameter,
      meas_method: methods[i] ?? 'Score',
      object_type: 'MP',
      meas_kind: 'Multi Point',
      meas_condition_mag: m,
      meas_condition_vac: 800,
      meas_condition_pixel: '512,512'
    }))
  }
}

// ---------------------------------------------------------------------------
// extractSignature — known vs unknown-safe fields
// ---------------------------------------------------------------------------
test('extractSignature marks recipe identity + unit KNOWN and revision/layout UNKNOWN', () => {
  const sig = extractSignature(source('msr-1', { recipe: 'RCP_A', unit: 'nm' }), 'CD_TOP')
  assert.equal(sig.recipe.state, 'known')
  assert.equal(sig.unit.state, 'known')
  if (sig.unit.state === 'known') assert.equal(sig.unit.value, 'nm')
  // Absent from the Phase-1 mock → never fabricated.
  assert.equal(sig.recipeRevision.state, 'unknown')
  assert.equal(sig.siteLayoutHash.state, 'unknown')
})

test('extractSignature keeps a present layout hash KNOWN (office-provided path)', () => {
  const sig = extractSignature(source('msr-1', { layoutHash: 'L1' }), 'CD_TOP')
  assert.equal(sig.siteLayoutHash.state, 'known')
  if (sig.siteLayoutHash.state === 'known') assert.equal(sig.siteLayoutHash.value, 'L1')
})

test('extractSignature reduces a per-row-varying field to single / mixed / unknown', () => {
  const single = extractSignature(source('m', { mags: [200015, 200015] }), 'CD_TOP')
  assert.equal(single.mag.state, 'single')

  const mixed = extractSignature(source('m', { mags: [200015, 250030] }), 'CD_TOP')
  assert.equal(mixed.mag.state, 'mixed')

  // 0 is the empty-row sentinel — dropped, leaving no real value → unknown.
  const empty = extractSignature(source('m', { mags: [0, 0] }), 'CD_TOP')
  assert.equal(empty.mag.state, 'unknown')
})

test('extractSignature flags missing recipe identity as unknown (drives metadata-missing)', () => {
  const sig = extractSignature(source('m', { noRecipe: true }), 'CD_TOP')
  assert.equal(sig.recipe.state, 'unknown')
})

// ---------------------------------------------------------------------------
// compareToReference — exclusion reason codes
// ---------------------------------------------------------------------------
const sig = (msr: string, opts: Opts = {}): CompatibilitySignature =>
  extractSignature(source(msr, opts), opts.parameter ?? 'CD_TOP')

test('compatible signatures produce no exclusion reasons', () => {
  const ref = sig('ref', { recipe: 'RCP_A', unit: 'nm' })
  assert.deepEqual(compareToReference(ref, sig('c', { recipe: 'RCP_A', unit: 'nm' })), [])
})

test('recipe / unit / method / layout conflicts each get a distinct reason code', () => {
  const ref = sig('ref', { recipe: 'RCP_A', unit: 'nm', layoutHash: 'L1', methods: ['Score', 'Score'] })
  assert.deepEqual(
    compareToReference(ref, sig('c', { recipe: 'RCP_B', unit: 'nm', layoutHash: 'L1', methods: ['Score', 'Score'] })),
    ['recipe-mismatch']
  )
  assert.deepEqual(
    compareToReference(ref, sig('c', { recipe: 'RCP_A', unit: 'um', layoutHash: 'L1', methods: ['Score', 'Score'] })),
    ['unit-mismatch']
  )
  assert.deepEqual(
    compareToReference(ref, sig('c', { recipe: 'RCP_A', unit: 'nm', layoutHash: 'L1', methods: ['Edge', 'Edge'] })),
    ['method-mismatch']
  )
  assert.deepEqual(
    compareToReference(ref, sig('c', { recipe: 'RCP_A', unit: 'nm', layoutHash: 'L2', methods: ['Score', 'Score'] })),
    ['layout-mismatch']
  )
})

test('unknown never conflicts with unknown — two unknown layouts are NOT a layout-mismatch', () => {
  const ref = sig('ref', { recipe: 'RCP_A', unit: 'nm' }) // layout unknown
  const cand = sig('c', { recipe: 'RCP_A', unit: 'nm' }) // layout unknown
  assert.equal(compareToReference(ref, cand).includes('layout-mismatch'), false)
})

test('a mixed acquisition field on either side never raises method-mismatch (no fabricated single value)', () => {
  const ref = sig('ref', { recipe: 'RCP_A', unit: 'nm', methods: ['Score', 'Edge'] }) // mixed
  const cand = sig('c', { recipe: 'RCP_A', unit: 'nm', methods: ['Width', 'Width'] }) // single, different
  assert.equal(compareToReference(ref, cand).includes('method-mismatch'), false)
})

test('missing recipe identity yields metadata-missing', () => {
  const ref = sig('ref', { recipe: 'RCP_A', unit: 'nm' })
  assert.deepEqual(compareToReference(ref, sig('c', { noRecipe: true, unit: 'nm' })), ['metadata-missing'])
})

// ---------------------------------------------------------------------------
// buildAnalysisManifest — the 12 / 10 / 8 / 2 acceptance example
// ---------------------------------------------------------------------------
test('buildAnalysisManifest reproduces 12 selected · 10 loaded · 8 compatible · 2 excluded', () => {
  const focus = 'msr-0'
  const loaded: SignatureSource[] = [
    source('msr-0', { recipe: 'RCP_A', unit: 'nm' }), // focus
    source('msr-1', { recipe: 'RCP_A', unit: 'nm' }),
    source('msr-2', { recipe: 'RCP_A', unit: 'nm' }),
    source('msr-3', { recipe: 'RCP_A', unit: 'nm' }),
    source('msr-4', { recipe: 'RCP_A', unit: 'nm' }),
    source('msr-5', { recipe: 'RCP_A', unit: 'nm' }),
    source('msr-6', { recipe: 'RCP_A', unit: 'nm' }),
    source('msr-7', { recipe: 'RCP_A', unit: 'nm' }),
    source('msr-8', { recipe: 'RCP_B', unit: 'nm' }), // recipe-mismatch
    source('msr-9', { recipe: 'RCP_A', unit: 'um' }) // unit-mismatch
  ]
  // 12 selected, only 10 came back loaded (msr-10, msr-11 failed to load).
  const requestedMsrs = [...loaded.map(f => f.msr), 'msr-10', 'msr-11']

  const manifest = buildAnalysisManifest(focus, loaded, 'CD_TOP', { requestedMsrs })

  assert.deepEqual(manifest.counts, { selected: 12, loaded: 10, compatible: 8, excluded: 2 })
  assert.equal(manifest.included.length, 8)
  assert.ok(manifest.included.includes('msr-0'))

  const reasonsByMsr = new Map(manifest.excluded.map(e => [e.msr, e.reasons]))
  assert.deepEqual(reasonsByMsr.get('msr-8'), ['recipe-mismatch'])
  assert.deepEqual(reasonsByMsr.get('msr-9'), ['unit-mismatch'])
  assert.equal(manifest.scope, 'set')
})

// ---------------------------------------------------------------------------
// Layout/coordinate-dependent readiness — ready / unavailable / limited
// ---------------------------------------------------------------------------
test('same known layout across the set → multi-MSR readiness is ready', () => {
  const files = [
    source('a', { recipe: 'RCP_A', unit: 'nm', layoutHash: 'L1' }),
    source('b', { recipe: 'RCP_A', unit: 'nm', layoutHash: 'L1' })
  ]
  const m = buildAnalysisManifest('a', files, 'CD_TOP')
  assert.equal(m.readiness.multiMsrDelta.status, 'ready')
  assert.equal(m.readiness.siteVariability.status, 'ready')
  assert.equal(m.readiness.sameSiteGallery.status, 'ready')
})

test('unknown layout (the Phase-1 mock reality) → readiness is unavailable', () => {
  const files = [
    source('a', { recipe: 'RCP_A', unit: 'nm' }),
    source('b', { recipe: 'RCP_A', unit: 'nm' })
  ]
  const m = buildAnalysisManifest('a', files, 'CD_TOP')
  assert.equal(m.readiness.multiMsrDelta.status, 'unavailable')
  assert.equal(m.readiness.sameSiteGallery.status, 'unavailable')
})

test('partial site overlap → limited with common-coverage in the reasons', () => {
  const files = [
    source('a', { recipe: 'RCP_A', unit: 'nm' }),
    source('b', { recipe: 'RCP_A', unit: 'nm' })
  ]
  const siteKeys = new Map<string, ReadonlySet<string>>([
    ['a', new Set(['s1', 's2', 's3'])],
    ['b', new Set(['s2', 's3', 's4'])]
  ])
  const m = buildAnalysisManifest('a', files, 'CD_TOP', { siteKeys })
  assert.equal(m.readiness.siteVariability.status, 'limited')
  assert.ok(m.readiness.siteVariability.reasons.some(r => r.includes('common-coverage')))
  assert.ok(m.readiness.siteVariability.reasons.some(r => r.includes('2')))
})

test('a single-MSR scope leaves multi-MSR readiness unavailable', () => {
  const m = buildAnalysisManifest('a', [source('a', { recipe: 'RCP_A', unit: 'nm', layoutHash: 'L1' })], 'CD_TOP')
  assert.equal(m.scope, 'single')
  assert.equal(m.readiness.multiMsrDelta.status, 'unavailable')
})
