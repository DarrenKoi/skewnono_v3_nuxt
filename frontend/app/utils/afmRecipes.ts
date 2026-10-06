// Pure logic for AFM Recipe 현황: one tool's measurement list, grouped by the
// recipe that made each measurement. No DOM/Nuxt imports so it runs under
// `node --test`. Days are the rows' own `formatted_date` strings throughout —
// nothing here builds a local-time Date, and a null cell is "unknown", never 0.
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import { measuredAt } from './afmSearch.ts'
import { inclusiveDayCount, shiftIsoDate } from './dateTime.ts'

export const FILE_KINDS = [
  { flag: 'has_data', label: 'Data' },
  { flag: 'has_profile', label: 'Profile' },
  { flag: 'has_image', label: '이미지' },
  { flag: 'has_align', label: 'Align' },
  { flag: 'has_tip', label: 'Tip' }
] as const

// How many days the list's sparkline covers, ending today.
export const SPARK_DAYS = 14
// A recipe measured within this many calendar days, today included, is recent.
export const RECENT_DAYS = 7
// A recipe whose last measurement is more than this many days back is stale.
export const STALE_DAYS = 30

export interface RecipeSummary {
  recipe: string
  // Its measurements, newest first; the ones with no date come last.
  rows: AfmFileRow[]
  count: number
  // Rows with a `formatted_date`: what first / last / the day counts are read from.
  dated: number
  first: string | null
  last: string | null
  // Calendar days from `last` to today; null when no row has a date.
  daysAgo: number | null
  lots: number
  // Over the rows that carry a point count; null when none does.
  pointMin: number | null
  pointMax: number | null
  // The kinds at least one measurement has, in FILE_KINDS order.
  files: { label: string, count: number }[]
  // Daily counts for the SPARK_DAYS days ending today, oldest first.
  spark: number[]
  // Measurements with not_completed_count > 0, out of the `failedOf` that
  // recorded the value at all. `failed` is null when failedOf is 0.
  failed: number | null
  failedOf: number
}

const dayOf = (row: AfmFileRow) => row.formatted_date ?? ''
const daysBetween = (from: string, to: string) => inclusiveDayCount(from, to) - 1

const summarize = (recipe: string, group: AfmFileRow[], today: string): RecipeSummary => {
  const at = new Map(group.map(row => [row, measuredAt(row)]))
  // "YYYY-MM-DD HH:MM:SS" sorts as text; '' (no date) sorts after everything.
  const rows = [...group].sort((a, b) => (at.get(b)! > at.get(a)! ? 1 : at.get(b)! < at.get(a)! ? -1 : 0))
  const days = group.map(dayOf).filter(Boolean).sort()
  const first = days[0] ?? null
  const last = days.at(-1) ?? null
  const points = group.flatMap(row => row.point_count ?? [])
  const judged = group.flatMap(row => row.not_completed_count ?? [])
  const sparkStart = shiftIsoDate(today, SPARK_DAYS - 1)
  const spark = Array.from({ length: SPARK_DAYS }, () => 0)
  for (const day of days) {
    if (day >= sparkStart && day <= today) spark[daysBetween(sparkStart, day)]!++
  }
  return {
    recipe,
    rows,
    count: group.length,
    dated: days.length,
    first,
    last,
    daysAgo: last === null ? null : daysBetween(last, today),
    lots: new Set(group.map(row => (row.lot_id ?? '').trim()).filter(Boolean)).size,
    pointMin: points.length ? Math.min(...points) : null,
    pointMax: points.length ? Math.max(...points) : null,
    files: FILE_KINDS.flatMap(({ flag, label }) => {
      const count = group.filter(row => row[flag]).length
      return count ? [{ label, count }] : []
    }),
    spark,
    failed: judged.length ? judged.filter(n => n > 0).length : null,
    failedOf: judged.length
  }
}

export interface RecipeBoard {
  recipes: RecipeSummary[]
  // Measurements that belong to a recipe.
  measured: number
  // Left out: no recipe name, so no recipe to belong to.
  unnamed: number
  // Among `measured`: no formatted_date, so in no day count.
  undated: number
}

// `today` is the viewer's local date, "YYYY-MM-DD" (todayStamp()).
export const recipeBoard = (rows: AfmFileRow[], today: string): RecipeBoard => {
  const groups = new Map<string, AfmFileRow[]>()
  let unnamed = 0
  for (const row of rows) {
    const recipe = (row.recipe_name ?? '').trim()
    if (!recipe) {
      unnamed++
      continue
    }
    const group = groups.get(recipe)
    if (group) group.push(row)
    else groups.set(recipe, [row])
  }
  const recipes = [...groups.entries()].map(([recipe, group]) => summarize(recipe, group, today))
  return {
    recipes,
    measured: rows.length - unnamed,
    unnamed,
    undated: recipes.reduce((sum, r) => sum + r.count - r.dated, 0)
  }
}

export type RecipeTile = 'recent' | 'stale' | 'once'

// A recipe with no dated measurement is neither recent nor stale: unknown.
const TILE_TEST: Record<RecipeTile, (recipe: RecipeSummary) => boolean> = {
  recent: r => r.daysAgo !== null && r.daysAgo < RECENT_DAYS,
  stale: r => r.daysAgo !== null && r.daysAgo > STALE_DAYS,
  once: r => r.count === 1
}

export const tileCounts = (recipes: RecipeSummary[]): Record<RecipeTile, number> => ({
  recent: recipes.filter(TILE_TEST.recent).length,
  stale: recipes.filter(TILE_TEST.stale).length,
  once: recipes.filter(TILE_TEST.once).length
})

// Every whitespace-separated term must be in the name, whatever its case.
export const filterRecipes = (recipes: RecipeSummary[], query: string, tile: RecipeTile | null): RecipeSummary[] => {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean)
  return recipes.filter((r) => {
    const name = r.recipe.toLowerCase()
    return (!tile || TILE_TEST[tile](r)) && terms.every(term => name.includes(term))
  })
}

export type AfmRecipeSortKey = 'recipe' | 'count' | 'last' | 'first' | 'lots' | 'point' | 'failed'
export interface AfmRecipeSort {
  key: AfmRecipeSortKey
  desc: boolean
}
export const DEFAULT_RECIPE_SORT: AfmRecipeSort = { key: 'last', desc: true }

// Point sorts on the smallest count, then the largest; 미완료 on its count.
const SORT_VALUE: Record<AfmRecipeSortKey, (recipe: RecipeSummary) => (string | number | null)[]> = {
  recipe: r => [r.recipe],
  count: r => [r.count],
  last: r => [r.last],
  first: r => [r.first],
  lots: r => [r.lots],
  point: r => [r.pointMin, r.pointMax],
  failed: r => [r.failed]
}

// A null sorts last whichever way the column runs; ties fall back to the name.
export const sortRecipes = (recipes: RecipeSummary[], sort: AfmRecipeSort): RecipeSummary[] => {
  const value = SORT_VALUE[sort.key]
  return [...recipes].sort((a, b) => {
    const av = value(a)
    const bv = value(b)
    for (let i = 0; i < av.length; i++) {
      const x = av[i] ?? null
      const y = bv[i] ?? null
      if (x === y) continue
      if (x === null) return 1
      if (y === null) return -1
      const order = typeof x === 'string' ? x.localeCompare(y as string) : x - (y as number)
      if (order) return sort.desc ? -order : order
    }
    return a.recipe.localeCompare(b.recipe)
  })
}

// One recipe's daily counts over its own first-to-last span, empty days included.
export const dailyCounts = (recipe: RecipeSummary): { day: string, count: number }[] => {
  if (recipe.first === null || recipe.last === null) return []
  const counts = new Map<string, number>()
  for (const row of recipe.rows) {
    const day = dayOf(row)
    if (day) counts.set(day, (counts.get(day) ?? 0) + 1)
  }
  return Array.from({ length: inclusiveDayCount(recipe.first, recipe.last) }, (_, i) => {
    const day = shiftIsoDate(recipe.first!, -i)
    return { day, count: counts.get(day) ?? 0 }
  })
}

// The tip types (`tip_id`) a recipe was measured with, most used first.
// Measurements that name no tip are in no count.
export const tipUsage = (recipe: RecipeSummary): { tip: string, count: number }[] => {
  const counts = new Map<string, number>()
  for (const row of recipe.rows) {
    const tip = (row.tip_id ?? '').trim()
    if (tip) counts.set(tip, (counts.get(tip) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([tip, count]) => ({ tip, count }))
    .sort((a, b) => b.count - a.count || a.tip.localeCompare(b.tip))
}

// The tallest day on any row's sparkline: every row is drawn against it, so
// the bars compare between recipes. Never below 1 (a bar needs a scale).
export const sparkPeak = (recipes: RecipeSummary[]): number =>
  Math.max(1, ...recipes.flatMap(r => r.spark))

export const sparkTotal = (recipe: RecipeSummary): number => recipe.spark.reduce((a, b) => a + b, 0)

// --- cell text ---

export const daysAgoLabel = (daysAgo: number | null): string =>
  daysAgo === null ? '' : daysAgo === 0 ? '오늘' : daysAgo > 0 ? `${daysAgo}일 전` : `${-daysAgo}일 뒤`

export const pointLabel = (recipe: RecipeSummary): string =>
  recipe.pointMin === null ? '–' : recipe.pointMin === recipe.pointMax ? String(recipe.pointMin) : `${recipe.pointMin}–${recipe.pointMax}`

// `Profile`, or `Profile 3/6` when only some of the measurements have the kind.
export const fileLabel = (file: { label: string, count: number }, total: number): string =>
  file.count === total ? file.label : `${file.label} ${file.count}/${total}`

export const failedLabel = (recipe: RecipeSummary): string =>
  recipe.failed === null ? '–' : `${recipe.failed} / ${recipe.failedOf}`
