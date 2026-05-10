import type { RouteLocationNormalizedLoaded } from 'vue-router'

export const recipeTableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis',
  th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
} as const

export const readRecipeNameQuery = (route: RouteLocationNormalizedLoaded): string => {
  const raw = route.query.recipe_name
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim() : ''
}

export const formatRecipeTimestamp = (iso: string, opts: { withSeconds?: boolean } = {}): string => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso

  const pad = (n: number) => String(n).padStart(2, '0')
  const yyyy = date.getFullYear()
  const mm = pad(date.getMonth() + 1)
  const dd = pad(date.getDate())
  const hh = pad(date.getHours())
  const mi = pad(date.getMinutes())

  if (opts.withSeconds) {
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${pad(date.getSeconds())}`
  }
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}
