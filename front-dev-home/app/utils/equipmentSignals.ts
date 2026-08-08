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

// OFFICE-VERIFY — 사무실 실 분포를 보기 전까지는 자리표시자입니다. 이 셋은
// `/equipments` 한 번 호출의 `fleet.percentiles` 만으로 맞출 수 있습니다.
// 절차는 recipe_tat/MIGRATION.md 의 "장비별 뷰" 절.
// 값이 확정되면 이 주석을 `office 확인 YYYY-MM-DD` 로 바꿉니다.
export const USAGE_FLOOR = 0.85
export const TAT_FLOOR = 0.92
export const SHARE_CEIL = 0.50

// OFFICE-VERIFY — TAT_CEIL 만 주석이 따로인 이유: 이 상수는
// `fleet.percentiles` 하나로 끝나지 않습니다. mock 은 칸 하나가 장비 5대뿐
// 이라 느린 장비가 자기 레시피의 base(r) 을 스스로 끌어올려 자기 지수를
// 감쇠시키고, 장비가 훨씬 많은 사무실 칸에서는 그 감쇠가 약해집니다 — 같은
// 정도의 물리적 느림이 사무실에서는 더 높은 지수로 읽힐 것으로 예상됩니다
// (recipe_tat/MIGRATION.md 의 "셀 크기 감쇠" 항목). 그래서 분위수를 읽는
// 것만으로는 이 값을 검증했다고 할 수 없고, 위 셋과 함께
// `office 확인 YYYY-MM-DD` 를 찍으면 검증하지 않은 상수에 검증 도장을 찍는
// 셈이 됩니다. 장비 수가 많은 칸의 tat_index 분포를 따로 확인한 뒤에
// 이 주석만 따로 바꿉니다.
export const TAT_CEIL = 1.10

export const SIGNAL_META: Record<EquipmentSignal, { label: string, tone: 'warn' | 'info' }> = {
  slow: { label: '느림', tone: 'warn' },
  underused: { label: '저사용', tone: 'warn' },
  narrow: { label: '편중', tone: 'warn' },
  fast: { label: '빠름', tone: 'info' }
}

// 또래 집단(peer group)은 조회 범위 그 자체입니다. 그래서 범위가 여러 fab을
// 걸치면 배지가 장비가 아니라 **fab**을 가리킵니다.
//
//  - `tat_index`의 base(r)은 조회 범위 전체의 레시피별 평균이라, 여러 fab을
//    함께 조회하면 fab 단위의 속도 차이가 그 fab 장비 전부의 지수가 됩니다.
//  - `usage_ratio`/`occupancy`에는 정규화가 **아예** 없습니다. 레시피가 짧은
//    fab의 장비는 같은 개수를 돌아도 두 값이 함께 낮게 나옵니다.
//
// mock에서 실제로 그렇습니다: cd-sem 전 fab 14일 조회에서 `빠름` 9대가 전부
// (여러 창에서 8~9대) meastime 배수가 가장 낮은 M11이고, `저사용`도 배수가
// 낮은 두 fab(M11·R4)에 몰립니다. 배수가 높은 M14/M16은 반대로 `느림`을
// 독차지합니다 — 어느 쪽도 장비 상태가 아니라 fab을 읽은 것입니다.
//
// `percentiles`가 비면 배지를 달지 않는 것과 같은 이유로, 섞인 또래 집단에서도
// 달지 않습니다: **판단 근거가 없으면 경고하지 않습니다.** 원 수치 열은 그대로
// 남으므로 사용자가 잃는 정보는 없습니다.
//
// 이 판정은 `equipmentSignals()` 밖에 있습니다. 그 함수의 계약은 "행 하나와
// 분포 하나에 대한 순수 판정"이고, fab 범위는 행에도 분포에도 들어 있지
// 않습니다 — 호출자가 지키는 조건입니다.
export const isPeerGroupComparable = (rows: readonly { fab_name: string }[]): boolean =>
  new Set(rows.map(row => row.fab_name)).size === 1

const at = (percentiles: FleetPercentiles, metric: string, key: string): number | null => {
  const value = percentiles?.[metric]?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export const equipmentSignals = (
  row: EquipmentSignalInput,
  percentiles: FleetPercentiles
): EquipmentSignal[] => {
  const signals: EquipmentSignal[] = []

  // 꼬리 비교는 모두 포함 부등호(<=, >=)입니다. percentile_summary는
  // nearest-rank라 p10/p90은 항상 실제 표본 값 하나와 같습니다 — 장비
  // 5대짜리 작은 셀에서는 그 표본이 곧 플릿의 최솟값/최댓값 자신인
  // 경우가 흔합니다. 엄격 부등호(<, >)를 쓰면 그 경계를 정의하는 장비
  // 자신이 "자기 꼬리 안"에 들지 못해, 가장 극단적인 — 정확히 배지를
  // 달아야 할 — 장비가 구조적으로 제외됩니다. recipe_count처럼 정수형
  // 지표는 플릿 규모가 커져도 동률이 사라지지 않으므로 이 문제는 mock
  // 특유의 결함이 아니라 상시적입니다.
  const usageTail = at(percentiles, 'usage_ratio', 'p10')
  if (usageTail !== null && row.usage_ratio <= usageTail && row.usage_ratio < USAGE_FLOOR) {
    signals.push('underused')
  }

  // tat_index === null 은 표본 미달입니다. "느리지 않다"가 아니라 "모른다"
  // 이므로 어느 쪽으로도 판정하지 않습니다.
  if (row.tat_index !== null) {
    const slowTail = at(percentiles, 'tat_index', 'p90')
    if (slowTail !== null && row.tat_index >= slowTail && row.tat_index > TAT_CEIL) {
      signals.push('slow')
    }
    const fastTail = at(percentiles, 'tat_index', 'p10')
    if (fastTail !== null && row.tat_index <= fastTail && row.tat_index < TAT_FLOOR) {
      signals.push('fast')
    }
  }

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
