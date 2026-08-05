// Within-device point-count outlier detection (D22 / grilling Q3).
// Baseline = all parameter point_counts across one device's recipes.
// A parameter is an outlier when point_count > multiplier × median.
// Pure + framework-free (mirrors ruleEngine.ts), unit-tested with node --test.
//
// 특수 측정 job(_WCDU/_FCDU/_FULL/_HALF)은 기준선에서도, 초과 표시 대상에서도
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
import { isExemptJob } from './lotHealth.ts'
import type { RecipeInput } from './ruleEngine'

export const DEFAULT_OUTLIER_MULTIPLIER = 2

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
  // 한 번만 거릅니다. 기준선과 표시 대상이 **같은** 모집단이어야, 화면의
  // "중앙값 6 · outlier 3" 이 서로 다른 recipe 집합을 말하지 않습니다.
  const judged = recipes.filter(r => !isExemptJob(r.recipe_id))
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
