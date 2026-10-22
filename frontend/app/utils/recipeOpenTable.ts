import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import type { RecipeStatusSummaryItem } from '~/utils/recipeStatusSummary'

export type RecipeOpenSortKey = Extract<keyof IdpImageInfoRow,
  | 'Parameter' | 'SEQ' | 'Region' | 'Addressing' | 'Mother_Para'
  | 'Double_Addressing' | 'Meas_Counting' | 'dnumber_removed'
>
export type RecipeOpenSortDirection = 'asc' | 'desc'
// Region, then SEQ (user's call 2026-10-22): a Region's parameters measure one
// image, so they read as a group, mother first.
export const DEFAULT_RECIPE_OPEN_SORT = {
  key: 'Region' as RecipeOpenSortKey,
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
  // Ties fall back to Region then SEQ, both ascending whatever the direction,
  // and last to payload order so equal rows never swap between renders.
  return rows.map((row, sourceIndex) => ({ row, sourceIndex })).sort((a, b) => (
    compare(a.row[key], b.row[key]) * multiplier
    || compare(a.row.Region, b.row.Region)
    || compare(a.row.SEQ, b.row.SEQ)
    || a.sourceIndex - b.sourceIndex
  ))
}

/**
 * The `v-for` key for one sorted row — its position in the UNSORTED payload,
 * never its contents.
 *
 * A content key is what the table used until 2026-08-18, and it looked safe:
 * `Parameter-SEQ` is unique in every mock recipe, because the mock numbers SEQ
 * as a running row index. The office table carries no such rule — SEQ is an
 * "image definition 순번" (docs/datatables/hitachi/recipe_idp.txt) and a sparse row can
 * leave both columns empty — so two rows there can share the pair.
 *
 * When they do, re-sorting does not reorder the table, it GROWS it: Vue's keyed
 * patch matches new children to old ones through a key→index map, a repeated
 * key overwrites its own entry, and the unmatched old row is left in the DOM
 * instead of being moved. One orphan per header click, on data whose length
 * never changed.
 *
 * `sourceIndex` is unique by construction and stable across re-sorts, which is
 * what a key has to be. It is an index, but not the display index — the usual
 * "never key by index" warning is about the latter.
 */
export const recipeOpenRowKey = (item: { sourceIndex: number }) => item.sourceIndex

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

/** The IDP table's optional columns. Parameter is always shown, so it is not here. */
export type IdpColumnKey = Exclude<RecipeOpenSortKey, 'Parameter'>
export const IDP_OPTIONAL_COLUMNS: readonly { key: IdpColumnKey, label: string }[] = [
  { key: 'SEQ', label: 'SEQ' },
  { key: 'Region', label: 'Region' },
  { key: 'Addressing', label: 'Addressing' },
  { key: 'Mother_Para', label: 'Mother' },
  { key: 'Double_Addressing', label: 'Double' },
  { key: 'Meas_Counting', label: 'Cnt' },
  { key: 'dnumber_removed', label: 'd# 제거' }
]
export const DEFAULT_IDP_COLUMNS: IdpColumnKey[] = IDP_OPTIONAL_COLUMNS.map(column => column.key)

/**
 * Stored keys → known keys only, so a renamed column cannot break the table.
 * A pick that held ONLY retired keys (the dropped P_No / D_No) means the
 * defaults, not "hide everything" — only a stored [] means that.
 */
export const normalizeIdpColumns = (parsed: unknown): IdpColumnKey[] => {
  if (!Array.isArray(parsed)) throw new TypeError('not a column list')
  const known = new Set<unknown>(IDP_OPTIONAL_COLUMNS.map(column => column.key))
  const kept = parsed.filter((key): key is IdpColumnKey => known.has(key))
  return kept.length === 0 && parsed.length > 0 ? [...DEFAULT_IDP_COLUMNS] : kept
}
