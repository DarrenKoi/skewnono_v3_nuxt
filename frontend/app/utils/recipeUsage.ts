import type {
  RecipeUsageCatalogRow,
  RecipeUsageRankingRow,
  RecipeUsageSource
} from '../composables/useRecipeUsageApi.ts'

export type RecipeUsageSourceFilter = RecipeUsageSource | 'all'

export const RECIPE_USAGE_SOURCE_LABELS: Record<RecipeUsageSource, string> = {
  mes: 'MES 실적',
  tool: '장비 상주',
  both: '실적+상주'
}

export const RECIPE_USAGE_SOURCE_HELP
  = 'MES 실적: MES로 작업을 시작한 이력이 있는 recipe입니다. '
    + '장비 상주: 현재 장비에 파일이 있는 recipe입니다. '
    + '실적+상주: 두 곳 모두에 있는 recipe입니다.'

/** Space-separated tokens, every one a case-insensitive substring of `text`. */
export const matchesRecipeTokens = (text: string, query: string): boolean => {
  const haystack = text.toLowerCase()
  return query.toLowerCase().split(/\s+/).filter(Boolean).every(token => haystack.includes(token))
}

export const filterRecipeCatalog = (
  rows: readonly RecipeUsageCatalogRow[],
  query: string,
  source: RecipeUsageSourceFilter = 'all'
): RecipeUsageCatalogRow[] =>
  rows.filter(row =>
    (source === 'all' || row.source === source) && matchesRecipeTokens(row.recipe_id, query))

export type RecipeCatalogSortKey = 'recipe_id' | 'tool_count' | 'n_uses' | 'first_used' | 'last_used'

const catalogSortValue = (row: RecipeUsageCatalogRow, key: RecipeCatalogSortKey) =>
  key === 'tool_count' ? row.eqp_ids.length : row[key]

/** A recipe with no usage date (source `tool`) sorts last in BOTH directions:
 *  "never used" is not the oldest date, and must not lead an ascending sort. */
export const sortRecipeCatalog = (
  rows: readonly RecipeUsageCatalogRow[],
  key: RecipeCatalogSortKey,
  desc: boolean
): RecipeUsageCatalogRow[] => {
  const dir = desc ? -1 : 1
  return [...rows].sort((a, b) => {
    const av = catalogSortValue(a, key)
    const bv = catalogSortValue(b, key)
    if (av === bv) return a.recipe_id.localeCompare(b.recipe_id)
    if (av === null) return 1
    if (bv === null) return -1
    return (av < bv ? -1 : 1) * dir
  })
}

// ponytail: fixed sample floor. Make it scale with the window length if 14-day
// and 90-day windows turn out to need different floors.
export const RECIPE_USAGE_MIN_FAIL_RUNS = 5

export interface RecipeUsageFailRow extends RecipeUsageRankingRow {
  /** Below the sample floor: its rate is shown but never ranks. */
  low_sample: boolean
  /** fail_rate, or 0 below the floor. The Fail table sorts on this, so one
   *  failed run out of one cannot lead a rate sort. */
  fail_rate_ranked: number
}

/** Recipes that failed at least once, by fail_runs then by rate. */
export const rankRecipeFails = (
  rows: readonly RecipeUsageRankingRow[],
  minRuns = RECIPE_USAGE_MIN_FAIL_RUNS
): RecipeUsageFailRow[] =>
  rows
    .filter(row => row.fail_runs > 0)
    .map((row) => {
      const lowSample = row.runs < minRuns
      return { ...row, low_sample: lowSample, fail_rate_ranked: lowSample ? 0 : row.fail_rate }
    })
    .sort((a, b) =>
      b.fail_runs - a.fail_runs
      || b.fail_rate_ranked - a.fail_rate_ranked
      || a.recipe_id.localeCompare(b.recipe_id))

/** Pull a YYYY-MM-DD range inside [min, max]. A null bound is open. */
export const clampDateRange = (
  range: { start: string, end: string },
  min: string | null,
  max: string | null
): { start: string, end: string } => {
  const clamp = (date: string) => {
    if (min && date < min) return min
    if (max && date > max) return max
    return date
  }
  return { start: clamp(range.start), end: clamp(range.end) }
}
