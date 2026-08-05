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
 *   DUMMY — 자리를 채우는 placeholder. 재는 대상 자체가 아닙니다.
 *   ALIGN — 정렬(addressing)용. 측정이 아니라 **측정을 위한 준비**라, 그 point
 *           수는 "얼마나 많이 쟀는가" 라는 질문의 답에 들어가면 안 됩니다.
 *           (설비 알람도 align 9006 과 meas 9007 을 다른 사건으로 셉니다.)
 *
 * 이 목록이 **outlier 전용**인 것이 중요합니다. 판정(cap) 쪽의 DUMMY 면제는
 * 룰 데이터의 name_override(`cap: null`)가 표현하고, 그래야 셀마다 켜고 끌 수
 * 있습니다 (providers/rules.py `_SAMPLE_OVERRIDES`). 여기서 두 관심사를 한
 * 술어로 묶으면 룰 한 칸을 고칠 때 중앙값 기준선까지 따라 움직입니다 —
 * outlier 는 서술적 통계고 cap 은 규범이라, 둘은 같은 스위치를 쓰면 안 됩니다.
 *
 * ALIGN 은 지금 판정에서는 빼지 **않습니다** — 요청 범위가 outlier 집계였고,
 * 판정까지 넓히는 것은 룰 데이터의 결정이라 여기서 몰래 하지 않습니다.
 *
 * 규칙은 룰 데이터의 affix 매칭과 같은 의미입니다: 이름이 그 낱말로 시작하거나
 * 끝나면 참, 한복판에 우연히 든 것은 거짓.
 */
const NON_MEASUREMENT_PARAMS = ['DUMMY', 'ALIGN'] as const

export const isOutlierExemptParam = (name: string): boolean => {
  const up = (name || '').trim().toUpperCase()
  return NON_MEASUREMENT_PARAMS.some(word => up.startsWith(word) || up.endsWith(word))
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
    .map(r => ({ ...r, parameters: r.parameters.filter(p => !isOutlierExemptParam(p.name)) }))
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
