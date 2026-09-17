// Deep links INTO 스큐보아's search screen from other pages (장비 리스트,
// Recipe 현황 / 검색, 디바이스 통계). The link carries the search-bar text the
// user would have typed (`eq:` / `recipe:` tokens, see utils/measHistQuery.ts)
// plus an optional FAB filter; SearchLanding applies both once and runs the
// search. Pure, so it is unit-tested under raw `node --test`.

export const SKEWVOIR_TOOL_TYPES = ['cd-sem', 'hv-sem'] as const
export type SkewvoirToolType = typeof SKEWVOIR_TOOL_TYPES[number]

/** 스큐보아 exists for the two SEM families only — no link for the others. */
export const hasSkewvoir = (toolType: string): toolType is SkewvoirToolType =>
  (SKEWVOIR_TOOL_TYPES as readonly string[]).includes(toolType)

export interface SkewvoirSearchTarget {
  eq?: string
  /** The class-qualified recipe name (`full_name`) — see recipeDetailId. */
  recipe?: string
  fab?: string
}

export const skewvoirSearchRoute = (toolType: SkewvoirToolType, target: SkewvoirSearchTarget) => {
  const tokens: string[] = []
  if (target.eq?.trim()) tokens.push(`eq:${target.eq.trim()}`)
  if (target.recipe?.trim()) tokens.push(`recipe:${target.recipe.trim()}`)
  const fab = target.fab?.trim().toUpperCase()
  return {
    path: `/ebeam/${toolType}/skewvoir`,
    query: { ...(tokens.length ? { q: tokens.join(' ') } : {}), ...(fab ? { fab } : {}) }
  }
}
