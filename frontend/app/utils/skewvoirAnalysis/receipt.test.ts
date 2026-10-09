// Pure-logic tests for the 검토 영수증 (S8): analysis state → receipt → sheets.
// Run: cd frontend && node --test app/utils/skewvoirAnalysis/receipt.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildReviewReceipt, receiptFilename, receiptReady, receiptSheets, type ReceiptInput } from './receipt.ts'
import { DEFAULT_METHOD_CONFIG } from '../anomaly/types.ts'
import type { MsrFileResponse, MsrFileRow } from '~/composables/useMsrFileApi'
import type { MsrFeatureRow } from './features.ts'

const close = (a: unknown, b: number, eps = 1e-6) =>
  assert.ok(typeof a === 'number' && Math.abs(a - b) < eps, `${a} !== ${b}`)

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

// One site per value, each on its own chip so the per-site delta has pairs.
const values = (...vs: number[]) =>
  vs.map((cd_value, i) => row({ sequence: i + 1, chip_number: `${i}, 0`, cd_value }))

// Only `rows` is read from a file; the rest of MsrFileResponse is irrelevant.
const file = (msr: string, rows: MsrFileRow[]) => ({ msr, rows } as MsrFileResponse)
const files = (spec: Record<string, MsrFileRow[]>) =>
  new Map(Object.entries(spec).map(([msr, rows]) => [msr, file(msr, rows)]))

const hist = (lot_id: string, eqp_id: string, timestamp: string, recipe_name = 'RCP_A') =>
  ({ lot_id, eqp_id, timestamp, recipe_name })

const SET = files({
  M1: values(100, 102, 104),
  M2: [...values(120, 122), row({ sequence: 3, chip_number: '2, 0', cd_value: null, mp_number: -1 })]
})

const input = (over: Partial<ReceiptInput> = {}): ReceiptInput => ({
  generatedAt: new Date(2026, 9, 9, 14, 5),
  toolLabel: 'CD-SEM',
  scope: 'set',
  selection: { msr: 'M1', lot: 'LOT1', recipe: 'RCP_A', eq: 'EQ1', capturedAt: '2026-10-01 09:00' },
  parameter: 'CD_TOP',
  parameterLabel: 'CD_TOP',
  unit: 'nm',
  msrList: ['M1', 'M2'],
  rowByMsr: new Map([
    ['M1', hist('LOT1', 'EQ1', '2026-10-01T09:00:00')],
    ['M2', hist('LOT2', 'EQ2', '2026-10-02T10:30:00')]
  ]),
  focusFile: SET.get('M1')!,
  setFiles: SET,
  excluded: [],
  baselineGroups: { base: [], target: ['M1', 'M2'] },
  anomalyCfg: DEFAULT_METHOD_CONFIG,
  radialModel: 'linear',
  tsBaseline: 'raw',
  toolSkew: { rows: [], recipes: 1, contrastRecipes: 0 },
  featureRows: [],
  featureRegistry: [],
  shareUrl: 'http://sknn/skewvoir?msr=M1',
  memo: '',
  ...over
})

test('a set without a baseline is still a receipt: what was selected, under which settings, and each measurement on its own', () => {
  const r = buildReviewReceipt(input())

  assert.equal(r.generatedAt, '2026-10-09 14:05')
  assert.deepEqual(r.selection, {
    toolType: 'CD-SEM', recipe: 'RCP_A', parameter: 'CD_TOP', unit: 'nm', scope: 'set', focusMsr: 'M1'
  })
  assert.deepEqual(r.settings, {
    anomalyMethod: 'range', watch: 10, abnormal: 20, radialModel: 'linear', tsBaseline: 'raw'
  })
  assert.equal(r.baseline, null)

  const [m1, m2] = r.members
  assert.equal(r.members.length, 2)
  assert.deepEqual(
    [m1!.msr, m1!.lot, m1!.eqp, m1!.capturedAt, m1!.recipe, m1!.role, m1!.reason],
    ['M1', 'LOT1', 'EQ1', '2026-10-01 09:00', 'RCP_A', '포함', '']
  )
  assert.equal(m1!.metrics!.n, 3)
  close(m1!.metrics!.level!.mean, 102)
  close(m1!.metrics!.level!.median, 102)
  close(m1!.metrics!.spread!.std, 2)
  close(m1!.metrics!.spread!.threeSigma, 6)
  close(m1!.metrics!.spread!.range, 4)

  assert.deepEqual([m2!.metrics!.n, m2!.metrics!.missing, m2!.metrics!.total], [2, 1, 3])
  close(m2!.metrics!.level!.mean, 121)
  assert.equal(m2!.capturedAt, '2026-10-02 10:30')
})

test('a member that is incompatible or never loaded is listed as 제외 with its reason, and carries no numbers', () => {
  const r = buildReviewReceipt(input({
    msrList: ['M1', 'M2', 'M9'],
    excluded: [{ msr: 'M2', reasons: ['unit-mismatch', 'recipe-mismatch'] }]
  }))
  const [, m2, m9] = r.members
  assert.deepEqual([m2!.role, m2!.reason, m2!.metrics], ['제외', '단위 불일치, 레시피 불일치', null])
  assert.deepEqual([m9!.role, m9!.reason, m9!.metrics], ['제외', '파일을 불러오지 못했습니다', null])
  // No history row either: the id still stands, the identity is blank.
  assert.deepEqual([m9!.lot, m9!.eqp, m9!.capturedAt], ['', '', ''])
})

test('single scope: the focus file alone, identified from the URL selection when history has no row', () => {
  const r = buildReviewReceipt(input({
    scope: 'single', msrList: ['M1'], rowByMsr: new Map(), setFiles: new Map(),
    baselineGroups: { base: [], target: ['M1'] }
  }))
  assert.equal(r.members.length, 1)
  const m = r.members[0]!
  assert.deepEqual([m.lot, m.eqp, m.capturedAt, m.recipe, m.role], ['LOT1', 'EQ1', '2026-10-01 09:00', 'RCP_A', '포함'])
  assert.equal(m.metrics!.n, 3)
})

test('the anomaly thresholds on the receipt are the ones the flagged sites were counted under', () => {
  const one = files({ M1: values(10, 10, 10, 10, 13) })
  const base = { msrList: ['M1'], setFiles: one, focusFile: one.get('M1')! }

  // 13 against its four siblings' mean of 10 is +30%: past 이상 ±20.
  const strict = buildReviewReceipt(input(base))
  assert.equal(strict.members[0]!.outlierCount, 1)
  assert.deepEqual(
    strict.flaggedSites.map(s => [s.msr, s.sequence, s.chip, s.cd, s.kind]),
    [['M1', 5, '4, 0', 13, '이상']]
  )
  close(strict.flaggedSites[0]!.delta, 30)

  // Loosened to 주의 ±40 / 이상 ±50, the same site is no longer flagged.
  const loose = buildReviewReceipt(input({
    ...base,
    anomalyCfg: { ...DEFAULT_METHOD_CONFIG, range: { ...DEFAULT_METHOD_CONFIG.range, watchPct: 40, abnormalPct: 50 } }
  }))
  assert.deepEqual(loose.settings, {
    anomalyMethod: 'range', watch: 40, abnormal: 50, radialModel: 'linear', tsBaseline: 'raw'
  })
  assert.equal(loose.members[0]!.outlierCount, 0)
  assert.deepEqual(loose.flaggedSites, [])
})

test('an unmeasured site is listed as 측정 실패, never as a value', () => {
  const r = buildReviewReceipt(input())
  assert.deepEqual(
    r.flaggedSites.map(s => [s.msr, s.sequence, s.cd, s.delta, s.kind]),
    [['M2', 3, null, null, '측정 실패']]
  )
})

// ── S7: baseline versus target ───────────────────────────────────────────

const SPLIT = files({
  B1: values(10, 12),
  B2: values(14, 16, 18),
  T1: values(15, 17, 19, 21)
})

const splitInput = (over: Partial<ReceiptInput> = {}) => input({
  msrList: ['B1', 'B2', 'T1'],
  rowByMsr: new Map(),
  setFiles: SPLIT,
  focusFile: SPLIT.get('T1')!,
  baselineGroups: { base: ['B1', 'B2'], target: ['T1'] },
  ...over
})

test('with a baseline set, each member carries its role and the receipt carries the S7 numbers and sentence', () => {
  const r = buildReviewReceipt(splitInput())
  assert.deepEqual(r.members.map(m => m.role), ['기준', '기준', '대상'])

  const b = r.baseline!
  // 기준 10,12,14,16,18 → mean 14, range 8. 대상 15,17,19,21 → mean 18, range 6.
  assert.deepEqual([b.base.msrs.length, b.base.pooled.n, b.target.msrs.length, b.target.pooled.n], [2, 5, 1, 4])
  close(b.base.pooled.level!.mean, 14)
  close(b.target.pooled.level!.mean, 18)
  close(b.comparison!.shift, 4)
  close(b.comparison!.shiftInBaseSigma, 0.421637, 1e-5)
  close(b.comparison!.threeSigmaRatio, 0.816497, 1e-5)
  close(b.comparison!.rangeDelta, -2)
  assert.equal(b.sentence, '기준 2건보다 대상 1건의 평균이 +4.00 nm(기준 3σ 의 0.4배) 이동했고 3σ 는 0.8배입니다.')

  // Per chip: 기준 (0,0)=12 (1,0)=14 (2,0)=18 · 대상 15, 17, 19 and a fourth
  // site the baseline never measured.
  assert.deepEqual(b.deltaSites, [[0, 0, 3], [1, 0, 3], [2, 0, 1]])
  assert.equal(b.unpaired, 1)
})

test('a baseline that leaves nothing comparable still reports why, instead of dropping the section', () => {
  const r = buildReviewReceipt(splitInput({ baselineGroups: { base: ['B1', 'B2', 'T1'], target: [] } }))
  assert.equal(r.baseline!.comparison, null)
  assert.equal(r.baseline!.sentence, '평가 불가 — 대상으로 남은 측정이 없습니다. 세트의 일부만 기준으로 지정하세요.')
})

// ── Tables that had no export of their own ───────────────────────────────

const derived = (value: number) => ({ value, unit: 'nm', n: 3, missing: 0, transform: '', reference: '', version: '' })
const feature = (msr: string, level: number, spatial: number | null): MsrFeatureRow => ({
  msr, parameter: 'CD_TOP', level: derived(level), spread: derived(1), coverage: derived(1), failure: derived(0),
  spatial: spatial == null ? null : derived(spatial), fixedFdc: {}, dynamicFdc: {}, quality: {}
})
const def = (id: 'level' | 'spatial', label: string, unit: string): ReceiptInput['featureRegistry'][number] =>
  ({ id, label, unit, grain: 'msr', source: '', aggregation: '', family: id })

test('the across-MSR feature table: one row per compared measurement, a missing feature left empty', () => {
  const r = buildReviewReceipt(input({
    msrList: ['M1', 'M2', 'M9'],
    excluded: [{ msr: 'M9', reasons: ['unit-mismatch'] }],
    featureRegistry: [def('level', 'CD 평균', 'nm'), def('spatial', '반경 기울기', 'nm/mm')],
    featureRows: [feature('M1', 102, 0.5), feature('M2', 121, null), feature('M9', 999, 9)]
  }))
  assert.deepEqual(r.features.axes.map(a => [a.label, a.unit]), [['CD 평균', 'nm'], ['반경 기울기', 'nm/mm']])
  // M9 is 제외, so its numbers do not stand beside the others.
  assert.deepEqual(r.features.rows, [
    { msr: 'M1', values: [102, 0.5] },
    { msr: 'M2', values: [121, null] }
  ])
})

test('the tool skew table is carried as computed', () => {
  const toolSkew = {
    recipes: 1, contrastRecipes: 1,
    rows: [{ eqpId: 'EQ2', n: 2, mean: 121, offset: 9.5, sigma: 0.7, recipes: 1 }]
  }
  assert.deepEqual(buildReviewReceipt(input({ toolSkew })).toolSkew, toolSkew)
})

// ── Sheets ───────────────────────────────────────────────────────────────

const sheetsOf = (over: Partial<ReceiptInput> = {}) => receiptSheets(buildReviewReceipt(input(over)))
const named = (sheets: ReturnType<typeof receiptSheets>, name: string) => sheets.find(s => s.name === name)!.rows

test('sheets without a baseline: 요약 states the selection, settings, time and the URL caveat; 세트 one row per measurement', () => {
  const sheets = sheetsOf({ memo: '  EQ2 가 높다  ' })
  assert.deepEqual(sheets.map(s => s.name), ['요약', '세트', '주의·이상·실패 site'])

  assert.deepEqual(named(sheets, '요약'), [
    ['항목', '값'],
    ['생성 시각', '2026-10-09 14:05'],
    ['장비 타입', 'CD-SEM'],
    ['Recipe', 'RCP_A'],
    ['파라미터', 'CD_TOP'],
    ['단위', 'nm'],
    ['분석 범위', '세트 비교 · 2건'],
    ['Focus MSR', 'M1'],
    ['이상 판정 방식', '범위(%)'],
    ['주의 기준', '±10%'],
    ['이상 기준', '±20%'],
    ['반경 fit 차수', '1차'],
    ['Time-Series 값 기준', '측정값'],
    ['기준 대비', '기준을 지정하지 않았습니다.'],
    ['메모', 'EQ2 가 높다'],
    ['주의', '원본 파일은 61일 뒤 삭제됩니다. URL 은 다시 계산하는 주소이며 수치는 생성 시각 기준입니다.'],
    ['분석 URL', 'http://sknn/skewvoir?msr=M1']
  ])

  assert.deepEqual(named(sheets, '세트'), [
    ['MSR', 'Lot', '장비', '측정 시각', 'Recipe', '역할', '제외 사유', 'site', '미측정', '전체',
      'mean (nm)', 'median (nm)', 'std (nm)', '3σ (nm)', 'MAD σ (nm)', 'range (nm)', '주의·이상 site'],
    ['M1', 'LOT1', 'EQ1', '2026-10-01 09:00', 'RCP_A', '포함', '', 3, 0, 3, 102, 102, 2, 6, 2.9652, 4, 0],
    // Two measured sites: a spread exists, but too few to judge any site.
    ['M2', 'LOT2', 'EQ2', '2026-10-02 10:30', 'RCP_A', '포함', '', 2, 1, 3, 121, 121, 1.4142, 4.2426, 1.4826, 2, '']
  ])

  assert.deepEqual(named(sheets, '주의·이상·실패 site'), [
    ['MSR', 'SEQ', 'CHIP', 'CD (nm)', '편차 (%)', '구분'],
    ['M2', 3, '2, 0', '', '', '측정 실패']
  ])
})

test('sheets for a single clean measurement: 요약 and 세트 only', () => {
  const sheets = sheetsOf({
    scope: 'single', msrList: ['M1'], setFiles: new Map(), baselineGroups: { base: [], target: ['M1'] },
    featureRegistry: [def('level', 'CD 평균', 'nm')], featureRows: [feature('M1', 102, null)]
  })
  assert.deepEqual(sheets.map(s => s.name), ['요약', '세트'])
  assert.deepEqual(named(sheets, '요약')[6], ['분석 범위', '단일 측정'])
  assert.equal(named(sheets, '세트').length, 2)
})

test('the stddev method prints its thresholds in σ, and a parameter without a unit prints no empty parentheses', () => {
  const sheets = sheetsOf({
    unit: '',
    tsBaseline: 'resid',
    radialModel: 'cubic',
    anomalyCfg: { ...DEFAULT_METHOD_CONFIG, method: 'stddev' }
  })
  const summary = named(sheets, '요약')
  assert.deepEqual(summary.slice(8, 13), [
    ['이상 판정 방식', '표준편차(σ)'],
    ['주의 기준', '±2σ'],
    ['이상 기준', '±3σ'],
    ['반경 fit 차수', '3차'],
    ['Time-Series 값 기준', '잔차']
  ])
  assert.deepEqual(named(sheets, '세트')[0]!.slice(10, 13), ['mean', 'median', 'std'])
})

test('sheets with a baseline: the comparison table, its per-site differences, and the note that the baseline is hand-picked', () => {
  const sheets = receiptSheets(buildReviewReceipt(splitInput()))
  assert.deepEqual(sheets.map(s => s.name), ['요약', '세트', '기준 대비', '기준 대비 site', '주의·이상·실패 site'])

  assert.deepEqual(named(sheets, '요약').slice(13, 15), [
    ['기준 대비', '기준 2건보다 대상 1건의 평균이 +4.00 nm(기준 3σ 의 0.4배) 이동했고 3σ 는 0.8배입니다.'],
    ['기준 성격', '이 세트 안에서 손으로 나눈 기준이며 공식 기준선이 아닙니다.']
  ])
  assert.deepEqual(named(sheets, '세트').map(r => r[5]), ['역할', '기준', '기준', '대상'])

  assert.deepEqual(named(sheets, '기준 대비'), [
    ['구분', '측정', 'site', 'mean (nm)', 'median (nm)', '3σ (nm)', 'range (nm)', '최대 측정 비중'],
    ['기준', 2, 5, 14, 14, 9.4868, 8, 0.6],
    ['대상', 1, 4, 18, 18, 7.746, 6, 1],
    ['대상 − 기준', '', '', 4, '', '', -2, ''],
    ['기준 3σ 대비 평균 이동(배)', 0.4216],
    ['3σ 배율(대상/기준)', 0.8165],
    ['한쪽 그룹만 측정한 site', 1]
  ])
  assert.deepEqual(named(sheets, '기준 대비 site'), [
    ['chip X', 'chip Y', '대상 − 기준 (nm)'],
    [0, 0, 3],
    [1, 0, 3],
    [2, 0, 1]
  ])
})

test('a baseline with nothing to compare prints the reason in place of the difference rows', () => {
  const sheets = receiptSheets(buildReviewReceipt(splitInput({ baselineGroups: { base: ['B1', 'B2', 'T1'], target: [] } })))
  assert.deepEqual(named(sheets, '기준 대비').slice(1), [
    ['기준', 3, 9, 15.7778, 16, 10.3682, 11, 0.4444],
    ['대상', 0, 0, '', '', '', '', 0],
    ['평가 불가', '대상으로 남은 측정이 없습니다. 세트의 일부만 기준으로 지정하세요.']
  ])
  assert.equal(sheets.some(s => s.name === '기준 대비 site'), false)
})

test('장비 skew and MSR별 지표 become sheets when they hold data', () => {
  const sheets = sheetsOf({
    toolSkew: {
      recipes: 2, contrastRecipes: 1,
      rows: [
        { eqpId: 'EQ2', n: 2, mean: 121, offset: 9.5, sigma: 0.7, recipes: 1 },
        { eqpId: 'EQ1', n: 1, mean: 102, offset: null, sigma: null, recipes: 0 }
      ]
    },
    featureRegistry: [def('level', 'CD 평균', 'nm'), def('spatial', '반경 기울기', 'nm/mm')],
    featureRows: [feature('M1', 102, 0.5), feature('M2', 121, null)]
  })
  assert.deepEqual(named(sheets, '장비 skew'), [
    // Two recipes in the set: the offset is against each recipe's own baseline.
    ['장비', 'n', '평균 (nm)', 'recipe별 기준 대비 (nm)', 'σ (nm)'],
    ['EQ2', 2, 121, 9.5, 0.7],
    ['EQ1', 1, 102, '', '']
  ])
  assert.deepEqual(named(sheets, 'MSR별 지표'), [
    ['MSR', 'Lot', '장비', 'CD 평균 (nm)', '반경 기울기 (nm/mm)'],
    ['M1', 'LOT1', 'EQ1', 102, 0.5],
    ['M2', 'LOT2', 'EQ2', 121, '']
  ])
})

test('receiptFilename: focus msr and the generation date, safe for a file system', () => {
  assert.equal(receiptFilename(buildReviewReceipt(input())), 'skewvoir-receipt-M1-20261009.xlsx')
  const slashed = buildReviewReceipt(input({ selection: { msr: 'A/B 1', lot: '', recipe: '', eq: '', capturedAt: '' } }))
  assert.equal(receiptFilename(slashed), 'skewvoir-receipt-A_B_1-20261009.xlsx')
})

test('receiptReady: a set receipt waits for the whole set, which the 측정 개요 view never loads', () => {
  const set = {
    scope: 'set' as const, focusLoaded: true, setResolved: 3, setLoaded: 3, setPending: false,
    setError: false, loadedKey: 'A|B|C', wantedKey: 'A|B|C'
  }
  assert.equal(receiptReady(set), true)
  assert.equal(receiptReady({ ...set, setLoaded: 0 }), false)
  assert.equal(receiptReady({ ...set, setPending: true }), false)
  assert.equal(receiptReady({ ...set, focusLoaded: false }), false)
  assert.equal(receiptReady({ ...set, scope: 'single', setResolved: 0, setLoaded: 0, loadedKey: '', wantedKey: '' }), true)
  assert.equal(receiptReady({ ...set, scope: 'single', focusLoaded: false }), false)
})

// Codex review 2026-10-09 #2: a failed batch keeps the PREVIOUS set's files, so
// the count alone matches while the files belong to another set.
test('receiptReady: files left over from the previous set do not make the new one ready', () => {
  const stale = {
    scope: 'set' as const, focusLoaded: true, setResolved: 2, setLoaded: 2, setPending: false,
    setError: true, loadedKey: 'A|B', wantedKey: 'C|D'
  }
  assert.equal(receiptReady(stale), false)
  assert.equal(receiptReady({ ...stale, setError: false }), false)
  assert.equal(receiptReady({ ...stale, loadedKey: 'C|D' }), false)
})

// Codex review 2026-10-09 #3: the screen compares over the set files only, so a
// focus the 30-member cap left out of them must not enter the receipt's baseline.
test('a set receipt does not add the focus file to a baseline the screen could not compute', () => {
  const r = buildReviewReceipt(input({
    selection: { msr: 'F', lot: 'LOTF', recipe: 'RCP_A', eq: 'EQF', capturedAt: '2026-10-03 09:00' },
    msrList: ['F', 'T'],
    focusFile: file('F', values(10, 12)),
    setFiles: files({ T: values(20, 22) }),
    baselineGroups: { base: ['F'], target: ['T'] }
  }))
  assert.equal(r.baseline?.comparison, null)
  assert.equal(r.members.find(m => m.msr === 'F')?.role, '제외')
})

test('a single-scope receipt still reads the focus file, which is all it has', () => {
  const r = buildReviewReceipt(input({
    scope: 'single', msrList: ['M1'], setFiles: new Map(), baselineGroups: { base: [], target: ['M1'] }
  }))
  assert.equal(r.members[0]?.role, '포함')
})

// Codex review 2026-10-09 #1: chip indices only name the same physical site when
// the layouts agree; without that the per-site delta pairs unrelated sites.
test('the per-site delta is left out when the set cannot be compared site by site', () => {
  const split = { base: ['M1'], target: ['M2'] }
  assert.equal(buildReviewReceipt(input({ baselineGroups: split })).baseline?.deltaSites.length, 2)
  const r = buildReviewReceipt(input({ baselineGroups: split, siteDeltaReady: false }))
  assert.deepEqual(r.baseline?.deltaSites, [])
  assert.equal(r.baseline?.siteDeltaReady, false)
  assert.ok(r.baseline?.comparison, 'the level comparison does not need a shared layout')
})
