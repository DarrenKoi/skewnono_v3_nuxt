import { buildChartPalette, type ChartPalette } from '~/utils/chartPalette'
import { getEchartThemeBackground, getEchartThemeInk } from '~/utils/echartsThemes'

/**
 * The active theme's presentation colors, for charts that must name a color
 * explicitly instead of letting ECharts assign one.
 *
 * ECharts hands series colors out automatically from the theme palette, so a
 * chart that sets none is already theme-aware. This is for the rest: a fit line
 * that has to contrast with its scatter, a label drawn onto the canvas, a
 * reference line. Those need a literal, and reading it from here is what keeps
 * the literal tracking the palette ECharts is using for everything else.
 *
 * Returns a computed rather than a plain object because the theme is switchable
 * at runtime — read it as `sk.value.series` inside your option computed, and
 * the option rebuilds when the user picks a different theme.
 *
 * Data-encoding and semantic colors do NOT belong here; import SK_SCALE and
 * SK_STATE directly, they are the same in every theme by design.
 */
export const useChartPalette = () => {
  const { palette, resolvedThemeName } = useEchartsTheme()

  return computed<ChartPalette>(() => buildChartPalette(
    palette.value,
    getEchartThemeInk(resolvedThemeName.value),
    getEchartThemeBackground(resolvedThemeName.value)
  ))
}
