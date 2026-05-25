import {
  DEFAULT_ECHART_THEME_SELECTION,
  ECHART_THEME_OPTIONS,
  ECHART_THEME_STORAGE_KEY,
  getEchartThemePalette,
  isEchartThemeSelection,
  resolveEchartThemeName,
  type EchartThemeSelection
} from '~/utils/echartsThemes'

export const useEchartsTheme = () => {
  const colorMode = useColorMode()
  const selectedTheme = useState<EchartThemeSelection>(
    'echarts-theme-selection',
    () => DEFAULT_ECHART_THEME_SELECTION
  )
  const initialized = useState('echarts-theme-selection-initialized', () => false)

  if (import.meta.client && !initialized.value) {
    const saved = window.localStorage.getItem(ECHART_THEME_STORAGE_KEY)
    selectedTheme.value = isEchartThemeSelection(saved) ? saved : DEFAULT_ECHART_THEME_SELECTION
    if (!isEchartThemeSelection(saved)) {
      window.localStorage.setItem(ECHART_THEME_STORAGE_KEY, selectedTheme.value)
    }
    initialized.value = true
  }

  const resolvedThemeName = computed(() => resolveEchartThemeName(selectedTheme.value, colorMode.value))

  // The active theme's series palette. Charts that need explicit color literals
  // (e.g. tooltip markers) read indices off this so they match the line colors
  // ECharts assigns from the same palette.
  const palette = computed(() => getEchartThemePalette(resolvedThemeName.value))

  if (import.meta.client) {
    watch(
      selectedTheme,
      (next) => {
        window.localStorage.setItem(ECHART_THEME_STORAGE_KEY, next)
      },
      { flush: 'sync' }
    )
  }

  return {
    selectedTheme,
    resolvedThemeName,
    palette,
    themeOptions: ECHART_THEME_OPTIONS
  }
}
