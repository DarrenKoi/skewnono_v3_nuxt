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

// `편중` 배지는 두 화면에서 같은 규칙·같은 입력(recipe_count,
// top_recipe_share)을 쓰므로 판정도 하나여야 합니다. 임계값(SHARE_CEIL)만
// 가져오던 것을 2026-08-09부터 **판정 함수 전체**로 바꿨습니다: 이 파일에는
// `at()` 접근자와 편중 판정 절이 통째로 복사돼 있었는데, 같은 술어의 두
// 사본은 경계 조건 하나씩 갈라집니다 — 특히 `<=` 는 지워지기 쉽고, 지워지면
// 배지를 달아야 할 가장 극단적인 장비가 조용히 빠집니다.
//
// 여기서 재수출하지 않습니다 — 재수출은 함수 하나에 Nuxt auto-import 이름을
// 둘 만들고, 그중 하나가 조용히 선택됩니다.
import { isNarrowMix } from './equipmentSignals.ts'

// 또래 집단 판정(`isPeerGroupComparable`)은 여러 fab 을 걸친 조회에서 배지를
// 끄는 규칙이며, 그 논거는 `./equipmentSignals.ts` 에 한 번만 적혀 있습니다.
// 여기서 재수출하지 않습니다 — 재수출은 함수 하나에 auto-import 이름을 둘
// 만들고, Nuxt 가 그중 하나를 조용히 고르게 만듭니다. 이 배지 정책을 쓰는
// 화면은 `RecipeTatEquipmentView.vue` 가 하듯 `~/utils/equipmentSignals` 에서
// 직접 가져다 씁니다.

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

export const FAIL_SIGNAL_META: Record<FailSignal, { label: string, tone: 'warn' | 'info' }> = {
  weak: { label: '취약', tone: 'warn' },
  narrow: { label: '편중', tone: 'warn' },
  healthy: { label: '양호', tone: 'info' }
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

  // 판정은 equipmentSignals 의 것을 그대로 씁니다 — 두 화면의 `편중` 은 같은
  // 배지이고, 포함 부등호가 왜 load-bearing 인지도 거기 한 번만 적혀 있습니다.
  if (isNarrowMix(row, percentiles)) {
    signals.push('narrow')
  }

  return signals
}
