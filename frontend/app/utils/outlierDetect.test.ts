// Pure-logic tests for outlierDetect. Run: node --test app/utils/outlierDetect.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectDeviceOutliers,
  isOutlierExemptParam,
  DEFAULT_OUTLIER_MULTIPLIER
} from './outlierDetect.ts'
import type { RecipeInput } from './ruleEngine.ts'

const recipe = (recipe_id: string, points: number[]): RecipeInput => ({
  lot_cd: 'R000',
  recipe_id,
  fac_id: 'R3',
  ctn_desc: '',
  prod_catg_cd: 'DRAM',
  recipe_class: 'Main',
  family: 'Core',
  phase: 'EV',
  memory_class_auto: 'DRAM',
  parameters: points.map((point_count, i) => ({ name: `P_${i}`, point_count }))
})

/** 이름이 중요한 테스트용 — points 를 [name, count] 로 줍니다. */
const namedRecipe = (recipe_id: string, params: [string, number][]): RecipeInput => ({
  ...recipe(recipe_id, []),
  parameters: params.map(([name, point_count]) => ({ name, point_count }))
})

test('empty device → median 0, no outliers', () => {
  const r = detectDeviceOutliers([])
  assert.equal(r.median, 0)
  assert.equal(r.outlier_count, 0)
  assert.deepEqual(r.outliers, [])
})

test('uniform point counts → no outliers', () => {
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10]), recipe('B', [10, 10])])
  assert.equal(r.median, 10)
  assert.equal(r.outlier_count, 0)
})

test('a single high value is flagged with its recipe_id and name', () => {
  // medians of [10,10,10,10,50] = 10; threshold = 2*10 = 20; 50 > 20.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [50])])
  assert.equal(r.median, 10)
  assert.equal(r.threshold, 20)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.recipe_id, 'B')
  assert.equal(r.outliers[0]?.point_count, 50)
  assert.equal(r.outliers[0]?.name, 'P_0')
})

test('value exactly at threshold is NOT an outlier (strictly greater)', () => {
  // median 10, threshold 20, a 20 must not flag.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [20])])
  assert.equal(r.outlier_count, 0)
})

test('multiplier is configurable', () => {
  // median 10, multiplier 4 → threshold 40; 30 does not flag, 50 does.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [30, 50])], 4)
  assert.equal(r.threshold, 40)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.point_count, 50)
})

test('default multiplier is 2', () => {
  assert.equal(DEFAULT_OUTLIER_MULTIPLIER, 2)
})

// --- 특수 측정 job 제외 (user-confirmed 2026-08-05) ---

test('an exempt job is never flagged, however many points it measures', () => {
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B_WCDU', [800])])
  assert.equal(r.outlier_count, 0, 'a full-map job measures a lot by design')
  assert.deepEqual(r.outliers, [])
})

test('every exempt job kind is excluded — the CDU family by pattern', () => {
  const r = detectDeviceOutliers([
    recipe('A', [10, 10, 10, 10]),
    recipe('B_WCDU', [800]),
    recipe('C_FCDU', [800]),
    recipe('D_BCDU', [800]),
    // 아직 이름을 본 적 없는 CDU 종류도 같은 규칙을 따라야 합니다 — 목록으로
    // 두었을 때 _BCDU 가 새어 나간 것이 이 테스트가 있는 이유입니다.
    recipe('E_XCDU', [800]),
    recipe('F_FULL', [800]),
    recipe('G_HALF', [800]),
    recipe('H_MTX', [800])
  ])
  assert.equal(r.median, 10, 'the baseline is the normal recipes only')
  assert.equal(r.outlier_count, 0)
})

// 이것이 이 규칙의 진짜 이유입니다. exempt job 이 기준선에 남아 있으면 중앙값이
// 끌려 올라가 **정상 recipe 의 진짜 과다 측정이 문턱 아래로 숨습니다**.
test('excluding exempt jobs keeps a real outlier in a normal recipe visible', () => {
  const rows = [
    recipe('A', [10, 10, 10, 10, 10, 10]),
    recipe('B', [40]), // 진짜 과다 측정 — 정상 recipe 인데 4배
    recipe('X_FULL', [400, 400, 400, 400, 400, 400, 400])
  ]
  const r = detectDeviceOutliers(rows)

  // exempt 를 세면 중앙값이 400 쪽으로 끌려가 threshold 가 40 을 넘고 B 가 숨습니다.
  assert.equal(r.median, 10)
  assert.equal(r.threshold, 20)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.recipe_id, 'B')
})

test('a device measuring ONLY exempt jobs reports an empty baseline, not a huge one', () => {
  const r = detectDeviceOutliers([recipe('A_WCDU', [500, 500]), recipe('B_FCDU', [500])])
  assert.equal(r.median, 0)
  assert.equal(r.outlier_count, 0)
})

// --- 측정이 아닌 파라미터 제외 (user-confirmed 2026-08-05) ---

// 실물 표기는 "Dummy" / "Align" 입니다 — 다른 파라미터가 대체로 전부 대문자인
// 것과 달리 이 둘만 그렇지 않습니다 (user-confirmed 2026-08-05). 그 표기를 맨
// 앞에 두는 것은, 나머지가 전부 통과해도 **이것 하나가 실패하면 실물이 새는**
// 항목이기 때문입니다.
test('isOutlierExemptParam matches the real mixed-case spelling', () => {
  assert.equal(isOutlierExemptParam('Dummy'), true)
  assert.equal(isOutlierExemptParam('Align'), true)
})

test('isOutlierExemptParam matches DUMMY and ALIGN as an affix, case-insensitive', () => {
  for (const name of [
    'Dummy', 'DUMMY', 'dummy', 'Dummy_1', 'DUMMY_1', 'CD_Dummy', 'CD_DUMMY',
    'Align', 'ALIGN', 'align', 'Align_2', 'ALIGN_2', 'X_Align', 'X_ALIGN'
  ]) {
    assert.equal(isOutlierExemptParam(name), true, name)
  }
  // 한복판에 우연히 든 낱말은 잡지 않습니다 — 룰 데이터의 affix 매칭과 같은 의미.
  for (const name of ['WAFER_CD', 'EDGE_L', 'A_DUMMY_B', 'A_ALIGN_B', '']) {
    assert.equal(isOutlierExemptParam(name), false, name)
  }
})

test('DUMMY and ALIGN never appear as outliers, however many points they carry', () => {
  const r = detectDeviceOutliers([
    namedRecipe('A', [['WAFER_CD', 6], ['EDGE_L', 6], ['LEVEL_1', 6], ['OVL_X', 6]]),
    namedRecipe('B', [['Dummy', 400], ['Align', 400]])
  ])
  assert.equal(r.outlier_count, 0)
  assert.deepEqual(r.outliers, [])
})

// 이 둘을 빼는 진짜 이유는 기준선입니다. 기준선은 **양쪽으로** 흔들릴 수 있고,
// 아래 두 테스트가 각각 한 방향입니다.
//
// 실물에서 일어나는 것은 두 번째(끌어내림)입니다 — Dummy·Align 의 실물 point
// 수는 1~3 입니다 (user-confirmed 2026-08-10). 그래서 이 규칙이 막는 것은
// "가려짐" 이 아니라 **오검출** 입니다. 첫 번째 테스트가 쓰는 40 은 규칙이
// 값의 크기에 기대지 않는다는 것을 보이기 위한 합성값입니다.
test('excluding them keeps the baseline on real measurements', () => {
  const r = detectDeviceOutliers([
    namedRecipe('A', [['WAFER_CD', 5], ['EDGE_L', 5], ['LEVEL_1', 5]]),
    namedRecipe('B', [['Align', 40], ['Align_2', 40], ['Dummy', 40], ['OVL_X', 30]])
  ])
  // Align·Dummy 를 세면 중앙값이 40 쪽으로 올라가 OVL_X 30 이 숨습니다.
  assert.equal(r.median, 5)
  assert.equal(r.threshold, 10)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.name, 'OVL_X')
})

// 실물 방향. Dummy·Align 이 1~3 이라 남겨 두면 중앙값이 **내려가고** 문턱도
// 함께 내려가, 정상 범위의 파라미터가 outlier 로 잡힙니다.
//
// 반대 상황을 주석으로 적어 두는 대신 **같은 값을 이름만 바꿔** 한 번 더
// 돌립니다. 주석은 규칙을 지웠을 때 깨지지 않지만, 이 대조는 깨집니다.
test('excluding them keeps small helper params from lowering the baseline', () => {
  const points: Array<[string, number]> = [['?1', 1], ['?2', 3], ['?3', 3], ['?4', 3]]
  const measured: Array<[string, number]>
    = [['WAFER_CD', 6], ['EDGE_L', 6], ['LEVEL_1', 6], ['OVL_X', 11]]

  const excluded = detectDeviceOutliers([
    namedRecipe('A', measured),
    namedRecipe('B', points.map(([, v], i) => [i === 0 ? 'Dummy' : `Align_${i}`, v]))
  ])
  assert.equal(excluded.median, 6)
  assert.equal(excluded.threshold, 12)
  assert.equal(excluded.outlier_count, 0, 'OVL_X 11 은 문턱 12 아래라 정상입니다')

  // 같은 숫자, 제외되지 않는 이름. 규칙이 없을 때 무슨 일이 나는지가 이것입니다.
  const counted = detectDeviceOutliers([
    namedRecipe('A', measured),
    namedRecipe('B', points.map(([, v], i) => [`HELPER_${i}`, v]))
  ])
  assert.equal(counted.median, 4.5)
  assert.equal(counted.threshold, 9)
  assert.equal(counted.outlier_count, 1)
  assert.equal(counted.outliers[0]?.name, 'OVL_X', '없던 outlier 가 생깁니다')
})

test('a recipe of nothing but non-measurement params contributes no baseline', () => {
  const r = detectDeviceOutliers([namedRecipe('A', [['Dummy', 9], ['Align', 9]])])
  assert.equal(r.median, 0)
  assert.equal(r.outlier_count, 0)
})

// 위치 규칙 (user-confirmed 2026-08-10). 맨 앞의 것만 준비용이고, 뒤에 있는
// 것은 이름이 같아 보여도 진짜 측정 파라미터입니다.
test('a trailing ALIGN-suffixed parameter is measured, not stripped', () => {
  const r = detectDeviceOutliers([
    namedRecipe('A', [['Align', 3], ['WAFER_CD', 6], ['EDGE_L', 6], ['CD_ALIGN', 30]])
  ])
  // 맨 앞 Align 만 빠지고 CD_ALIGN 은 남습니다 — 중앙값 6, 문턱 12, 30 은 outlier.
  assert.equal(r.median, 6)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.name, 'CD_ALIGN')
})

test('leading helpers are stripped as a run, not one at a time', () => {
  const r = detectDeviceOutliers([
    namedRecipe('A', [['Dummy', 1], ['Align', 3], ['WAFER_CD', 6], ['EDGE_L', 6]])
  ])
  // 둘 다 빠져야 중앙값이 6 입니다. 하나만 빼면 [3, 6, 6] 이라 중앙값이 6 으로
  // 같아 보이지만, 파라미터가 하나 더 남아 있다는 사실이 다릅니다.
  assert.equal(r.median, 6)
  assert.deepEqual(r.outliers, [])
})
