// 장비별 뷰의 배지 판정. 백엔드는 비율과 분포(분위수)를 계산하고, 여기서는
// "이 값을 경고로 볼 것인가"라는 표시 정책만 결정합니다.
//
// 판정이 분위수 AND 절대 기준인 이유:
//  - 절대 기준만 쓰면, 상수가 실 분포와 어긋나는 순간 전부 정상이거나 전부
//    경고가 됩니다. 실 플릿은 가동률이 대부분 90% 이상으로 촘촘히 몰려
//    있어서(user-confirmed 2026-08-07) 이 위험이 실제로 큽니다.
//  - 분위수만 쓰면, 완벽히 건강한 플릿에서도 항상 하위 10%를 경고합니다.
//    "제일 낮은 장비"와 "문제 있는 장비"는 다릅니다.

export interface EquipmentSignalInput {
  tat_index: number | null
  usage_ratio: number
  recipe_count: number
  top_recipe_share: number
}

// 백엔드 fleet.percentiles: { metric: { p10..p90 } }. 빈 dict은
// "판단 근거 없음"이고, 그 경우 배지를 달지 않습니다.
export type FleetPercentiles = Record<string, Record<string, number>>

export type EquipmentSignal = 'slow' | 'fast' | 'underused' | 'narrow'

// OFFICE-VERIFY — 사무실 실 분포를 보기 전까지는 전부 자리표시자입니다.
// 조정 절차는 recipe_tat/MIGRATION.md 의 "장비별 뷰" 절.
// 값이 확정되면 이 주석을 `office 확인 YYYY-MM-DD` 로 바꿉니다.
export const USAGE_FLOOR = 0.85
export const TAT_CEIL = 1.10
export const TAT_FLOOR = 0.92
export const SHARE_CEIL = 0.50

export const SIGNAL_META: Record<EquipmentSignal, { label: string, tone: 'warn' | 'info' }> = {
  slow: { label: '느림', tone: 'warn' },
  underused: { label: '저사용', tone: 'warn' },
  narrow: { label: '편중', tone: 'warn' },
  fast: { label: '빠름', tone: 'info' }
}

const at = (percentiles: FleetPercentiles, metric: string, key: string): number | null => {
  const value = percentiles?.[metric]?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export const equipmentSignals = (
  row: EquipmentSignalInput,
  percentiles: FleetPercentiles
): EquipmentSignal[] => {
  const signals: EquipmentSignal[] = []

  // 꼬리 비교는 모두 엄격 부등호(<, >)입니다. 백분위수 자체는 "그 경계에
  // 걸친 값"이라 아직 꼬리 "안"이 아니라 꼬리의 경계일 뿐입니다 — 경계값은
  // 절대 기준을 넘더라도 꼬리 판정에서 제외해, 분포 폭이 절대 기준보다
  // 좁은 구간(예: p10이 절대 기준보다 안쪽인 경우)에서 경계 자체가 항상
  // 배지로 새는 것을 막습니다.
  const usageTail = at(percentiles, 'usage_ratio', 'p10')
  if (usageTail !== null && row.usage_ratio < usageTail && row.usage_ratio < USAGE_FLOOR) {
    signals.push('underused')
  }

  // tat_index === null 은 표본 미달입니다. "느리지 않다"가 아니라 "모른다"
  // 이므로 어느 쪽으로도 판정하지 않습니다.
  if (row.tat_index !== null) {
    const slowTail = at(percentiles, 'tat_index', 'p90')
    if (slowTail !== null && row.tat_index > slowTail && row.tat_index > TAT_CEIL) {
      signals.push('slow')
    }
    const fastTail = at(percentiles, 'tat_index', 'p10')
    if (fastTail !== null && row.tat_index < fastTail && row.tat_index < TAT_FLOOR) {
      signals.push('fast')
    }
  }

  const coverageTail = at(percentiles, 'recipe_count', 'p10')
  if (
    coverageTail !== null
    && row.recipe_count < coverageTail
    && row.top_recipe_share >= SHARE_CEIL
  ) {
    signals.push('narrow')
  }

  return signals
}
