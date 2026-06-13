import type { CompareRecipe } from '~/composables/useRecipeCompareApi'

export const GROUPING_DEFAULT_THRESHOLD = 8
export const OUTLIER_SHARE = 0.25

export type Coverage = 'all' | 'partial' | 'unique'
export type CoverageFilter = 'all' | 'common' | 'partial' | 'unique'

export interface OverlapRow {
  parameter: string
  presentIn: string[]
  count: number
  total: number
  coverage: Coverage
}

export function classifyCoverage(count: number, total: number): Coverage {
  if (total > 0 && count === total) return 'all'
  if (count <= 1) return 'unique'
  return 'partial'
}

export function buildOverlap(recipes: CompareRecipe[]): OverlapRow[] {
  const total = recipes.length
  const order: string[] = []
  const present = new Map<string, Set<string>>()

  for (const recipe of recipes) {
    const seenInRecipe = new Set<string>()
    for (const p of recipe.parameters) {
      if (seenInRecipe.has(p.Parameter)) continue
      seenInRecipe.add(p.Parameter)
      if (!present.has(p.Parameter)) {
        present.set(p.Parameter, new Set())
        order.push(p.Parameter)
      }
      present.get(p.Parameter)!.add(recipe.recipe_id)
    }
  }

  return order.map((parameter) => {
    const ids = present.get(parameter)!
    return {
      parameter,
      presentIn: recipes.filter(r => ids.has(r.recipe_id)).map(r => r.recipe_id),
      count: ids.size,
      total,
      coverage: classifyCoverage(ids.size, total)
    }
  })
}

export function filterOverlap(rows: OverlapRow[], filter: CoverageFilter): OverlapRow[] {
  if (filter === 'all') return rows
  const want: Coverage = filter === 'common' ? 'all' : filter
  return rows.filter(r => r.coverage === want)
}

export function commonParameters(rows: OverlapRow[]): string[] {
  return rows.filter(r => r.coverage === 'all').map(r => r.parameter)
}
