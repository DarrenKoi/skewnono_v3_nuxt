// front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts
// Pure-logic tests for the single-MSR visual-evidence review queue.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/gallery.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { buildReviewQueue, resolveEvidenceOnly, reviewImage } from './gallery.ts'
import { parseWaferGeometry } from '../waferGeometry.ts'
import type { MsrFileRow, ExeDetailInfo } from '~/composables/useMsrFileApi'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

const exe = (): ExeDetailInfo => ({
  class_name: 'C1', recipe_name: 'RCP_A', idp_name: '/Recipe/RCP_A.idp', lot_id: 'LOT1',
  process: 'P1', wafer_id: 'W1', idw_name: '/Recipe/RCP_A.idw', chip_array: '40,56',
  chip_pitch: '7500000,5357142', wafer_size: '300000000', map_offset: '0,0', map_origin: '20,28'
})

const geo = () => parseWaferGeometry(exe())

// A realistic wafer: 20 collinear sites (CD rises 0.5 nm/mm along +x → residual
// ~0), whose count keeps a single site's leverage low, plus ONE mid-range site
// (SEQ_OUTLIER) that jumps far off that line (a big LOCAL residual the OLS fit
// cannot mask), plus one failed site (SEQ_FAIL, cd null, mp -1) for the failure
// layer. Every measured site carries an image; the failure carries none.
const N_CLEAN = 20
const SEQ_OUTLIER = 100
const SEQ_FAIL = 200

const mixedRows = (): MsrFileRow[] => {
  const rows: MsrFileRow[] = []
  // Clean line: radius 0,4,8,… mm along +x (stage x = 150e6 + r·1e6 nm).
  for (let i = 0; i < N_CLEAN; i++) {
    const rMm = i * 4
    rows.push(row({
      sequence: i + 1,
      chip_number: `${i}, 0`,
      stage_coordinate: `${150000000 + rMm * 1000000},150000000`,
      cd_value: 100 + 0.5 * rMm,
      mp_image_name_01: `img-${i + 1}.svg`
    }))
  }
  // Mid-range local outlier (radius 40 mm, line ≈ 120, actual 320).
  rows.push(row({
    sequence: SEQ_OUTLIER,
    chip_number: '10, 0',
    stage_coordinate: '190000000,150000000',
    cd_value: 320,
    mp_image_name_01: 'img-outlier.svg'
  }))
  // Failed site (no image).
  rows.push(row({
    sequence: SEQ_FAIL,
    chip_number: '9, 9',
    stage_coordinate: '150000000,150000000',
    cd_value: null,
    mp_number: -1,
    no_of_mp_image: 0,
    mp_image_name_01: ''
  }))
  return rows
}

// ---------------------------------------------------------------------------

test('default sort: failure first, then largest residual magnitude', () => {
  const q = buildReviewQueue(mixedRows(), 'CD_TOP', geo())
  // The failure is always first.
  assert.equal(q.entries[0]!.sequence, SEQ_FAIL)
  assert.ok(q.entries[0]!.reasons.includes('failure'))
  // The mid-range outlier carries the largest residual among measured sites — next.
  assert.equal(q.entries[1]!.sequence, SEQ_OUTLIER)
  assert.ok(q.entries[1]!.reasons.includes('residual'))
  // Residual magnitude is non-increasing across the measured (non-failure) tail.
  const mags = q.entries.slice(1).map(e => Math.abs(e.residual ?? 0))
  for (let i = 1; i < mags.length; i++) assert.ok(mags[i - 1]! >= mags[i]!)
})

test('sequence is the tiebreak when the primary group and residual magnitude tie', () => {
  // Two failures (residual null → magnitude 0), given out of order: they must
  // come back ordered by sequence.
  const rows = [
    row({ sequence: 7, chip_number: '7, 0', cd_value: null, mp_number: -1 }),
    row({ sequence: 3, chip_number: '3, 0', cd_value: null, mp_number: -1 })
  ]
  const q = buildReviewQueue(rows, 'CD_TOP', geo())
  assert.deepEqual(q.entries.map(e => e.sequence), [3, 7])
})

test('a site with no image still produces an evidence entry (no image names)', () => {
  const rows = [
    row({ sequence: 1, chip_number: '0, 0', cd_value: 100, no_of_mp_image: 0, mp_image_name_01: '' })
  ]
  const q = buildReviewQueue(rows, 'CD_TOP', geo())
  assert.equal(q.entries.length, 1)
  assert.deepEqual(q.entries[0]!.images, [])
  assert.equal(reviewImage(q.entries[0]!), null)
  assert.equal(q.entries[0]!.hasImage, false)
})

test('the representative image is the head of the list, never stored beside it', () => {
  const q = buildReviewQueue(mixedRows(), 'CD_TOP', geo())
  for (const entry of q.entries) {
    assert.equal(reviewImage(entry), entry.images[0] ?? null)
    assert.equal(entry.hasImage, entry.images.length > 0)
  }
})

test('every parameter row yields exactly one entry (no image row is ever dropped)', () => {
  const q = buildReviewQueue(mixedRows(), 'CD_TOP', geo())
  assert.equal(q.entries.length, N_CLEAN + 2)
})

test('vendor score is a monitoring badge only — never a verdict reason', () => {
  // All sites collinear (no residual outliers); one site carries a deep-low
  // measurement score so it earns a monitoring badge but no evidence reason.
  const rows = [
    row({ sequence: 1, chip_number: '0, 0', stage_coordinate: '150000000,150000000', cd_value: 100, measurement_score: 900 }),
    row({ sequence: 2, chip_number: '1, 0', stage_coordinate: '160000000,150000000', cd_value: 105, measurement_score: 910 }),
    row({ sequence: 3, chip_number: '2, 0', stage_coordinate: '170000000,150000000', cd_value: 110, measurement_score: 905 }),
    row({ sequence: 4, chip_number: '3, 0', stage_coordinate: '180000000,150000000', cd_value: 115, measurement_score: 5 }) // deep-low vendor score
  ]
  const q = buildReviewQueue(rows, 'CD_TOP', geo())
  const low = q.entries.find(e => e.sequence === 4)!
  // Vendor score never leaks into reasons.
  for (const e of q.entries) {
    assert.ok(!e.reasons.some(r => String(r).includes('vendor')))
  }
  // The low-score site carries a monitoring badge but is NOT evidence-backed.
  assert.ok(low.monitor)
  assert.equal(low.monitor!.low, true)
  assert.equal(low.evidenceBacked, false)
  assert.deepEqual(low.reasons, ['sequence'])
})

test('이상·실패 우선: only failure/residual entries are evidence-backed (vendor alone is not)', () => {
  const q = buildReviewQueue(mixedRows(), 'CD_TOP', geo())
  const backed = q.entries.filter(e => e.evidenceBacked)
  const seqs = backed.map(e => e.sequence).sort((a, b) => a - b)
  assert.deepEqual(seqs, [SEQ_OUTLIER, SEQ_FAIL]) // residual site + failure site
})

test('no abnormal/watch classification is produced from mock data (no verdict provenance)', () => {
  const q = buildReviewQueue(mixedRows(), 'CD_TOP', geo())
  for (const e of q.entries) {
    assert.ok(!e.reasons.includes('abnormal'))
    assert.ok(!e.reasons.includes('watch'))
    for (const r of e.reasons) {
      assert.ok(['failure', 'residual', 'sequence'].includes(r))
    }
  }
})

test('§0.5 — gallery.ts never references the mock health scalar or placeholder spm_dict', () => {
  const src = readFileSync(fileURLToPath(new URL('./gallery.ts', import.meta.url)), 'utf8')
  // Strip comments so a caveat mentioning the words in prose does not trip this.
  const code = src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .map(l => l.replace(/\/\/.*$/, ''))
    .join('\n')
  assert.ok(!/\bhealth\b/.test(code), 'gallery.ts must not read the mock health scalar')
  assert.ok(!/spm_dict/.test(code), 'gallery.ts must not read the placeholder spm_dict')
})

test('gallery entries carry a derived nm-per-pixel', () => {
  // row() defaults: meas_condition_mag: 250030, meas_condition_pixel: '512,512'.
  // FOV 135000000/250030 = 539.9352nm, / 512 = 1.0545609 nm/px.
  const q = buildReviewQueue([row({})], 'CD_TOP', geo())
  const [entry] = q.entries
  assert.notEqual(entry!.nmPerPx, null)
  assert.ok(Math.abs(entry!.nmPerPx! - 1.0545609) < 1e-6)
})

test('nm-per-pixel divides by the x (horizontal) pixel count, not y', () => {
  // Deliberately non-square resolution: every other fixture in this file uses
  // '512,512', which cannot distinguish dividing by x vs. y. Field of view is
  // a width, so the horizontal pixel count (x) is the correct divisor — pin
  // that here so a future .x -> .y slip fails loudly instead of passing.
  // FOV 135000000/250030 = 539.9352... nm.
  // x path (correct): 539.9352... / 640 = 0.84364...
  // y path (wrong):   539.9352... / 480 = 1.12486...
  const rows = [row({ meas_condition_mag: 250030, meas_condition_pixel: '640,480' })]
  const q = buildReviewQueue(rows, 'CD_TOP', geo())
  const [entry] = q.entries
  assert.notEqual(entry!.nmPerPx, null)
  assert.ok(Math.abs(entry!.nmPerPx! - 0.84364) < 1e-4)
})

test('an empty row derives no scale rather than Infinity', () => {
  // mock writes mag 0 / pixel "0,0" on empty rows.
  const rows = [row({ meas_condition_mag: 0, meas_condition_pixel: '0,0' })]
  const q = buildReviewQueue(rows, 'CD_TOP', geo())
  const [entry] = q.entries
  assert.equal(entry!.nmPerPx, null)
})

// ---------------------------------------------------------------------------
// resolveEvidenceOnly — the PRE-ARMED 이상·실패 우선 default
// ---------------------------------------------------------------------------

test('resolveEvidenceOnly: pre-arms when the queue has evidence to review', () => {
  assert.equal(resolveEvidenceOnly(null, 3), true)
})

test('resolveEvidenceOnly: relaxes to the full queue on a clean wafer', () => {
  // Arming here would land the reviewer on "필터에 해당하는 항목이 없습니다"
  // with every good site hidden behind a filter they never set.
  assert.equal(resolveEvidenceOnly(null, 0), false)
})

test('resolveEvidenceOnly: an explicit choice always beats the default', () => {
  assert.equal(resolveEvidenceOnly(false, 5), false) // turned off despite evidence
  assert.equal(resolveEvidenceOnly(true, 0), true) // kept on despite an empty result
})

test('resolveEvidenceOnly: a still-loading queue reads as no-evidence and re-resolves', () => {
  // Callers resolve against a live count, so the same untouched choice flips to
  // armed as soon as rows arrive — no setup-time snapshot to go stale.
  assert.equal(resolveEvidenceOnly(null, 0), false)
  assert.equal(resolveEvidenceOnly(null, 1), true)
})
