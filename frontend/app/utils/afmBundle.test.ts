// Pure-logic tests for afmBundle. Run: node --test app/utils/afmBundle.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailPayload, AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { prepareEntries, trendRows, type TrendSource } from './afmTrend.ts'
import { buildBundle, bundleSheets, bundleSuspects } from './afmBundle.ts'

const COL = 'Left_H (nm)'

const row = (point: string, value: number | null, extra: Record<string, unknown> = {}): AfmDetailRow => ({
  measurement_point: point,
  Site: 'B',
  State: 'COMPLETED',
  Valid: true,
  ...(value === null ? {} : { [COL]: value }),
  ...extra
} as unknown as AfmDetailRow)

const summaryOf = (mean: number): AfmSummaryRow[] => [{ Site: 'B', ITEM: 'MEAN', [COL]: mean }]

const payload = (summary: AfmSummaryRow[], data: AfmDetailRow[], information: Record<string, string> = {}): AfmDetailPayload => ({
  filename: 'f', tool: 'MAP608', pickle_filename: 'f.pkl', information, summary, data, available_points: []
})

// One measurement whose Summary MEAN is `mean`, with the given point rows.
const item = (name: string, recipe: string, mean: number, data: AfmDetailRow[] = [row('1', mean)], information: Record<string, string> = {}) => ({
  source: { filename: name, recipeName: recipe, lotId: `LOT-${name}`, slotNumber: 3, formattedDate: '2026-10-01' } satisfies TrendSource,
  payload: payload(summaryOf(mean), data, information)
})

const group = (items: ReturnType<typeof item>[], pins: string[] = [], showLimits = true) => {
  const trend = trendRows(prepareEntries(items), 'B', COL, 'MEAN', showLimits, new Set(pins))
  return { ...trend, tool: 'MAP608', block: 'B', column: COL, stat: 'MEAN' as const, showLimits, generatedAt: new Date(2026, 9, 9, 14, 5), memo: '' }
}

// Baseline a=10, b=12 → μ 11, MAD 1 → σ 1.4826 → band 6.5522 ~ 15.4478.
const PINNED = () => group([
  item('a', 'R', 10),
  item('b', 'R', 12, [row('1', 12), row('2', null, { State: 'FAILED' })]),
  item('c', 'R', 16),
  item('d', 'R', 11)
], ['a', 'b'])

test('a suspect is a target outside its band, or any measurement with a FAILED / STOPPED point', () => {
  const { rows } = PINNED()
  assert.deepEqual(
    bundleSuspects(rows).map(s => [s.row.entry.key, s.out, s.notCompleted]),
    // b is baseline: never out of band, listed for its FAILED point. a and d are clean.
    [['b', false, 1], ['c', true, 0]]
  )
})

test('a pinned-baseline group names the baseline as the source of the band', () => {
  const bundle = buildBundle(PINNED())
  assert.equal(bundle.generatedAt, '2026-10-09 14:05')
  assert.equal(bundle.bandName, '고정 기준 범위')
  assert.equal(bundle.bandSource, '기준으로 고정한 측정 2건의 평균 ± 3σ')
  assert.equal(bundle.total, 4)
  assert.equal(bundle.suspectCount, 2)
  assert.equal(bundle.recipes.length, 1)
  const [r] = bundle.recipes
  assert.deepEqual([r!.recipe, r!.n, r!.mu, r!.reason], ['R', 2, 11, ''])
  assert.ok(Math.abs(r!.low! - 6.5522) < 1e-9)
  assert.ok(Math.abs(r!.high! - 15.4478) < 1e-9)
})

// R: 10, 12, 16 (unpinned; MAD 2 → σ 2.9652, so nothing is out). Q: 100 alone.
const MIXED = () => group([item('a', 'R', 10), item('b', 'R', 12), item('q', 'Q', 100), item('c', 'R', 16)])

test('a mixed-recipe group keeps one reference per recipe and never pools them', () => {
  const bundle = buildBundle(MIXED())
  assert.equal(bundle.bandName, '그룹 기준 범위')
  assert.equal(bundle.bandSource, '그룹의 측정 4건의 평균 ± 3σ')
  assert.deepEqual(bundle.recipes.map(r => [r.recipe, r.n, r.mu, r.reason]), [
    ['R', 3, 38 / 3, ''],
    ['Q', 1, 100, '값 2건 이상부터']
  ])
  assert.equal(bundle.recipes[1]!.low, null)
})

const TIP_INFO = {
  'Tip ID': 'T1', 'Tip Cassette ID': 'C1', 'Tip Port No': '1', 'Tip Slot No': '4', 'Tip Width': '40.5',
  'Start Time': '2026.10.01 10:00:00', 'End Time': '2026.10.01 10:01:40'
}

test('측정 목록 lists every measurement, flags the suspects, and leaves a missing number empty', () => {
  const { measurements } = buildBundle(group([
    item('a', 'R', 10, [row('1', 10, { 'Mileage': 10, 'Approach Count': 2 })], TIP_INFO),
    item('b', 'R', 12, [row('1', 12), row('2', null, { State: 'FAILED' }), row('3', 12, { Valid: false })]),
    item('c', 'R', 16),
    item('d', 'R', 11, [row('1', 11)], { 'Start Time': '2025-12-31 23:45:00' })
  ], ['a', 'b']))
  const pick = (key: string) => measurements.find(m => m.key === key)!
  const { time: _time, ...a } = pick('a')
  assert.deepEqual(a, {
    key: 'a', lot: 'LOT-a', slot: '3', recipe: 'R', role: '기준',
    value: 10, delta: -1, out: false, failed: 0, stopped: 0, invalid: 0,
    tipId: 'T1', tipCassette: 'C1', tipPort: '1', tipSlot: '4', tipWidth: 40.5, mileage: 10, approach: 2,
    seconds: 100, perPoint: 100, suspect: ''
  })
  const b = pick('b')
  assert.deepEqual([b.role, b.out, b.failed, b.stopped, b.invalid, b.suspect], ['기준', false, 1, 0, 2, 'FAILED·STOPPED 포인트'])
  // Nothing recorded stays null — never 0.
  assert.deepEqual([b.tipId, b.tipWidth, b.mileage, b.approach, b.seconds, b.perPoint], ['', null, null, null, null, null])
  const c = pick('c')
  assert.deepEqual([c.role, c.value, c.delta, c.out, c.suspect], ['대상', 16, 5, true, '고정 기준 범위 밖'])
  assert.equal(pick('d').time, '2025-12-31 23:45')
  assert.equal(pick('d').suspect, '')
})

test('with nothing pinned no measurement has a role', () => {
  assert.deepEqual(buildBundle(MIXED()).measurements.map(m => m.role), ['', '', '', ''])
})

test('이상 측정 포인트 holds each suspect\'s rows against its own recipe\'s per-point group mean', () => {
  const { points } = buildBundle(group([
    item('a', 'R', 10, [row('1', 10), row('2', 20)]),
    item('b', 'R', 12, [row('2', null, { State: 'FAILED' }), row('1', 12)]),
    item('c', 'R', 16, [row('1', 17, { 'Site X': 1, 'Site Y': -2 }), row('2', 24, { Valid: false })]),
    item('q', 'Q', 100, [row('1', 100, { State: 'STOPPED' })])
  ], ['a', 'b']))
  // Point 1 of R: (10 + 12 + 17) / 3 = 13. Point 2: (20 + 24) / 2 = 22. Q stands alone.
  assert.deepEqual(
    points.map(p => [p.key, p.recipe, p.point, p.siteX, p.siteY, p.state, p.valid, p.value, p.reference, p.delta]),
    [
      ['b', 'R', '1', null, null, 'COMPLETED', 'TRUE', 12, 13, -1],
      ['b', 'R', '2', null, null, 'FAILED', 'TRUE', null, 22, null],
      ['c', 'R', '1', 1, -2, 'COMPLETED', 'TRUE', 17, 13, 4],
      ['c', 'R', '2', null, null, 'COMPLETED', 'FALSE', 24, 22, 2],
      ['q', 'Q', '1', null, null, 'STOPPED', 'TRUE', 100, 100, 0]
    ]
  )
})

test('bundleSheets writes 요약 · 측정 목록 · 이상 측정 포인트, with empty cells for missing numbers', () => {
  const sheets = bundleSheets(buildBundle({ ...PINNED(), memo: '  c 재측정 예정 ' }))
  assert.deepEqual(sheets.map(s => s.name), ['요약', '측정 목록', '이상 측정 포인트'])
  const summary = new Map(sheets[0]!.rows.map(r => [r[0], r.slice(1)]))
  assert.deepEqual(summary.get('장비'), ['MAP608'])
  assert.deepEqual(summary.get('기준 범위'), ['고정 기준 범위'])
  assert.deepEqual(summary.get('기준 범위의 근거'), ['기준으로 고정한 측정 2건의 평균 ± 3σ'])
  assert.deepEqual(summary.get('그룹의 측정'), [4])
  assert.deepEqual(summary.get('조사 대상 측정'), [2])
  assert.deepEqual(summary.get('메모'), ['c 재측정 예정'])
  assert.deepEqual(summary.get('R')!.slice(0, 2), [2, 11])
  assert.ok(String(summary.get('유의')![0]).includes('생성 시각'))

  const [head, ...list] = sheets[1]!.rows
  assert.equal(list.length, 4)
  const at = (name: string) => head!.indexOf(name)
  const b = list.find(r => r[at('파일')] === 'b')!
  assert.equal(b[at('조사 대상')], 'FAILED·STOPPED 포인트')
  assert.equal(b[at('역할')], '기준')
  assert.equal(b[at('Left_H (nm) MEAN')], 12)
  assert.equal(b[at('FAILED 행')], 1)
  assert.equal(b[at('Tip Width')], '')
  assert.equal(b[at('소요시간 (초)')], '')
  assert.equal(list.find(r => r[at('파일')] === 'c')![at('고정 기준 범위 밖')], '밖')
  assert.equal(list.find(r => r[at('파일')] === 'a')![at('조사 대상')], '')
  // Suspect rows are the emphasised ones.
  assert.deepEqual(list.map(r => sheets[1]!.emphasize!(r)), [false, true, true, false])

  const [pHead, ...pRows] = sheets[2]!.rows
  // b's FAILED point has no value: the cell and its Δ stay empty.
  const failed = pRows.find(r => r[pHead!.indexOf('State')] === 'FAILED')!
  assert.equal(failed[pHead!.indexOf('Left_H (nm)')], '')
  assert.equal(failed[pHead!.indexOf('Δ (값 − 기준)')], '')
})

test('a sheet with nothing to say is omitted, and so is an empty memo', () => {
  const none = bundleSheets(buildBundle(group([])))
  assert.deepEqual(none.map(s => s.name), ['요약'])
  assert.ok(!none[0]!.rows.some(r => r[0] === '메모'))
  // c is out of band but its file has no data table: no point rows to write.
  const noRows = bundleSheets(buildBundle(group([item('a', 'R', 10), item('b', 'R', 12), item('c', 'R', 16, [])], ['a', 'b'])))
  assert.deepEqual(noRows.map(s => s.name), ['요약', '측정 목록'])
})

test('요약 says a mixed group is not pooled, and that a switched-off band judged nothing', () => {
  const text = (sheets: ReturnType<typeof bundleSheets>) => sheets[0]!.rows.map(r => r.join(' | ')).join('\n')
  assert.match(text(bundleSheets(buildBundle(MIXED()))), /recipe 2종 — μ와 기준 범위는 recipe별로 따로 계산하며 하나로 합치지 않습니다/)
  assert.match(text(bundleSheets(buildBundle(group([item('a', 'R', 10)], [], false)))), /기준 범위 꺼짐/)
  assert.match(text(bundleSheets(buildBundle({ ...MIXED(), notLoaded: 2 }))), /불러오지 못한 측정 \| 2건/)
  assert.doesNotMatch(text(bundleSheets(buildBundle(MIXED()))), /불러오지 못한/)
})

// A file read by people: 10.333333333333334 is noise, and the cells are not
// re-used as inputs anywhere.
test('bundleSheets rounds every number to 4 decimals', () => {
  const sheets = bundleSheets(buildBundle(group([item('a', 'R', 10), item('b', 'R', 10), item('c', 'R', 11)])))
  const summary = new Map(sheets[0]!.rows.map(r => [r[0], r.slice(1)]))
  // μ = 31 / 3 = 10.3333…
  assert.equal(summary.get('R')![1], 10.3333)
  for (const sheet of sheets) {
    for (const cell of sheet.rows.flat()) {
      if (typeof cell === 'number') assert.equal(cell, Number(cell.toFixed(4)), `${sheet.name}: ${cell}`)
    }
  }
})

// Codex review 2 of 2026-10-09: the file's per-point reference must be the one
// the screen is showing. With 02 on 제외, a FAILED row stays in the file as
// evidence but must not sit in the average the others are compared against.
test('the per-point reference follows 02\'s 포함 / 제외 choice, and 요약 says which', () => {
  const g = () => group([
    item('a', 'R', 10),
    item('b', 'R', 100, [row('1', 100, { State: 'FAILED' })]),
    item('c', 'R', 20)
  ])
  const refOfB = (pointsValidOnly: boolean) => {
    const bundle = buildBundle({ ...g(), pointsValidOnly })
    const point = bundle.points.find(p => p.key === 'b')!
    const mode = new Map(bundleSheets(bundle)[0]!.rows.map(r => [r[0], r[1]])).get('포인트 기준')
    return { value: point.value, reference: point.reference, mode: String(mode) }
  }
  // 포함: (10 + 100 + 20) / 3 = 43.3333…; 제외: (10 + 20) / 2 = 15.
  const kept = refOfB(false)
  assert.equal(Number(kept.reference!.toFixed(4)), 43.3333)
  assert.match(kept.mode, /FAILED · Valid FALSE 행 포함/)
  const dropped = refOfB(true)
  assert.equal(dropped.value, 100)
  assert.equal(dropped.reference, 15)
  assert.match(dropped.mode, /FAILED · Valid FALSE 행 제외/)
})

// Codex review 2: 밖 is judged on unrounded numbers; the sheet shows 4 decimals,
// so at the boundary the printed numbers alone cannot explain the flag.
test('요약 says the band was judged before rounding', () => {
  const summary = new Map(bundleSheets(buildBundle(PINNED()))[0]!.rows.map(r => [r[0], r[1]]))
  assert.match(String(summary.get('범위 밖 판정')), /반올림 전/)
})
