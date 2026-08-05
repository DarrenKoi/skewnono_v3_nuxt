// Shared drill-down view-model (D22). Both the descriptive (outlier) and
// prescriptive (cap-violation) surfaces normalize into DrillDevice so a single
// slideover renders both. Adapters are pure + unit-tested.
import { isExemptJob } from './lotHealth.ts'
import { isOutlierExemptParam } from './outlierDetect.ts'
import type { RecipeInput, LotHealth } from './ruleEngine'
import type { DeviceOutlierResult } from './outlierDetect'

export interface DrillParameter {
  name: string
  point_count: number
  flagged: boolean
  /**
   * 이 행을 한마디로 설명하는 꼬리표. 걸렸으면 왜 걸렸는지("> 20" outlier,
   * "cap 10" violation), 분석에서 빠졌으면 빠졌다는 사실("분석 제외")입니다.
   *
   * 빠진 것도 말해 주어야 하는 이유는 ALIGN 때문입니다 — point 40 짜리가 아무
   * 표시 없이 놓여 있고 바로 위 정상 파라미터 13 은 붉게 잡혀 있으면, 규칙이
   * 고장난 것으로 읽힙니다. 값을 감추지 않고 이유만 답니다.
   */
  note?: string
}

export interface DrillRecipe {
  recipe_id: string
  flagged: boolean
  total_params: number
  flagged_count: number
  parameters: DrillParameter[]
  /**
   * 분석 범위 밖의 특수 측정 job(_*CDU/_FULL/_HALF/_MTX)인가.
   *
   * 목록에서 **빼지 않고 표시만** 합니다. 이 job 들은 파라미터당 point 수가
   * 정상 recipe 의 몇 배라, 아무 말 없이 미표시로 두면 "104 point 인데 왜 초과가
   * 아니지" 로 읽혀 제외 규칙이 고장난 것처럼 보입니다. 빼 버리면 이번에는
   * 디바이스가 실제로 돌리는 recipe 가 목록에서 사라집니다.
   */
  exempt?: boolean
}

export interface DrillDevice {
  lot_cd: string
  ctn_desc: string
  recipes: DrillRecipe[]
  flagged_recipe_count: number
  flagged_param_count: number
}

/** DUMMY·ALIGN 행의 꼬리표. recipe 층의 '분석 제외' 배지와 같은 말을 씁니다. */
const EXEMPT_PARAM_NOTE = '분석 제외'

/** Descriptive adapter — within-device point-count outliers (Plan 1). */
export const toOutlierDrill = (
  lot_cd: string,
  ctn_desc: string,
  recipes: RecipeInput[],
  result: DeviceOutlierResult
): DrillDevice => {
  const flaggedKey = new Set(result.outliers.map(o => `${o.recipe_id} ${o.name}`))
  const drillRecipes: DrillRecipe[] = recipes.map((r) => {
    const parameters: DrillParameter[] = r.parameters.map((p) => {
      const flagged = flaggedKey.has(`${r.recipe_id} ${p.name}`)
      // 제외된 파라미터는 flagged 가 될 수 없으므로 두 꼬리표가 부딪히지
      // 않습니다 — detectDeviceOutliers 가 같은 술어로 이미 걸러 냈습니다.
      const note = flagged
        ? `> ${result.threshold}`
        : isOutlierExemptParam(p.name) ? EXEMPT_PARAM_NOTE : undefined
      return { name: p.name, point_count: p.point_count, flagged, note }
    })
    const flagged_count = parameters.filter(p => p.flagged).length
    return {
      recipe_id: r.recipe_id,
      flagged: flagged_count > 0,
      total_params: parameters.length,
      flagged_count,
      parameters,
      // detectDeviceOutliers 가 이미 뺐으므로 여기서 flagged 가 켜질 일은
      // 없습니다. 그 사실을 화면이 말하게 하는 것이 이 플래그의 역할입니다.
      exempt: isExemptJob(r.recipe_id)
    }
  })
  return {
    lot_cd,
    ctn_desc,
    recipes: drillRecipes,
    flagged_recipe_count: drillRecipes.filter(r => r.flagged).length,
    flagged_param_count: result.outlier_count
  }
}

/** Prescriptive adapter — cap violations from evaluateLot (D22, count not ratio). */
export const toViolationDrill = (
  lot_cd: string,
  ctn_desc: string,
  health: LotHealth
): DrillDevice => {
  const drillRecipes: DrillRecipe[] = health.recipes.map((r) => {
    const parameters: DrillParameter[] = r.results.map(p => ({
      name: p.name,
      point_count: p.point_count,
      flagged: p.violation,
      note: p.violation && typeof p.cap === 'number' ? `cap ${p.cap}` : undefined
    }))
    return {
      recipe_id: r.recipe_id,
      flagged: !r.pass && r.gray == null,
      total_params: r.total_params,
      flagged_count: r.violation_params.length,
      parameters
    }
  })
  return {
    lot_cd,
    ctn_desc,
    recipes: drillRecipes,
    flagged_recipe_count: health.violation_recipes, // count (D22)
    flagged_param_count: drillRecipes.reduce((sum, r) => sum + r.flagged_count, 0)
  }
}
