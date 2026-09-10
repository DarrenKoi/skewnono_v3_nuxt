export interface RecipeStatusTrendPoint {
  date: string
}

export const filterRecipeStatusTrendPoints = <T extends RecipeStatusTrendPoint>(
  points: readonly T[],
  anchorDate: string | null | undefined,
  includeToday: boolean
): T[] => {
  if (includeToday || !anchorDate) return [...points]
  return points.filter(point => point.date !== anchorDate)
}
