// Runs under raw `node --test` — see cdu.test.ts.
import test from 'node:test'
import assert from 'node:assert/strict'
import { measurementVerdict, type VerdictInput } from './verdict.ts'
import { cduMetrics, sectorClustering } from './cdu.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

// A minimal MsrFileRow — only the fields cduMetrics reads carry meaning here.
const row = (sequence: number, cd: number | null): MsrFileRow => ({
  sequence,
  mp_number: cd === null ? -1 : sequence,
  chip_number: `${sequence}, 0`,
  parameter: 'CD_TOP',
  cd_value: cd
} as MsrFileRow)

const input = (over: Partial<VerdictInput> = {}): VerdictInput => ({
  paramLabel: 'CD_TOP',
  unit: 'nm',
  metrics: cduMetrics([row(1, 29.4), row(2, 29.6), row(3, 29.8)], 'CD_TOP', 'nm'),
  outlierCount: 0,
  failedCauses: 0,
  missing: 0,
  measured: 3,
  total: 3,
  clustering: sectorClustering([]),
  ...over
})

test('a clean measurement reads 정상', () => {
  const v = measurementVerdict(input())
  assert.equal(v.tone, 'ok')
  assert.equal(v.badge, '정상')
})

test('one outlier is enough for 확인 필요', () => {
  assert.equal(measurementVerdict(input({ outlierCount: 1 })).tone, 'attention')
})

test('a failed cause with no outlier is still 확인 필요', () => {
  // 결측/align/이미지 실패 are reasons to look even when every measured site
  // sits inside the pack.
  const v = measurementVerdict(input({ failedCauses: 1, missing: 2, measured: 1, total: 3 }))
  assert.equal(v.tone, 'attention')
  assert.equal(v.badge, '확인 필요')
})

// ── σ 기여도 ──────────────────────────────────────────────────────────────
// 1 − σ(이상치 제외)/σ. A self-comparison inside one wafer, so it needs no spec
// and no history — which is exactly why this is the number the sentence quotes.

const spiked = () => cduMetrics(
  // Nine identical sites and one far away: the MAD of that set is 0 by
  // construction (the median deviation is 0), so σ(이상치 제외) is 0 and the
  // spike carries the WHOLE of σ. 100% is a worked answer, not the formula
  // run twice.
  [...Array.from({ length: 9 }, (_, i) => row(i + 1, 10)), row(10, 20)],
  'CD_TOP',
  'nm'
)

test('one spike among identical sites carries all of σ', () => {
  assert.equal(measurementVerdict(input({ metrics: spiked(), outlierCount: 1 })).outlierShare, 1)
})

test('an evenly spread wafer attributes almost none of σ to outliers', () => {
  const v = measurementVerdict(input())
  assert.ok(v.outlierShare !== null && v.outlierShare < 0.2, `even spread, got ${v.outlierShare}`)
})

test('a spread that is not defined has no share to report', () => {
  const single = cduMetrics([row(1, 29.4)], 'CD_TOP', 'nm')
  assert.equal(measurementVerdict(input({ metrics: single })).outlierShare, null)
})

test('identical sites have no σ to divide, so the share is not fabricated', () => {
  const flat = cduMetrics([row(1, 29.4), row(2, 29.4), row(3, 29.4)], 'CD_TOP', 'nm')
  assert.equal(measurementVerdict(input({ metrics: flat })).outlierShare, null)
})

// ── 판정 문장 ─────────────────────────────────────────────────────────────

const textOf = (v: { sentence: { text: string }[] }) => v.sentence.map(s => s.text).join('')

test('the headline names the level, the σ share, the outliers and where they sit', () => {
  const v = measurementVerdict(input({
    metrics: spiked(),
    outlierCount: 1,
    clustering: sectorClustering([{ sector: 'E' }, { sector: 'E' }, { sector: 'N' }])
  }))
  assert.equal(
    textOf(v),
    'CD_TOP 11.00 nm · σ 의 100% 가 이상 1 site 에서 나오고, 그 site 들은 우측(E)에 몰려 있습니다.'
  )
})

test('the outlier phrase is the only part the template paints red', () => {
  const v = measurementVerdict(input({ metrics: spiked(), outlierCount: 1 }))
  assert.deepEqual(v.sentence.filter(s => s.kind === 'bad').map(s => s.text), ['이상 1 site'])
})

test('a clean wafer says so without borrowing a spec it does not have', () => {
  assert.equal(
    textOf(measurementVerdict(input())),
    'CD_TOP 29.60 nm · 3 site 모두 측정되었고 이상 site 는 없습니다.'
  )
})

test('outliers that do NOT concentrate σ are not credited with concentrating it', () => {
  // σ and σ(이상치 제외) agree here, so the "n% 가 이상 site 에서" clause would
  // be a claim the numbers do not support.
  const v = measurementVerdict(input({ outlierCount: 2 }))
  assert.ok(!textOf(v).includes('σ 의'), textOf(v))
  assert.equal(textOf(v), 'CD_TOP 29.60 nm · 이상 2 site 가 있고 σ 는 웨이퍼 전체에 퍼져 있습니다.')
})

test('a scattered verdict never reads as a hot spot', () => {
  const v = measurementVerdict(input({
    metrics: spiked(),
    outlierCount: 1,
    clustering: sectorClustering([{ sector: 'E' }, { sector: 'N' }, { sector: 'W' }, { sector: 'S' }])
  }))
  assert.ok(!textOf(v).includes('몰려'), textOf(v))
})

test('missing sites are named when nothing was flagged as an outlier', () => {
  assert.equal(
    textOf(measurementVerdict(input({ missing: 3, measured: 3, total: 6, failedCauses: 1 }))),
    'CD_TOP 29.60 nm · 이상 site 는 없고, 3 site 가 측정되지 않았습니다.'
  )
})

test('an MSR-level cause with every site measured still gets said out loud', () => {
  assert.equal(
    textOf(measurementVerdict(input({ failedCauses: 1 }))),
    'CD_TOP 29.60 nm · 이상 site 는 없지만 실패 원인 1 건이 잡혀 있습니다.'
  )
})

test('a measurement with no measured site refuses to state a level', () => {
  const none = cduMetrics([row(1, null), row(2, null)], 'CD_TOP', 'nm')
  const v = measurementVerdict(input({ metrics: none, missing: 2, measured: 0, total: 2, failedCauses: 1 }))
  assert.equal(textOf(v), 'CD_TOP — 측정된 site 가 없습니다.')
  assert.equal(v.outlierShare, null)
})

test('a flat-topped wafer reports no outlier contribution, never a negative one', () => {
  // Near-uniform values: MAD × 1.4826 OVERSHOOTS the sample σ (0.3706·range vs
  // 0.2887·range), so the raw ratio goes past 1 and the share goes negative.
  // The extremes are not inflating σ here — that is a share of zero, and a
  // caption reading "이상치 제외 시 -22% 축소" is not a smaller number, it is a
  // sentence that means nothing.
  const flatTop = cduMetrics(
    [10, 11, 12, 13, 14, 15, 16, 17, 18, 19].map((v, i) => row(i + 1, v)),
    'CD_TOP',
    'nm'
  )
  const v = measurementVerdict(input({ metrics: flatTop }))
  assert.equal(v.outlierShare, 0)
})
