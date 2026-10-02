// Pure-logic tests for afmPoints. Run: node --test app/utils/afmPoints.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { blocksOfPoint, formatDelta, imagePoint, measurementStem, pointState, siteDots, tagBlocks } from './afmPoints.ts'

const row = (point: string, state: string, extra: Record<string, string | number> = {}): AfmDetailRow => ({
  'measurement_point': point,
  'Point No': 1,
  'X (um)': 0,
  'Y (um)': 0,
  'Method_ID': 'BS_TOP01',
  'State': state,
  'Valid': true,
  'Pick Up Count': 1,
  'Sample Count': 1,
  'Approach Count': 1,
  'Mileage': 1,
  ...extra
})

const summary: AfmSummaryRow[] = [
  { Site: 'Profile_LEFT_UL', ITEM: 'MEAN' },
  { Site: 'Profile_LEFT_UL', ITEM: 'MAX' },
  { Site: 'Profile_RIGHT_UL', ITEM: 'MEAN' }
]

// Two blocks, written block by block — the order a data CSV has them in.
const twoBlocks = [
  row('0001', 'COMPLETED'), row('0002', 'COMPLETED'),
  row('0001', 'STOPPED'), row('0002', 'FAILED')
]

test('blocksOfPoint: a block starts where a point comes round again', () => {
  assert.deepEqual(blocksOfPoint(twoBlocks, summary, '0002').map(b => [b.name, b.row.State]), [
    ['Profile_LEFT_UL', 'COMPLETED'],
    ['Profile_RIGHT_UL', 'FAILED']
  ])
  // A block without a Summary (stopped early, or a file with none) is numbered.
  assert.deepEqual(blocksOfPoint(twoBlocks, summary.slice(0, 1), '0001').map(b => b.name), ['Profile_LEFT_UL', 'Block 2'])
  assert.deepEqual(blocksOfPoint(twoBlocks, [], '9999'), [])
  // A point the first block never measured still belongs to the second.
  const uneven = [row('0001', 'COMPLETED'), row('0001', 'COMPLETED'), row('0002', 'COMPLETED')]
  assert.deepEqual(blocksOfPoint(uneven, summary, '0002').map(b => b.name), ['Profile_RIGHT_UL'])
  assert.deepEqual(tagBlocks(uneven, summary).map(r => r.Block), ['Profile_LEFT_UL', 'Profile_RIGHT_UL', 'Profile_RIGHT_UL'])
})

test('tagBlocks: adds Block only where a file has more than one', () => {
  assert.deepEqual(tagBlocks(twoBlocks, summary).map(r => r.Block), [
    'Profile_LEFT_UL', 'Profile_LEFT_UL', 'Profile_RIGHT_UL', 'Profile_RIGHT_UL'
  ])
  const single = twoBlocks.slice(0, 2)
  assert.equal(tagBlocks(single, summary), single)
})

test('pointState: the worst block wins', () => {
  assert.equal(pointState([row('0001', 'COMPLETED'), row('0001', 'STOPPED')]), 'STOPPED')
  assert.equal(pointState([row('0001', 'STOPPED'), row('0001', 'FAILED')]), 'FAILED')
  assert.equal(pointState([row('0001', 'COMPLETED')]), 'COMPLETED')
  assert.equal(pointState([]), null)
})

test('siteDots: one dot per site, centre at 50/50, Y upwards', () => {
  const site = (id: string, x: number, y: number, point: string) =>
    row(point, 'COMPLETED', { 'Site ID': id, 'Site X': x, 'Site Y': y })
  const dots = siteDots([
    site('0001_X000_Y000', 0, 0, '0001_X000_Y000_0001'),
    site('0001_X000_Y000', 0, 0, '0001_X000_Y000_0002'),
    site('0002_X-002_Y001', -2, 1, '0002_X-002_Y001_0001')
  ])
  assert.deepEqual(dots, [
    { siteId: '0001_X000_Y000', point: '0001_X000_Y000_0001', left: 50, top: 50 },
    { siteId: '0002_X-002_Y001', point: '0002_X-002_Y001_0001', left: 10, top: 14 }
  ])
  // A recipe that records no Site ID has no map.
  assert.deepEqual(siteDots([row('0001', 'COMPLETED')]), [])
})

test('imagePoint: read after the measurement stem, longest key wins', () => {
  const stem = '#260424#000100#ETCH_0001_TRIM#T3HQR1B.06#T3HQR1B#085600#'
  assert.equal(imagePoint(`${stem}_0003_Height.webp`, stem, ['0001', '0003']), '0003')
  assert.equal(
    imagePoint(`${stem}_0002_X-001_Y000_0001_Height.webp`, stem, ['0001', '0002_X-001_Y000_0001']),
    '0002_X-001_Y000_0001'
  )
  assert.equal(imagePoint(`${stem}_overview.webp`, stem, ['0001']), '')
  // A name that is not this measurement's is not searched for a lookalike token.
  assert.equal(imagePoint('#other#ETCH_0001_TRIM#_0003_Height.webp', stem, ['0001', '0003']), '')
})

test('measurementStem: drops .csv, and the _Info of a MAPC01 list name', () => {
  assert.equal(measurementStem('#260424#093000#R#01#NA#NA#MON69683.01_Info.csv'), '#260424#093000#R#01#NA#NA#MON69683.01')
  assert.equal(measurementStem('#260424#093000#R#L.01#L#093400#.csv'), '#260424#093000#R#L.01#L#093400#')
})

test('formatDelta: always signed', () => {
  assert.equal(formatDelta(1.234), '+1.23')
  assert.equal(formatDelta(-0.5), '−0.50')
  assert.equal(formatDelta(0), '+0.00')
})
