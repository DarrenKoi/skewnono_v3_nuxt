import {
  DEFAULT_ECHART_THEME_SELECTION,
  ECHART_THEME_OPTIONS,
  ECHART_THEME_STORAGE_KEY,
  echartThemeId,
  getEchartThemePalette,
  getEchartThemeSurface,
  isEchartThemeSelection,
  resolveEchartThemeName,
  type EchartThemeSelection
} from '~/utils/echartsThemes'

export const useEchartsTheme = () => {
  const colorMode = useColorMode()

  // Via usePersistedState rather than a hand-rolled read + watch, because this
  // composable is instantiated once per chart (useEchart) AND again per chart
  // that reads useChartPalette. The old inline `watch(..., { flush: 'sync' })`
  // lived in the composable body with no guard, so every one of those
  // instances registered its own writer and a single theme pick fired dozens
  // of synchronous localStorage writes of the same string. The factory binds
  // exactly one writer per stateKey in a detached scope.
  //
  // serialize/deserialize are overridden to keep the value a RAW string: the
  // key predates this and already holds `default`, not `"default"`.
  const selectedTheme = usePersistedState<EchartThemeSelection>(
    'echarts-theme-selection',
    ECHART_THEME_STORAGE_KEY,
    {
      default: () => DEFAULT_ECHART_THEME_SELECTION,
      normalize: parsed =>
        isEchartThemeSelection(parsed) ? parsed : DEFAULT_ECHART_THEME_SELECTION,
      serialize: value => value,
      deserialize: raw => raw
    }
  )

  const resolvedThemeName = computed(() => resolveEchartThemeName(selectedTheme.value, colorMode.value))

  // The active theme's series palette. Charts that need explicit color literals
  // (e.g. tooltip markers) read indices off this so they match the line colors
  // ECharts assigns from the same palette.
  const palette = computed(() => getEchartThemePalette(resolvedThemeName.value))

  // What echarts.init() must be handed. Each theme is registered once per color
  // mode, so this changes when EITHER the picked theme or the color mode
  // changes -- which is what lets useEchart's single dispose/re-init watch
  // cover both without knowing that color modes exist.
  const themeId = computed(() => echartThemeId(resolvedThemeName.value, colorMode.value))

  // Tone of the surface the chart is actually drawn on: the theme's own in its
  // native mode, the mode's neutral furniture when the picker and the color
  // mode disagree.
  const surface = computed(() => getEchartThemeSurface(resolvedThemeName.value, colorMode.value))

  return {
    selectedTheme,
    resolvedThemeName,
    themeId,
    palette,
    surface,
    themeOptions: ECHART_THEME_OPTIONS
  }
}
