import type {
  FailDeltaKey,
  RecipeStatusDeltaItem,
  RecipeStatusDeltaTone,
  TatDeltaKey
} from './recipeStatusDelta.ts'

export interface RecipeStatusSummaryDelta {
  /** Empty while the previous-window summary is still loading. */
  text: string
  tone: RecipeStatusDeltaTone
  title: string
  /** The compared window still contains the unfinished anchor day. */
  anchorIncluded?: boolean
}

export interface RecipeStatusSummaryItem {
  label: string
  value: string
  tone?: 'danger'
  delta?: RecipeStatusSummaryDelta
}

/**
 * What the strip should show beside each value.
 *
 * `pending` reserves the slot with an empty delta so the strip does not jump
 * when the previous-window request lands. Neither `items` nor `pending` means
 * the strip has no comparison at all (the recipe-open tables, a failed
 * previous-window request).
 */
export interface RecipeStatusDeltaOptions<K extends string> {
  items?: readonly RecipeStatusDeltaItem<K>[]
  pending?: boolean
  anchorIncluded?: boolean
}

const PENDING_DELTA: RecipeStatusSummaryDelta = { text: '', tone: 'none', title: '' }

const resolveDelta = <K extends string>(
  key: K,
  options: RecipeStatusDeltaOptions<K> | undefined
): Pick<RecipeStatusSummaryItem, 'delta'> => {
  if (!options) return {}
  const flag = options.anchorIncluded ? { anchorIncluded: true } : {}
  if (options.pending) return { delta: { ...PENDING_DELTA, ...flag } }
  const found = options.items?.find(item => item.key === key)
  if (!found) return {}
  return { delta: { text: found.delta, tone: found.tone, title: found.title, ...flag } }
}

const DELTA_CLASS: Record<RecipeStatusDeltaTone, string> = {
  ok: 'text-(--sk-ok)',
  bad: 'text-(--sk-bad)',
  neutral: 'text-(--sk-ink)',
  none: 'text-(--sk-ink-muted)'
}

export const recipeStatusDeltaClass = (tone: RecipeStatusDeltaTone): string =>
  DELTA_CLASS[tone]

/**
 * Tooltip for a delta. The delta text leads because the strip ellipsizes a
 * delta wider than its item, and the tooltip is then the only place the whole
 * value can be read.
 */
export const recipeStatusDeltaTitle = (
  delta: RecipeStatusSummaryDelta
): string | undefined =>
  [delta.text, delta.title].filter(Boolean).join(' · ') || undefined

/** One caption per strip, or `null` when no item carries a comparison. */
export const recipeStatusDeltaCaption = (
  items: readonly RecipeStatusSummaryItem[]
): string | null => {
  const deltas = items.flatMap(item => item.delta ? [item.delta] : [])
  if (!deltas.length) return null
  return deltas.some(delta => delta.anchorIncluded)
    ? '이전 동일 기간 대비(원시 변화) · 기준일 포함'
    : '이전 동일 기간 대비(원시 변화)'
}

export const recipeStatusSummaryValueClass = (
  tone?: RecipeStatusSummaryItem['tone']
): string => tone === 'danger' ? 'text-(--sk-bad)' : 'text-(--sk-ink)'

export const resolveRecipeStatusSummaryValue = (
  pending: boolean,
  value: string | undefined
): string => pending ? '—' : (value ?? '—')

interface FailSummaryInput {
  failLabel: 'Align fails' | 'Meas fails'
  failCount: string
  totalMeasurements: string
  failRatio: string
}

interface TatSummaryInput {
  totalTat: string
  distinctRecipes: string
  totalExecutions: string
  avgMeastime: string
}

export const buildFailSummaryItems = (
  input: FailSummaryInput,
  delta?: RecipeStatusDeltaOptions<FailDeltaKey>
): RecipeStatusSummaryItem[] => [
  { label: input.failLabel, value: input.failCount, tone: 'danger', ...resolveDelta('failCount', delta) },
  { label: 'Total measurements', value: input.totalMeasurements, ...resolveDelta('totalMeasurements', delta) },
  { label: 'Fail ratio', value: input.failRatio, ...resolveDelta('failRatio', delta) }
]

export const buildTatSummaryItems = (
  input: TatSummaryInput,
  delta?: RecipeStatusDeltaOptions<TatDeltaKey>
): RecipeStatusSummaryItem[] => [
  { label: 'Total TAT', value: input.totalTat, ...resolveDelta('totalTat', delta) },
  { label: 'Distinct recipes', value: input.distinctRecipes, ...resolveDelta('distinctRecipes', delta) },
  { label: 'Total executions', value: input.totalExecutions, ...resolveDelta('totalExecutions', delta) },
  { label: 'Avg meastime', value: input.avgMeastime, ...resolveDelta('avgMeastime', delta) }
]
