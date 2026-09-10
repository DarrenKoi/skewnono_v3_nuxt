export interface RecipeStatusSummaryItem {
  label: string
  value: string
  tone?: 'danger'
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
  input: FailSummaryInput
): RecipeStatusSummaryItem[] => [
  { label: input.failLabel, value: input.failCount, tone: 'danger' },
  { label: 'Total measurements', value: input.totalMeasurements },
  { label: 'Fail ratio', value: input.failRatio }
]

export const buildTatSummaryItems = (
  input: TatSummaryInput
): RecipeStatusSummaryItem[] => [
  { label: 'Total TAT', value: input.totalTat },
  { label: 'Distinct recipes', value: input.distinctRecipes },
  { label: 'Total executions', value: input.totalExecutions },
  { label: 'Avg meastime', value: input.avgMeastime }
]
