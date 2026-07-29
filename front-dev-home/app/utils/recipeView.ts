import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import type { RecipeSearchSource } from '~/utils/recipeSelection'

export const recipeTableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
} as const

export type ImageSlotKey = Extract<
  keyof IdpImageInfoRow,
  'img_add1' | 'img_add2' | 'image_add3' | 'img_meas1' | 'img_meas2'
>

export type SlotRole = 'address' | 'measure'

export interface ImageSlot {
  key: ImageSlotKey
  label: string
  role: SlotRole
  stage: string
  /**
   * Does this slot name a `.jpeg` in the raw-recipe folder?
   *
   * `img_add2` and `img_meas2` do NOT — they name setting files (`PRMP0000`
   * and `PRMS0000`), which is why the panel shows three thumbnails and two
   * settings tables rather than five thumbnails. `image_add3` breaks the
   * `img_*` naming run but IS an image (user-confirmed 2026-07-29).
   */
  hasImage: boolean
}

export const IMAGE_SLOTS: readonly ImageSlot[] = [
  { key: 'img_add1', label: 'img_add1', role: 'address', stage: 'Addressing 1', hasImage: true },
  { key: 'img_add2', label: 'img_add2', role: 'address', stage: 'Addressing 2', hasImage: false },
  { key: 'image_add3', label: 'image_add3', role: 'address', stage: 'Addressing 3', hasImage: true },
  { key: 'img_meas1', label: 'img_meas1', role: 'measure', stage: 'Measure 1', hasImage: true },
  { key: 'img_meas2', label: 'img_meas2', role: 'measure', stage: 'Measure 2', hasImage: false }
] as const

/** French "non" — the office's empty-slot sentinel. NOT "none". */
export const EMPTY_SLOT = 'non'

export const isEmptySlot = (value: string | null | undefined): boolean =>
  !value || value.trim().toLowerCase() === EMPTY_SLOT

export const formatSettingValue = (value: string | null | undefined): string => {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

export type RecipeDetailScreen = 'open' | 'lateral' | 'meas-hist'

export const isRecipeDetailScreenSupported = (
  screen: RecipeDetailScreen,
  source: RecipeSearchSource
): boolean => source === 'redis' || screen !== 'open'

export const recipeDetailRoute = (
  toolType: string,
  fab: string,
  screen: RecipeDetailScreen,
  recipeName: string,
  source: RecipeSearchSource = 'redis'
) => {
  if (!isRecipeDetailScreenSupported(screen, source)) {
    throw new RangeError('OpenSearch recipes do not support the open detail view')
  }
  return {
    path: `/ebeam/${toolType}/${fab.toLowerCase()}/recipe-search/${screen}`,
    query: {
      recipe_name: recipeName,
      ...(source === 'opensearch' ? { source } : {})
    }
  }
}

export interface RecipeRowAction {
  screen: RecipeDetailScreen
  label: string
  icon: string
}

export const RECIPE_ROW_ACTIONS: readonly RecipeRowAction[] = [
  { screen: 'open', label: '열어 보기', icon: 'i-lucide-file-search' },
  { screen: 'lateral', label: '횡전개', icon: 'i-lucide-network' },
  { screen: 'meas-hist', label: '측정 이력', icon: 'i-lucide-history' }
] as const

export const buildRecipeDetailNavItems = (
  toolType: string,
  fab: string,
  recipeName: string,
  activeScreen: RecipeDetailScreen,
  setFlag: unknown,
  source: RecipeSearchSource = 'redis'
) => RECIPE_ROW_ACTIONS
  .filter(action => isRecipeDetailScreenSupported(action.screen, source))
  .map((action) => {
    const target = recipeDetailRoute(toolType, fab, action.screen, recipeName, source)
    return {
      ...action,
      active: action.screen === activeScreen,
      to: setFlag === '1'
        ? { ...target, query: { ...target.query, set: '1' } }
        : target
    }
  })

export const readRecipeNameQuery = (route: RouteLocationNormalizedLoaded): string => {
  const raw = route.query.recipe_name
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim() : ''
}

export const readRecipeSourceQuery = (
  route: RouteLocationNormalizedLoaded
): RecipeSearchSource => route.query.source === 'opensearch' ? 'opensearch' : 'redis'

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
