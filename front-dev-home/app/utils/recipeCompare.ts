import type { CompareRecipe, CompareIdpFields, CompareParameter } from '~/composables/useRecipeCompareApi'
import {
  IMAGE_SLOTS,
  ampFieldsForRole,
  formatAmpValue,
  type ImageSlotKey
} from './recipeView.ts'

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

const MISSING = '없음'

export interface MatrixRow {
  key: string
  label: string
  unit?: string
  values: string[]
  differs: boolean
}

interface IdpFieldDescriptor {
  key: keyof CompareIdpFields
  label: string
}

export const IDP_COMPARE_FIELDS: readonly IdpFieldDescriptor[] = [
  { key: 'Addressing', label: 'Addressing' },
  { key: 'Double_Addressing', label: 'Double_Addressing' },
  { key: 'Mother_Para', label: 'Mother_Para' },
  { key: 'Region', label: 'Region' },
  { key: 'Meas_Counting', label: 'Meas_Counting' },
  { key: 'dnumber_removed', label: 'dnumber_removed' }
]

export function cellsDiffer(values: string[]): boolean {
  if (values.length < 2) return false
  return values.some(v => v !== values[0])
}

export function findParameter(recipe: CompareRecipe, parameter: string): CompareParameter | null {
  return recipe.parameters.find(p => p.Parameter === parameter) ?? null
}

export function buildIdpRows(recipes: CompareRecipe[], parameter: string): MatrixRow[] {
  return IDP_COMPARE_FIELDS.map((field) => {
    const values = recipes.map((recipe) => {
      const p = findParameter(recipe, parameter)
      if (!p) return MISSING
      const v = p.idp[field.key]
      return v === null || v === undefined || v === '' ? '—' : String(v)
    })
    return { key: String(field.key), label: field.label, values, differs: cellsDiffer(values) }
  })
}

export function buildAmpRows(
  recipes: CompareRecipe[],
  parameter: string,
  slot: ImageSlotKey
): MatrixRow[] {
  const descriptor = IMAGE_SLOTS.find(s => s.key === slot)
  if (!descriptor) return []
  return ampFieldsForRole(descriptor.role).map((field) => {
    const values = recipes.map((recipe) => {
      const p = findParameter(recipe, parameter)
      if (!p) return MISSING
      const amp = p.amp.find(a => a.slot === slot) ?? null
      if (!amp) return MISSING
      return formatAmpValue(amp[field.key])
    })
    return { key: String(field.key), label: field.label, unit: field.unit, values, differs: cellsDiffer(values) }
  })
}

export function imageFilenames(
  recipes: CompareRecipe[],
  parameter: string,
  slot: ImageSlotKey
): (string | null)[] {
  return recipes.map((recipe) => {
    const p = findParameter(recipe, parameter)
    return p ? (p.images[slot] ?? null) : null
  })
}
