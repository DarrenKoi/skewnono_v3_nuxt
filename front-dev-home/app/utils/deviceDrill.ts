// Shared drill-down view-model (D22). Both the descriptive (outlier) and
// prescriptive (cap-violation) surfaces normalize into DrillDevice so a single
// slideover renders both. Adapters are pure + unit-tested.
import type { RecipeInput } from './ruleEngine'
import type { DeviceOutlierResult } from './outlierDetect'

export interface DrillParameter {
  name: string
  point_count: number
  flagged: boolean
  note?: string // why it was flagged, e.g. "> 20" (outlier) or "cap 10" (violation)
}

export interface DrillRecipe {
  recipe_id: string
  flagged: boolean
  total_params: number
  flagged_count: number
  parameters: DrillParameter[]
}

export interface DrillDevice {
  lot_cd: string
  ctn_desc: string
  recipes: DrillRecipe[]
  flagged_recipe_count: number
  flagged_param_count: number
}

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
      return { name: p.name, point_count: p.point_count, flagged, note: flagged ? `> ${result.threshold}` : undefined }
    })
    const flagged_count = parameters.filter(p => p.flagged).length
    return { recipe_id: r.recipe_id, flagged: flagged_count > 0, total_params: parameters.length, flagged_count, parameters }
  })
  return {
    lot_cd,
    ctn_desc,
    recipes: drillRecipes,
    flagged_recipe_count: drillRecipes.filter(r => r.flagged).length,
    flagged_param_count: result.outlier_count
  }
}
