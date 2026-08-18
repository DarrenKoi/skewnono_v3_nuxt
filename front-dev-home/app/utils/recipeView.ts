import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import type { SettingBlock, SettingRow } from '~/composables/useRecipeParamDetail'
import type { RecipeSearchSource } from '~/utils/recipeSelection'
import { formatDateTimeLocal } from './dateTime.ts'

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
  fabSegment: string,
  screen: RecipeDetailScreen,
  recipeName: string,
  source: RecipeSearchSource = 'redis',
  ownerFab = ''
) => {
  if (!isRecipeDetailScreenSupported(screen, source)) {
    throw new RangeError('OpenSearch recipes do not support the open detail view')
  }
  return {
    path: `/ebeam/${toolType}/${fabSegment.toLowerCase()}/recipe-search/${screen}`,
    query: {
      recipe_name: recipeName,
      ...(ownerFab ? { fab_name: ownerFab.toUpperCase() } : {}),
      ...(source === 'opensearch' ? { source } : {})
    }
  }
}

/**
 * The recipe identifier the three detail screens are addressed by.
 *
 * `recipe_search` knows a recipe by ONE name and it is the class-qualified one:
 * its catalog rows carry `recipe_name = "ADI/ADI_CD_BIAS_001"`, which is
 * character-for-character meas_hist's `full_name` (docs/datatables/meas_hist.txt).
 * That is why `RecipeSearchRow` has no separate `full_name` field — there is
 * nothing there to separate.
 *
 * The analytics rankings (recipe-tat, fail-issue) DO split the two: their rows
 * carry a bare `recipe_name` beside a qualified `full_name`, because they
 * aggregate over `full_name.keyword` and show the class in its own column. A
 * row from those tables therefore has to be qualified before it can address a
 * detail screen — handing over the bare half means:
 *
 *   * open — the office adapter takes the FTP class directory from the prefix
 *     (`_class_name`), so an unqualified name makes the Redis registry decline;
 *     the meas_hist fallback then term-matches `full_name.keyword` against a
 *     string that field never holds. No candidate .idp, a bare `LookupError`,
 *     and the app factory turns that into a **502 upstream_data_error**.
 *   * lateral — the same term on `full_name.keyword`; answers empty.
 *   * meas-hist — the one that survives, because it matches EITHER field.
 *
 * None of which the mock can catch: `get_recipe_open_data` seeds an RNG off
 * whatever string it is handed and fabricates a recipe around it, so a bare
 * name is a green 200 at home and a 502 at the office.
 */
export const recipeDetailId = (row: {
  recipe_name: string
  full_name?: string | null
}): string => (row.full_name ?? '').trim() || row.recipe_name.trim()

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
  fabSegment: string,
  recipeName: string,
  activeScreen: RecipeDetailScreen,
  setFlag: unknown,
  source: RecipeSearchSource = 'redis',
  ownerFab = ''
) => RECIPE_ROW_ACTIONS
  .filter(action => isRecipeDetailScreenSupported(action.screen, source))
  .map((action) => {
    const target = recipeDetailRoute(toolType, fabSegment, action.screen, recipeName, source, ownerFab)
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

export const readRecipeOwnerFabQuery = (route: RouteLocationNormalizedLoaded): string => {
  const raw = route.query.fab_name
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim().toUpperCase() : ''
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

// Kept as a named recipe-domain alias over the shared formatter — 6 call sites
// and a test block already speak in these terms, and those tests now double as
// a contract check on `formatDateTimeLocal`. Its defaults already match what
// this did: '' for empty input, the input echoed back when unparseable.
export const formatRecipeTimestamp = (iso: string, opts: { withSeconds?: boolean } = {}): string =>
  formatDateTimeLocal(iso, { withSeconds: opts.withSeconds })
