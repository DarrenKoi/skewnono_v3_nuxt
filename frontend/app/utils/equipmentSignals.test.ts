import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  equipmentSignals,
  isPeerGroupComparable,
  SIGNAL_META,
  type FleetPercentiles
} from './equipmentSignals.ts'

// 촘촘한 플릿을 흉내낸 분위수. 실 플릿은 가동률이 대부분 90% 이상으로
// 몰려 있다는 현업 확인을 반영합니다. usage_ratio.p10(0.88)은 일부러
// USAGE_FLOOR(0.85)보다 위에 둡니다 — 그래야 "꼬리 안이지만 절대 기준은
// 아직 넘지 않은" 값(예: 0.88 그 자체)을 만들 수 있습니다. p10이 floor보다
// 낮으면 꼬리에 들어가는 모든 값이 자동으로 floor도 넘어, 그 경우를 아예
// 구성할 수 없습니다.
const percentiles: FleetPercentiles = {
  usage_ratio: { p10: 0.88, p25: 0.94, p50: 1.00, p75: 1.06, p90: 1.14 },
  tat_index: { p10: 0.94, p25: 0.97, p50: 1.00, p75: 1.04, p90: 1.13 },
  recipe_count: { p10: 4, p25: 12, p50: 20, p75: 28, p90: 34 }
}

const healthy = { tat_index: 1.0, usage_ratio: 1.0, recipe_count: 20, top_recipe_share: 0.2 }

test('건강한 장비에는 배지를 달지 않는다', () => {
  assert.deepEqual(equipmentSignals(healthy, percentiles), [])
})

test('tat_index가 null이면 느림/빠름 판정을 하지 않는다', () => {
  // 표본 미달은 "느리지 않다"가 아니라 "모른다"입니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: null }, percentiles),
    []
  )
})

test('분위수 꼬리지만 절대 기준을 넘지 않으면 배지가 없다', () => {
  // 완전히 건강한 플릿에서도 누군가는 하위 10%입니다. 그것만으로는
  // 문제가 아닙니다. 0.88은 p10과 정확히 같아 꼬리 안이지만(0.88<=0.88),
  // USAGE_FLOOR(0.85)보다는 위라 절대 기준은 아직 넘지 않습니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, usage_ratio: 0.88 }, percentiles),
    []
  )
})

test('절대 기준을 넘어도 분위수 꼬리가 아니면 배지가 없다', () => {
  // 상수가 실 분포와 어긋났을 때 전부 경고가 되는 것을 막습니다.
  const wide: FleetPercentiles = {
    ...percentiles,
    usage_ratio: { p10: 0.30, p25: 0.50, p50: 1.00, p75: 1.50, p90: 2.00 }
  }
  assert.deepEqual(equipmentSignals({ ...healthy, usage_ratio: 0.80 }, wide), [])
})

test('꼬리이면서 절대 기준을 넘으면 저사용', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, usage_ratio: 0.70 }, percentiles),
    ['underused']
  )
})

test('꼬리이면서 절대 기준을 넘으면 느림', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 1.22 }, percentiles),
    ['slow']
  )
})

test('빠름은 하위 꼬리 + 절대 기준', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 0.90 }, percentiles),
    ['fast']
  )
})

test('편중은 레시피 수 꼬리와 상위 레시피 비중을 모두 요구한다', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, recipe_count: 3, top_recipe_share: 0.2 }, percentiles),
    []
  )
  assert.deepEqual(
    equipmentSignals({ ...healthy, recipe_count: 3, top_recipe_share: 0.7 }, percentiles),
    ['narrow']
  )
})

test('분위수가 비면 아무 배지도 달지 않는다', () => {
  // 빈 범위 = 판단 근거 없음. 근거 없이 경고하지 않습니다.
  const empty: FleetPercentiles = {
    usage_ratio: {}, tat_index: {}, occupancy: {}, recipe_count: {}
  }
  assert.deepEqual(
    equipmentSignals({ tat_index: 9, usage_ratio: 0.01, recipe_count: 1, top_recipe_share: 1 }, empty),
    []
  )
})

test('여러 신호가 동시에 나올 수 있다', () => {
  assert.deepEqual(
    equipmentSignals(
      { tat_index: 1.30, usage_ratio: 0.60, recipe_count: 2, top_recipe_share: 0.9 },
      percentiles
    ),
    ['underused', 'slow', 'narrow']
  )
})

test('모든 신호에 표시용 메타가 있다', () => {
  for (const signal of ['slow', 'fast', 'underused', 'narrow'] as const) {
    assert.ok(SIGNAL_META[signal].label.length > 0)
  }
})

// 아래는 브리프 원본 테스트 이후 뮤테이션 점검으로 추가한 회귀 테스트입니다.
// 최초 버전(엄격 부등호 + usage_ratio.p10=0.82인 픽스처)에서는 브리프
// 원본 11개 테스트만으로 conjunction 8개 절반 중 6개(slow 2개, fast 2개,
// narrow의 꼬리 절반, underused의 절대 기준 절반)가 무증명이었습니다 —
// 그 절반을 equipmentSignals.ts에서 통째로 지워도 원본 11개는 전부
// 통과했습니다(실제로 지워서 확인). 이후 포함 부등호로 되돌리고
// usage_ratio.p10을 0.88로 고치면서(위 test 3) underused의 절대 기준
// 절반은 원본 테스트만으로도 증명되게 됐습니다.
//
// 그래서 아래 여섯 중 다섯은 아직 무증명인 절반을 메우고, 마지막 하나
// (underused)는 위 test 3과 같은 절반을 값이 p10과 정확히 같지 않은
// 경우로 한 번 더 확인하는 **의도적 중복**입니다. 각각 실제로 해당 절반을
// equipmentSignals.ts에서 지워서 이 테스트가 깨지는 것과, 복원하면 다시
// 통과하는 것을 확인했습니다(중복인 마지막 하나 포함).

test('slow: 절대 기준을 넘어도 분위수 꼬리가 아니면 배지가 없다', () => {
  // TAT_CEIL(1.10) < tat_index의 p90(1.13). 그 사이 값(1.12)은 절대 기준은
  // 넘지만 아직 상위 10% 밖입니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 1.12 }, percentiles),
    []
  )
})

test('slow: 분위수 꼬리지만 절대 기준을 넘지 않으면 배지가 없다', () => {
  const narrowSpread: FleetPercentiles = {
    ...percentiles,
    tat_index: { ...percentiles.tat_index, p90: 1.05 }
  }
  // p90을 TAT_CEIL(1.10) 아래로 좁히면, 그 사이 값(1.08)은 상위 10%에는
  // 들어가지만 절대 기준은 아직 넘지 않습니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 1.08 }, narrowSpread),
    []
  )
})

test('fast: 분위수 꼬리지만 절대 기준을 넘지 않으면 배지가 없다', () => {
  // TAT_FLOOR(0.92) < tat_index의 p10(0.94). 그 사이 값(0.93)은 하위 10%에는
  // 들어가지만 절대 기준은 아직 넘지 않습니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 0.93 }, percentiles),
    []
  )
})

test('fast: 절대 기준을 넘어도 분위수 꼬리가 아니면 배지가 없다', () => {
  const wideSpread: FleetPercentiles = {
    ...percentiles,
    tat_index: { ...percentiles.tat_index, p10: 0.88 }
  }
  // p10을 TAT_FLOOR(0.92) 아래로 넓히면, 그 사이 값(0.90)은 절대 기준은
  // 넘지만 아직 하위 10% 밖입니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 0.90 }, wideSpread),
    []
  )
})

test('narrow: 상위 레시피 비중이 높아도 레시피 수가 꼬리가 아니면 배지가 없다', () => {
  // recipe_count(10)는 p10(4)보다 커서 꼬리 밖이지만 top_recipe_share(0.7)는
  // SHARE_CEIL(0.5)을 넘습니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, recipe_count: 10, top_recipe_share: 0.7 }, percentiles),
    []
  )
})

test('underused: 진짜 꼬리 안쪽 값이 절대 기준을 넘지 않으면 배지가 없다', () => {
  const tightSpread: FleetPercentiles = {
    ...percentiles,
    usage_ratio: { ...percentiles.usage_ratio, p10: 0.90 }
  }
  // p10을 USAGE_FLOOR(0.85) 위로 올리면, 그 사이 값(0.87)은 하위 10%에는
  // 들어가지만 절대 기준은 아직 넘지 않습니다. 위 test 3(0.88)도 픽스처
  // 수정 이후로는 같은 절반을 증명하지만, 이 테스트는 p10과 값이 정확히
  // 같지 않은 경우(0.87 < p10 0.90)로 독립적으로 재확인합니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, usage_ratio: 0.87 }, tightSpread),
    []
  )
})

// isPeerGroupComparable — 배지를 아예 달지 말아야 하는 조회 범위
//
// equipmentSignals()가 아니라 호출자가 지키는 조건이라 여기서 따로 봅니다.
// 섞인 fab에서 배지가 실제로 무엇을 가리키는지는 mock에서 측정됐습니다:
// cd-sem 전 fab 14일 조회에서 `빠름` 9대가 전부 meastime 배수가 가장 낮은
// M11이었습니다(창을 6개 옮겨가며 재현, 8~9대).

test('한 fab만 있는 또래 집단은 비교 가능하다', () => {
  assert.equal(
    isPeerGroupComparable([{ fab_name: 'R3' }, { fab_name: 'R3' }]),
    true
  )
})

test('fab이 둘 이상 섞이면 비교 불가다', () => {
  // 사이드바에서 두 fab을 고른 경우 — useFabRoute가 파싱하는 정상 상태입니다.
  assert.equal(
    isPeerGroupComparable([{ fab_name: 'R3' }, { fab_name: 'M16B' }]),
    false
  )
})

test('fab 필터 없는 전 플릿 조회도 비교 불가다', () => {
  // 설계 3.5절의 사무실 확인 절차가 fab 없이 부르는 바로 그 호출입니다.
  // 응답의 fab_names 에코는 빈 목록이지만 데이터는 전 fab을 덮습니다 —
  // 그래서 에코가 아니라 행의 fab을 셉니다.
  const fleetWide = ['M11A', 'M14B', 'M15C', 'M16A', 'R3', 'R4']
    .map(fab_name => ({ fab_name }))
  assert.equal(isPeerGroupComparable(fleetWide), false)
})

test('행이 없으면 비교 불가다', () => {
  // percentiles가 빈 dict일 때 배지를 달지 않는 것과 같은 이유입니다:
  // 근거가 없으면 판정하지 않습니다.
  assert.equal(isPeerGroupComparable([]), false)
})
