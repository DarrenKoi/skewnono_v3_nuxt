// Pure-logic tests for afmPoints. Run: node --test app/utils/afmPoints.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { blocksOfPoint, imagePoint, pointState, siteDots, tagBlocks } from './afmPoints.ts'

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

const L = { Site: 'Profile_LEFT_UL' }
const R = { Site: 'Profile_RIGHT_UL' }

// Two blocks; every row names its own.
const twoBlocks = [
  row('0001', 'COMPLETED', L), row('0002', 'COMPLETED', L),
  row('0001', 'STOPPED', R), row('0002', 'FAILED', R)
]

test('blocksOfPoint: a row belongs to the block its Site names', () => {
  assert.deepEqual(blocksOfPoint(twoBlocks, summary, '0002').map(b => [b.name, b.row.State]), [
    ['Profile_LEFT_UL', 'COMPLETED'],
    ['Profile_RIGHT_UL', 'FAILED']
  ])
  assert.deepEqual(blocksOfPoint(twoBlocks, [], '9999'), [])
  // A repeat recipe goes round its points again inside ONE block: a point
  // coming back is not a new block, and both readings are kept.
  const repeat = [row('0001', 'COMPLETED', L), row('0002', 'COMPLETED', L), row('0001', 'COMPLETED', L), row('0002', 'FAILED', L)]
  assert.deepEqual(blocksOfPoint(repeat, summary, '0002').map(b => [b.name, b.row.State]), [
    ['Profile_LEFT_UL', 'COMPLETED'],
    ['Profile_LEFT_UL', 'FAILED']
  ])
  assert.equal(tagBlocks(repeat, summary), repeat)
  // A stopped block has no row for the points it never reached.
  const stopped = [row('0001', 'COMPLETED', L), row('0002', 'COMPLETED', L), row('0001', 'STOPPED', R)]
  assert.deepEqual(blocksOfPoint(stopped, summary, '0002').map(b => b.name), ['Profile_LEFT_UL'])
  // Rows that name no block are one block: the Summary's first, else numbered.
  const bare = [row('0001', 'COMPLETED'), row('0001', 'COMPLETED')]
  assert.deepEqual(blocksOfPoint(bare, summary, '0001').map(b => b.name), ['Profile_LEFT_UL', 'Profile_LEFT_UL'])
  assert.deepEqual(blocksOfPoint(bare, [], '0001').map(b => b.name), ['Block 1', 'Block 1'])
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

test('imagePoint: read at the end of the name, longest key wins', () => {
  const stem = '#260424#000100#ETCH_0001_TRIM#T3HQR1B.06#T3HQR1B#085600#'
  assert.equal(imagePoint(`${stem}_0003_Height.webp`, ['0001', '0003']), '0003')
  assert.equal(
    imagePoint(`${stem}_0002_X-001_Y000_0001_Height.webp`, ['0001', '0002_X-001_Y000_0001']),
    '0002_X-001_Y000_0001'
  )
  assert.equal(imagePoint(`${stem}_0003_tip.webp`, ['0003']), '0003')
  // A tip image's kind is two tokens; the one per measurement shows no point.
  assert.equal(imagePoint(`${stem}_0003_C_PR.webp`, ['0001', '0003']), '0003')
  assert.equal(imagePoint(`${stem}_0002_X-001_Y000_0001_C_PR.webp`, ['0001', '0002_X-001_Y000_0001']), '0002_X-001_Y000_0001')
  assert.equal(imagePoint(`${stem}_C_Result.webp`, ['0001', '0003']), '')
  assert.equal(imagePoint(`${stem}_overview.webp`, ['0001']), '')
  // A lookalike token earlier in the name (here in the recipe) claims nothing.
  assert.equal(imagePoint('#x#ETCH_0001_TRIM#_overview.webp', ['0001']), '')
  // A MAPC01 image does not start with the list name; the end still reads.
  assert.equal(imagePoint('#260709#033958#R#01#MON69683#NA#RL1C078.01_0002_Height.webp', ['0001', '0002']), '0002')
})
