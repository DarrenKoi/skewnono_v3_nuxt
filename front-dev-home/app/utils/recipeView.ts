import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { AmpRole, AmpRow, IdpImageInfoRow } from '~/composables/useRecipeSearchApi'

export const recipeTableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
} as const

export type ImageSlotKey = Extract<
  keyof IdpImageInfoRow,
  'img_add1' | 'img_add2' | 'image_add3' | 'img_meas1' | 'img_meas2'
>

export interface ImageSlot {
  key: ImageSlotKey
  label: string
  role: AmpRole
  stage: string
}

export const IMAGE_SLOTS: readonly ImageSlot[] = [
  { key: 'img_add1', label: 'img_add1', role: 'address', stage: 'Addressing 1' },
  { key: 'img_add2', label: 'img_add2', role: 'address', stage: 'Addressing 2' },
  { key: 'image_add3', label: 'image_add3', role: 'address', stage: 'Addressing 3' },
  { key: 'img_meas1', label: 'img_meas1', role: 'measure', stage: 'Measure 1' },
  { key: 'img_meas2', label: 'img_meas2', role: 'measure', stage: 'Measure 2' }
] as const

export interface AmpFieldDescriptor {
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

export const AMP_FIELDS_ADDR: readonly AmpFieldDescriptor[] = [
  ...AMP_FIELDS_COMMON,
  { key: 'Template', label: 'Template' },
  { key: 'MatchScore', label: 'MatchScore', unit: '%' },
  { key: 'SearchArea', label: 'SearchArea', unit: 'px' },
  { key: 'Rotation', label: 'Rotation', unit: '°' }
]

export const AMP_FIELDS_MEAS: readonly AmpFieldDescriptor[] = [
  ...AMP_FIELDS_COMMON,
  { key: 'Algo', label: 'Algo' },
  { key: 'ROI', label: 'ROI', unit: 'px' },
  { key: 'EdgeThr', label: 'EdgeThr', unit: '%' },
  { key: 'EdgeDir', label: 'EdgeDir' },
  { key: 'Smooth', label: 'Smooth' }
]

export const ampFieldsForRole = (role: AmpRole): readonly AmpFieldDescriptor[] =>
  role === 'measure' ? AMP_FIELDS_MEAS : AMP_FIELDS_ADDR

export const formatAmpValue = (value: AmpRow[keyof AmpRow] | undefined): string => {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

export type RecipeDetailScreen = 'open' | 'lateral' | 'meas-hist'

export const recipeDetailRoute = (
  toolType: string,
  fab: string,
  screen: RecipeDetailScreen,
  recipeName: string
) => ({
  path: `/ebeam/${toolType}/${fab.toLowerCase()}/recipe-search/${screen}`,
  query: { recipe_name: recipeName }
})

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
  setFlag: unknown
) => RECIPE_ROW_ACTIONS.map((action) => {
  const target = recipeDetailRoute(toolType, fab, action.screen, recipeName)
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
