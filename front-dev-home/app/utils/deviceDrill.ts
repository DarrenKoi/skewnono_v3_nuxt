// Shared drill-down view-model (D22). Both the descriptive (outlier) and
// prescriptive (cap-violation) surfaces normalize into DrillDevice so a single
// slideover renders both. Adapters are pure + unit-tested.
import { isExemptJob } from './lotHealth.ts'
import { dropLeadingHelperParams } from './outlierDetect.ts'
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

/**
 * 분석 범위 밖이라는 말. **recipe 층 배지와 파라미터 행 꼬리표가 같은 문자열을
 * 씁니다** — 한 화면에서 위아래로 붙어 나오므로 다른 말을 쓰면 두 가지 제외가
 * 있는 것으로 읽힙니다.
 *
 * 문구가 규칙 옆에 사는 이유는 이것이 `isExemptJob` 이 무엇을 뺐는지 설명하는
 * 문장이기 때문입니다. 화면에 두면 규칙이 바뀌어도 설명은 그대로 남습니다.
 */
export const EXEMPT_LABEL = '분석 제외'

/** 배지의 tooltip. 어떤 job 이, 왜 기준선과 판정 **양쪽**에서 빠지는지. */
export const EXEMPT_TITLE = 'CDU 계열(_*CDU)·full/half-map·matrix 측정 job(_FULL/_HALF/_MTX)입니다. '
  + '설계상 측정 규모가 정상 recipe 와 달라 중앙값 기준선과 초과 판정에서 모두 빠집니다.'

/** Descriptive adapter — within-device point-count outliers (Plan 1). */
export const toOutlierDrill = (
  lot_cd: string,
  ctn_desc: string,
  recipes: RecipeInput[],
  result: DeviceOutlierResult
): DrillDevice => {
  const flaggedKey = new Set(result.outliers.map(o => `${o.recipe_id} ${o.name}`))
  const drillRecipes: DrillRecipe[] = recipes.map((r) => {
    // "분석 제외" 꼬리표는 **detectDeviceOutliers 가 실제로 뺀 것**과 같아야
    // 합니다. 이름만 보면(예전 방식) 목록 뒤쪽의 CD_ALIGN 같은 진짜 측정
    // 파라미터에까지 "분석 제외" 가 붙는데, 기준선 쪽은 그것을 세고 있어서 한
    // 화면이 두 가지 이야기를 하게 됩니다 (user-confirmed 2026-08-10: 준비용은
    // 목록 맨 앞의 것뿐입니다).
    const measured = new Set(dropLeadingHelperParams(r.parameters).map(p => p.name))
    const parameters: DrillParameter[] = r.parameters.map((p) => {
      const flagged = flaggedKey.has(`${r.recipe_id} ${p.name}`)
      // 제외된 파라미터는 flagged 가 될 수 없으므로 두 꼬리표가 부딪히지
      // 않습니다 — detectDeviceOutliers 가 같은 규칙으로 이미 걸러 냈습니다.
      const note = flagged
        ? `> ${result.threshold}`
        : measured.has(p.name) ? undefined : EXEMPT_LABEL
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
      // 판정에서 뺀 son 이 상한을 넘었으면 그 사실을 적습니다. 적지 않으면
      // "재 봤더니 상한 안" 과 "아예 안 쟀다" 가 화면에서 같은 모습이 되어,
      // son 판정 토글을 껐다는 사실이 숫자가 줄었다는 것 말고는 드러나지 않습니다.
      note: typeof p.cap !== 'number'
        ? undefined
        : p.violation
          ? `cap ${p.cap}`
          // 꼬리표 열은 112px 라 이보다 길면 두 줄로 접혀 행 높이가 어긋납니다.
          // "son" 을 적지 않아도 되는 것은 판정에서 빠지는 것이 son 뿐이고,
          // 표 위의 토글이 그 사실을 이미 말하고 있기 때문입니다.
          : (!p.judged && p.over_cap) ? `cap ${p.cap} · 제외` : undefined
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
