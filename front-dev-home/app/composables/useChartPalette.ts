import { buildChartPalette } from '~/utils/chartPalette'
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
 *
 * Note the older idiom this overlaps: several hardware panels do
 * `const { palette } = useEchartsTheme()` then index `palette.value[n]`
 * directly. That is still correct for "give me N distinguishable colors" (see
 * assignCompareColors in utils/hardwareCompare.ts). Reach for this composable
 * instead when the color has a ROLE — primary series, contrasting overlay,
 * furniture — so the role is named once rather than spelled as an index.
 */
export const useChartPalette = () => {
  const { palette, resolvedThemeName } = useEchartsTheme()

  return computed(() => buildChartPalette(
    palette.value,
    getEchartThemeInk(resolvedThemeName.value),
    getEchartThemeBackground(resolvedThemeName.value)
  ))
}
