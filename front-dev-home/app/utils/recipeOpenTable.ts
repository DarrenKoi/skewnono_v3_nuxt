import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import type { RecipeStatusSummaryItem } from '~/utils/recipeStatusSummary'

export type RecipeOpenSortKey = Extract<keyof IdpImageInfoRow,
  | 'Parameter' | 'SEQ' | 'Region' | 'Addressing' | 'Mother_Para'
  | 'Double_Addressing' | 'Meas_Counting' | 'dnumber_removed'
>
export type RecipeOpenSortDirection = 'asc' | 'desc'
export const DEFAULT_RECIPE_OPEN_SORT = {
  key: 'SEQ' as RecipeOpenSortKey,
  direction: 'asc' as RecipeOpenSortDirection
}

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
const compare = (
  left: IdpImageInfoRow[RecipeOpenSortKey],
  right: IdpImageInfoRow[RecipeOpenSortKey]
) => {
  if (typeof left === 'number' && typeof right === 'number') return left - right
  if (typeof left === 'boolean' && typeof right === 'boolean') {
    return Number(left) - Number(right)
  }
  return collator.compare(String(left), String(right))
}

export const sortRecipeOpenRows = (
  rows: readonly IdpImageInfoRow[],
  key: RecipeOpenSortKey = DEFAULT_RECIPE_OPEN_SORT.key,
  direction: RecipeOpenSortDirection = DEFAULT_RECIPE_OPEN_SORT.direction
) => {
  const multiplier = direction === 'asc' ? 1 : -1
  return rows.map((row, sourceIndex) => ({ row, sourceIndex })).sort((a, b) => (
    compare(a.row[key], b.row[key]) * multiplier || a.sourceIndex - b.sourceIndex
  ))
}

export const nextRecipeOpenSort = (
  currentKey: RecipeOpenSortKey,
  currentDirection: RecipeOpenSortDirection,
  requestedKey: RecipeOpenSortKey
) => ({
  key: requestedKey,
  direction: (currentKey === requestedKey && currentDirection === 'asc'
    ? 'desc'
    : 'asc') as RecipeOpenSortDirection
})

export const buildRecipeOpenSummaryItems = (
  measurementPointCount: number,
  alignPointCount: number
): RecipeStatusSummaryItem[] => [
  { label: '측정 포인트', value: measurementPointCount.toLocaleString() },
  { label: 'Align 포인트', value: alignPointCount.toLocaleString() }
]
