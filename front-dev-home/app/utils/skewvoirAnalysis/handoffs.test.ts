// front-dev-home/app/utils/skewvoirAnalysis/handoffs.test.ts
// Pure-logic tests for the overview → detail hand-offs.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/handoffs.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildHandoffs,
  hasSpatialCoordinates,
  hasSequenceData,
  hasImageEvidence,
  type HandoffFacts
} from './handoffs.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

const facts = (over: Partial<HandoffFacts> = {}): HandoffFacts => ({
  activeParam: 'CD_TOP',
  availableParams: ['CD_TOP'],
  focusedSite: null,
  ...over
})

test('hasSpatialCoordinates: true when a measured row parses a chip_number', () => {
  const rows = [row({ chip_number: '3, 4' })]
  assert.equal(hasSpatialCoordinates(rows, 'CD_TOP'), true)
})

test('hasSpatialCoordinates: false for a failed row (no cd_value)', () => {
  const rows = [row({ mp_number: -1, cd_value: null })]
  assert.equal(hasSpatialCoordinates(rows, 'CD_TOP'), false)
})

test('hasSpatialCoordinates: false when the parameter has no rows', () => {
  const rows = [row({ parameter: 'GATE_CD' })]
  assert.equal(hasSpatialCoordinates(rows, 'CD_TOP'), false)
})

test('hasSequenceData: true for any measured row on the parameter', () => {
  assert.equal(hasSequenceData([row({})], 'CD_TOP'), true)
  assert.equal(hasSequenceData([row({ mp_number: -1, cd_value: null })], 'CD_TOP'), false)
})

test('hasImageEvidence: true only when a row carries an image filename', () => {
  assert.equal(hasImageEvidence([row({ mp_image_name_01: '' })], 'CD_TOP'), false)
  assert.equal(hasImageEvidence([row({ mp_image_name_01: 'img_001.png' })], 'CD_TOP'), true)
})

test('buildHandoffs: all four targets ready, carrying site/param/x-y in one patch', () => {
  const targets = buildHandoffs(
    facts({ availableParams: ['CD_TOP', 'CD_BOT'], focusedSite: '3, 4' }),
    { coordinates: true, sequence: true, images: true }
  )
  assert.equal(targets.length, 4)

  const position = targets.find(t => t.key === 'position')!
  assert.equal(position.ready, true)
  assert.equal(position.reason, null)
  assert.deepEqual(position.query, { view: 'position-stack', scope: 'single', site: '3, 4', mp: 'CD_TOP' })

  const sequence = targets.find(t => t.key === 'sequence')!
  assert.equal(sequence.ready, true)
  assert.deepEqual(sequence.query, { view: 'time-series', scope: 'single' })

  const paired = targets.find(t => t.key === 'paired')!
  assert.equal(paired.ready, true)
  assert.deepEqual(paired.query, { view: 'correlation', scope: 'single', x: 'CD_TOP', y: 'CD_BOT' })

  const gallery = targets.find(t => t.key === 'gallery')!
  assert.equal(gallery.ready, true)
  assert.deepEqual(gallery.query, { view: 'gallery', scope: 'single', site: '3, 4', mp: 'CD_TOP', filter: 'priority' })
})

test('buildHandoffs: unconfirmed facts produce a reason, never a ready target', () => {
  const targets = buildHandoffs(
    facts({ availableParams: ['CD_TOP'], focusedSite: null }),
    { coordinates: false, sequence: false, images: false }
  )
  for (const t of targets) {
    if (t.key === 'paired') continue // gated on availableParams.length, asserted separately
    assert.equal(t.ready, false)
    assert.ok(t.reason && t.reason.length > 0, `${t.key} should carry a reason`)
  }
  const paired = targets.find(t => t.key === 'paired')!
  assert.equal(paired.ready, false, 'a single available parameter cannot pair')
  assert.ok(paired.reason)
})

test('buildHandoffs: paired defaults to the same parameter for x and y when only one is available', () => {
  const targets = buildHandoffs(
    facts({ availableParams: ['CD_TOP'] }),
    { coordinates: false, sequence: false, images: false }
  )
  const paired = targets.find(t => t.key === 'paired')!
  assert.deepEqual(paired.query, { view: 'correlation', scope: 'single', x: 'CD_TOP', y: 'CD_TOP' })
})

test('buildHandoffs: no focused site clears the site query key rather than leaving it stale', () => {
  const targets = buildHandoffs(
    facts({ focusedSite: null }),
    { coordinates: true, sequence: true, images: true }
  )
  const position = targets.find(t => t.key === 'position')!
  assert.equal(position.query.site, null)
})
