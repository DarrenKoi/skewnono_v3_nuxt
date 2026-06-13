import type { CompareRecipe, CompareIdpFields, CompareParameter } from '~/composables/useRecipeCompareApi'
import type { AmpRole, AmpRow } from '~/composables/useRecipeSearchApi'
import type { ImageSlotKey } from '~/utils/recipeView'

// NOTE: recipeCompare runs under `node --test`, which cannot resolve the `~` alias
// or extension-less sibling imports, while `nuxt typecheck` forbids `.ts`-extension
// imports. So the slot / AMP-field metadata below is inlined rather than imported
// from recipeView.ts. KEEP IN SYNC with recipeView.ts (IMAGE_SLOTS, AMP_FIELDS_*,
// ampFieldsForRole, formatAmpValue).

interface CompareSlot {
  key: ImageSlotKey
  stage: string
  role: AmpRole
}

export const COMPARE_SLOTS: readonly CompareSlot[] = [
  { key: 'img_add1', stage: 'Addressing 1', role: 'address' },
  { key: 'img_add2', stage: 'Addressing 2', role: 'address' },
  { key: 'image_add3', stage: 'Addressing 3', role: 'address' },
  { key: 'img_meas1', stage: 'Measure 1', role: 'measure' },
  { key: 'img_meas2', stage: 'Measure 2', role: 'measure' }
]

interface AmpFieldDescriptor {
  key: keyof AmpRow
  label: string
  unit?: string
}

const AMP_FIELDS_COMMON: readonly AmpFieldDescriptor[] = [
  { key: 'Mag', label: 'Mag', unit: '×' },
  { key: 'Vacc', label: 'Vacc', unit: 'V' },
  { key: 'I_probe', label: 'I_probe', unit: 'pA' },
  { key: 'Frame', label: 'Frame' },
  { key: 'Scan', label: 'Scan' },
  { key: 'WD', label: 'WD', unit: 'mm' },
  { key: 'Det', label: 'Det' }
]

const AMP_FIELDS_ADDR: readonly AmpFieldDescriptor[] = [
  ...AMP_FIELDS_COMMON,
  { key: 'Template', label: 'Template' },
  { key: 'MatchScore', label: 'MatchScore', unit: '%' },
  { key: 'SearchArea', label: 'SearchArea', unit: 'px' },
  { key: 'Rotation', label: 'Rotation', unit: '°' }
]

const AMP_FIELDS_MEAS: readonly AmpFieldDescriptor[] = [
  ...AMP_FIELDS_COMMON,
  { key: 'Algo', label: 'Algo' },
  { key: 'ROI', label: 'ROI', unit: 'px' },
  { key: 'EdgeThr', label: 'EdgeThr', unit: '%' },
  { key: 'EdgeDir', label: 'EdgeDir' },
  { key: 'Smooth', label: 'Smooth' }
]

const ampFieldsForRole = (role: AmpRole): readonly AmpFieldDescriptor[] =>
  role === 'measure' ? AMP_FIELDS_MEAS : AMP_FIELDS_ADDR

const formatAmpValue = (value: AmpRow[keyof AmpRow] | undefined): string =>
  (value === null || value === undefined || value === '') ? '—' : String(value)

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
  const descriptor = COMPARE_SLOTS.find(s => s.key === slot)
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
