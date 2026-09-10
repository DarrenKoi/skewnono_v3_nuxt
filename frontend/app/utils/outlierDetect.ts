// Within-device point-count outlier detection (D22 / grilling Q3).
// Baseline = all parameter point_counts across one device's recipes.
// A parameter is an outlier when point_count > multiplier × median.
// Pure + framework-free (mirrors ruleEngine.ts), unit-tested with node --test.
//
// 특수 측정 job(_*CDU/_FULL/_HALF/_MTX)은 기준선에서도, 초과 표시 대상에서도
// 빠집니다 (user-confirmed 2026-08-05). 웨이퍼 전면을 훑는 것이 목적인 job 이라
// 파라미터당 point_count 가 정상 recipe 와 자릿수부터 다릅니다 — 섞어 두면
//
//   * 중앙값이 위로 끌려 올라가 정상 recipe 의 진짜 과다 측정이 문턱 아래로
//     숨고,
//   * 이 job 들 자신은 매번 outlier 로 잡혀 목록을 채웁니다. 설계대로 측정한
//     것이라 "초과" 가 아닙니다.
//
// 판정(cap)에서 빼는 것과 같은 이유·같은 술어입니다 — `isExemptJob` 이 한 벌만
// 있는 이유가 그것입니다. 값 import 라 확장자를 답니다(node --test).
//
// 제외는 **두 층**입니다. 위가 recipe 층(job 종류), 아래가 파라미터 층 —
// 아래 `isOutlierExemptParam` 을 보십시오.
import { isExemptJob } from './lotHealth.ts'
import type { RecipeInput } from './ruleEngine'

export const DEFAULT_OUTLIER_MULTIPLIER = 2

/**
 * CD 측정량을 논하는 자리에 낄 수 없는 파라미터 이름 (user-confirmed
 * 2026-08-05). 둘 다 실물에 있는 이름입니다.
 *
 *   Dummy — 자리를 채우는 placeholder. 재는 대상 자체가 아닙니다.
 *   Align — 정렬(addressing)용. 측정이 아니라 **측정을 위한 준비**라, 그 point
 *           수는 "얼마나 많이 쟀는가" 라는 질문의 답에 들어가면 안 됩니다.
 *           (설비 알람도 align 9006 과 meas 9007 을 다른 사건으로 셉니다.)
 *
 * 둘 다 실물 point 수는 **1~3** 입니다 (user-confirmed 2026-08-10). 그래서 이
 * 목록이 실제로 막는 것은 **오검출**입니다 — 남겨 두면 중앙값이 끌려 내려가고
 * 문턱(중앙값×2)도 함께 내려가, 정상 범위의 파라미터가 outlier 로 잡힙니다.
 * 반대 방향(큰 값이 기준선을 끌어올려 진짜 과다측정을 가리는 것)도 규칙상
 * 막히지만, 실물 값으로는 일어나지 않습니다. 판정은 값의 크기에 기대지 않으므로
 * 두 방향 모두 테스트가 있습니다.
 *
 * 실물 표기는 위처럼 **대문자가 아닙니다** — 다른 파라미터가 대체로 전부
 * 대문자인 것과 달리 이 둘만 "Dummy"/"Align" 입니다 (user-confirmed
 * 2026-08-05). 아래 목록을 대문자로 적어 둔 것은 비교 전에 이름을 대문자로
 * 올리기 때문이지, 실물이 그렇게 생겨서가 아닙니다. 어느 표기로 와도 걸려야
 * 합니다 — 표기를 하나로 못박는 순간 사무실에서 조용히 새어 나갑니다.
 *
 * 이 목록이 **outlier 전용**인 것이 중요합니다. 판정(cap) 쪽의 DUMMY 면제는
 * 룰 데이터의 name_override(`cap: null`)가 표현하고, 그래야 셀마다 켜고 끌 수
 * 있습니다 (providers/rules.py `_SAMPLE_OVERRIDES`). 여기서 두 관심사를 한
 * 술어로 묶으면 룰 한 칸을 고칠 때 중앙값 기준선까지 따라 움직입니다 —
 * outlier 는 서술적 통계고 cap 은 규범이라, 둘은 같은 스위치를 쓰면 안 됩니다.
 *
 * Align 은 지금 판정에서는 빼지 **않습니다** — 요청 범위가 outlier 집계였고,
 * 판정까지 넓히는 것은 룰 데이터의 결정이라 여기서 몰래 하지 않습니다.
 *
 * 규칙은 룰 데이터의 affix 매칭과 같은 의미입니다: 이름이 그 낱말로 시작하거나
 * 끝나면 참, 한복판에 우연히 든 것은 거짓.
 */
// 대문자로 적힌 것은 **비교용 정규형**입니다 — 실물 표기가 아닙니다(위 주석).
const NON_MEASUREMENT_PARAMS = ['DUMMY', 'ALIGN'] as const

export const isOutlierExemptParam = (name: string): boolean => {
  const up = (name || '').trim().toUpperCase()
  return NON_MEASUREMENT_PARAMS.some(word => up.startsWith(word) || up.endsWith(word))
}

/**
 * 파라미터 목록에서 **맨 앞의** Dummy/Align 만 떼어 냅니다.
 *
 * 이 둘은 recipe 마다 늘 있는 것이 아니라 가끔 나타나고, 나타날 때는 측정
 * 순서의 맨 앞에 옵니다 (user-confirmed 2026-08-10) — 정렬은 측정보다 먼저 하는
 * 준비 작업이니 순서가 곧 그 뜻입니다. 그래서 판정이 이름만이 아니라 "이름 +
 * 맨 앞" 입니다.
 *
 * 이름만 보면 뒤쪽에 있는 **진짜 측정 파라미터**까지 지웁니다 — 이름이 "ALIGN"
 * 으로 끝나는 CD 파라미터가 있으면 그렇습니다. 그 손실은 예외가 아니라 중앙값이
 * 조금 달라지는 것으로만 나타나 발견이 늦습니다.
 *
 * 연속된 것을 전부 떼는 이유는 Dummy 와 Align 이 함께 올 때 둘 다 앞에 있기
 * 때문입니다. 백엔드 ``para_buckets.measurement_parameters`` 와 같은 규칙입니다.
 */
export const dropLeadingHelperParams = <T extends { name: string }>(
  parameters: readonly T[]
): T[] => {
  let index = 0
  while (index < parameters.length && isOutlierExemptParam(parameters[index]!.name)) {
    index += 1
  }
  return parameters.slice(index)
}

export interface PointOutlier {
  recipe_id: string
  name: string
  point_count: number
}

export interface DeviceOutlierResult {
  median: number
  threshold: number
  outliers: PointOutlier[]
  outlier_count: number
}

const median = (values: number[]): number => {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1]! + sorted[mid]!) / 2
    : sorted[mid]!
}

export const detectDeviceOutliers = (
  recipes: RecipeInput[],
  multiplier: number = DEFAULT_OUTLIER_MULTIPLIER
): DeviceOutlierResult => {
  // 두 층 모두 **한 번만** 거릅니다. 기준선과 표시 대상이 같은 모집단이어야,
  // 화면의 "중앙값 6 · outlier 3" 이 서로 다른 집합을 말하지 않습니다. 아래
  // 두 소비처가 이 배열 하나만 읽는 것이 그 보장입니다.
  const judged = recipes
    .filter(r => !isExemptJob(r.recipe_id))
    .map(r => ({ ...r, parameters: dropLeadingHelperParams(r.parameters) }))
  const allPoints = judged.flatMap(r => r.parameters.map(p => p.point_count))
  const med = median(allPoints)
  const threshold = med * multiplier

  const outliers: PointOutlier[] = []
  for (const r of judged) {
    for (const p of r.parameters) {
      if (p.point_count > threshold) {
        outliers.push({ recipe_id: r.recipe_id, name: p.name, point_count: p.point_count })
      }
    }
  }
  return { median: med, threshold, outliers, outlier_count: outliers.length }
}
