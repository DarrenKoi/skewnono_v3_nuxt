// 실패 장비별 뷰의 배지 판정. 백엔드는 지수와 그 신뢰구간을 계산하고,
// 여기서는 "이 값을 경고로 볼 것인가"라는 표시 정책만 결정합니다.
//
// 판정이 **구간 AND 상수**인 이유 — 두 조건이 서로 다른 질문에 답합니다.
//
//  - 구간 조건(`low > 1` / `high < 1`)은 "잡음과 구별되는가"입니다. 이 지수는
//    드문 사건의 건수비라 잡음이 1/√λ 입니다. 기대 실패가 5건인 장비는 완전히
//    건강해도 지수가 0.55~1.45 사이에서 흔들리므로, 점추정값만 보면 배지가
//    동전 던지기가 됩니다(설계 3.2절의 실측표).
//  - 상수 조건은 "볼 가치가 있을 만큼 큰가"입니다. 바쁜 장비는 구간이 아주
//    좁아져서 1.03 도 통계적으로는 유의해지는데, 3 % 차이로 사람을 부르지는
//    않습니다.
//
// 앞의 것은 통계가 답하고 뒤의 것은 사람이 정합니다. 그래서 상수만
// OFFICE-VERIFY 입니다.

// 또래 집단 판정은 recipe_tat 과 논거가 동일하므로 그 파일에서 재사용합니다.
// 복제하면 한쪽만 고쳐지는 날이 옵니다 — 그 함수 위의 긴 주석이 왜 여러 fab
// 에서 배지를 끄는지 설명합니다.
export { isPeerGroupComparable } from './equipmentSignals.ts'

export interface FailEquipmentSignalInput {
  index: number | null
  index_low: number | null
  index_high: number | null
  recipe_count: number
  top_recipe_share: number
}

// 백엔드 fleet.percentiles: { metric: { p10..p90 } }. 빈 dict 은
// "판단 근거 없음"이고, 그 경우 배지를 달지 않습니다.
export type FailPercentiles = Record<string, Record<string, number>>

export type FailSignal = 'weak' | 'healthy' | 'narrow'

// OFFICE-VERIFY — 사무실 실 분포를 보기 전까지는 자리표시자입니다. 다만
// recipe_tat 의 상수들과 성격이 다릅니다: 이 둘은 잡음 방어선이 아니라
// **업무 판단**입니다("얼마나 나빠야 사람이 움직이는가"). 잡음 방어는
// 구간이 이미 하고 있으므로, 이 값을 잘못 잡아도 배지가 잡음에 켜지지는
// 않습니다 — 너무 적게 켜지거나 너무 많이 켜질 뿐입니다.
// 조정 절차는 설계 문서 9절.
export const FAIL_INDEX_CEIL = 1.25
export const FAIL_INDEX_FLOOR = 0.75

// equipmentSignals.ts 의 같은 이름과 같은 의미이므로 같은 값입니다.
export const SHARE_CEIL = 0.50

export const FAIL_SIGNAL_META: Record<FailSignal, { label: string, tone: 'warn' | 'info' }> = {
  weak: { label: '취약', tone: 'warn' },
  narrow: { label: '편중', tone: 'warn' },
  healthy: { label: '양호', tone: 'info' }
}

const at = (
  percentiles: FailPercentiles,
  metric: string,
  key: string
): number | null => {
  const value = percentiles?.[metric]?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** 구간이 1.0 의 한쪽에 완전히 있는가. false 면 표에서 지수를 죽여 그립니다. */
export const isIndexConclusive = (row: FailEquipmentSignalInput): boolean => {
  if (row.index_low === null || row.index_high === null) return false
  return row.index_low > 1 || row.index_high < 1
}

export const failEquipmentSignals = (
  row: FailEquipmentSignalInput,
  percentiles: FailPercentiles
): FailSignal[] => {
  const signals: FailSignal[] = []

  // index === null 은 표본 미달입니다. "실패하지 않았다"가 아니라 "모른다"
  // 이므로 어느 쪽으로도 판정하지 않습니다.
  if (row.index !== null && row.index_low !== null && row.index_high !== null) {
    if (row.index_low > 1 && row.index > FAIL_INDEX_CEIL) {
      signals.push('weak')
    }
    if (row.index_high < 1 && row.index < FAIL_INDEX_FLOOR) {
      signals.push('healthy')
    }
  }

  // 꼬리 비교는 포함 부등호입니다. percentile_summary 는 nearest-rank 라 p10
  // 이 항상 실제 표본 값 하나와 같고, 작은 플릿에서는 그 표본이 곧 최솟값
  // 자신입니다. 엄격 부등호를 쓰면 경계를 정의하는 장비 자신이 자기 꼬리에
  // 들지 못해, 정확히 배지를 달아야 할 가장 극단적인 장비가 구조적으로
  // 제외됩니다. recipe_count 는 정수라 플릿이 커져도 동률이 사라지지
  // 않으므로 이는 상시적인 문제입니다.
  const coverageTail = at(percentiles, 'recipe_count', 'p10')
  if (
    coverageTail !== null
    && row.recipe_count <= coverageTail
    && row.top_recipe_share >= SHARE_CEIL
  ) {
    signals.push('narrow')
  }

  return signals
}
