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
}

export interface RecipeStatusSummaryItem {
  label: string
  value: string
  tone?: 'danger'
  delta?: RecipeStatusSummaryDelta
}

/**
 * The comparison the strip should show beside the values.
 *
 * `'pending'` reserves every slot with an empty delta so the strip does not
 * jump when the previous-window request lands; `undefined` means no comparison
 * at all (the recipe-open tables, a failed previous-window request).
 */
export type RecipeStatusDeltaInput<K extends string> = 'pending' | readonly RecipeStatusDeltaItem<K>[]

const PENDING_DELTA: RecipeStatusSummaryDelta = { text: '', tone: 'none', title: '' }

const resolveDelta = <K extends string>(
  key: K,
  delta: RecipeStatusDeltaInput<K> | undefined
): Pick<RecipeStatusSummaryItem, 'delta'> => {
  if (!delta) return {}
  if (delta === 'pending') return { delta: PENDING_DELTA }
  const found = delta.find(item => item.key === key)
  return found ? { delta: { text: found.delta, tone: found.tone, title: found.title } } : {}
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

/**
 * One caption per strip, or `null` when no item carries a comparison.
 * `anchorIncluded`: the compared window still contains the unfinished anchor day.
 */
export const recipeStatusDeltaCaption = (
  items: readonly RecipeStatusSummaryItem[],
  anchorIncluded = false
): string | null => {
  if (!items.some(item => item.delta)) return null
  return anchorIncluded
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
  delta?: RecipeStatusDeltaInput<FailDeltaKey>
): RecipeStatusSummaryItem[] => [
  { label: input.failLabel, value: input.failCount, tone: 'danger', ...resolveDelta('failCount', delta) },
  { label: 'Total measurements', value: input.totalMeasurements, ...resolveDelta('totalMeasurements', delta) },
  { label: 'Fail ratio', value: input.failRatio, ...resolveDelta('failRatio', delta) }
]

export const buildTatSummaryItems = (
  input: TatSummaryInput,
  delta?: RecipeStatusDeltaInput<TatDeltaKey>
): RecipeStatusSummaryItem[] => [
  { label: 'Total TAT', value: input.totalTat, ...resolveDelta('totalTat', delta) },
  { label: 'Distinct recipes', value: input.distinctRecipes, ...resolveDelta('distinctRecipes', delta) },
  { label: 'Total executions', value: input.totalExecutions, ...resolveDelta('totalExecutions', delta) },
  { label: 'Avg meastime', value: input.avgMeastime, ...resolveDelta('avgMeastime', delta) }
]
