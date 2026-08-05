import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import type { SettingBlock, SettingRow } from '~/composables/useRecipeParamDetail'
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

/**
 * Is this ENMP group a SEQUENCE listing rather than a settings group?
 *
 * `sequence_addressing` and `sequence_measurement` name the steps a sequence
 * runs ('Pre Dose', 'Image Save'); every other group holds one step's settings.
 * Two different questions, so the screen puts them on two different tabs.
 *
 * Matched on the `sequence` PREFIX rather than the two names read so far,
 * because the office parser's group names are still being refined — a third
 * sequence group should land on the sequence tab without a code change.
 */
export const isSequenceSection = (section: string | null | undefined): boolean =>
  !!section && section.trim().toLowerCase().startsWith('sequence')

export interface SplitSettingBlock {
  /** The `sequence_*` groups. */
  sequence: SettingBlock | null
  /** Every other group. */
  settings: SettingBlock | null
}

/**
 * Split one AF/PR (ENMP) block into its sequence groups and its settings groups.
 *
 * Both halves keep the source file name, and either may come back with NO rows —
 * a parameter that runs no addressing pass has no `sequence_addressing`. That is
 * deliberately not collapsed to `null`: an empty block renders "읽을 수 있는
 * 설정이 없습니다" (the file was read, the group is not in it) where `null`
 * renders "파일 없음" (there was no file). Those say different things.
 *
 * Row order inside each half is the reader's own — filtered, never re-sorted.
 */
export function splitSequenceSections(block: SettingBlock | null): SplitSettingBlock {
  if (!block) return { sequence: null, settings: null }
  const sequence: SettingRow[] = []
  const settings: SettingRow[] = []
  for (const row of block.rows) {
    (isSequenceSection(row.section) ? sequence : settings).push(row)
  }
  return {
    sequence: { source: block.source, rows: sequence },
    settings: { source: block.source, rows: settings }
  }
}

export interface SplitAfPrSettingBlock {
  addressing: SettingBlock | null
  measurement: SettingBlock | null
  other: SettingBlock | null
}

export function splitAfPrSectionsByDomain(
  block: SettingBlock | null
): SplitAfPrSettingBlock {
  if (!block) {
    return {
      addressing: null,
      measurement: null,
      other: null
    }
  }

  const addressing: SettingRow[] = []
  const measurement: SettingRow[] = []
  const other: SettingRow[] = []

  for (const row of block.rows) {
    const section = row.section?.trim().toLowerCase() ?? ''
    if (section.startsWith('addressing_')) {
      addressing.push(row)
    } else if (section.startsWith('measurement_')) {
      measurement.push(row)
    } else {
      other.push(row)
    }
  }

  const withRows = (rows: SettingRow[]): SettingBlock => ({
    source: block.source,
    rows
  })

  return {
    addressing: withRows(addressing),
    measurement: withRows(measurement),
    other: withRows(other)
  }
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

/**
 * A numeric IDP cell as fixed-point text, tolerating a cell that is not a
 * number.
 *
 * `Coordinate.X` is declared `float` in the backend contract, and on
 * 2026-08-05 the office parser sent it as the string "52.676". The call it hit
 * was a bare `row['Coordinate.X'].toFixed(3)`, which threw inside a computed —
 * so the align table never rendered AND the modal stopped responding to its
 * own close button. A thrown render is not a blank cell; it takes the whole
 * subtree with it.
 *
 * The backend now converts against the contract, which is where the bug is
 * actually fixed. This exists so the next contract violation costs one dash
 * instead of a frozen dialog: a display formatter has no business trusting
 * that a value it is about to print is a number.
 */
export const formatFixed = (value: unknown, digits: number, fallback = '—'): string => {
  const number = typeof value === 'number' ? value : Number(value)
  // Number(null) is 0 and Number('') is 0 — both are missing data, not zero.
  if (value === null || value === undefined || value === '') return fallback
  return Number.isFinite(number) ? number.toFixed(digits) : fallback
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
