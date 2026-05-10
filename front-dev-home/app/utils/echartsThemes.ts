type EchartsModule = { registerTheme: (name: string, theme: object) => void }

export type EchartThemeName = 'vintage' | 'dark' | 'macarons' | 'infographic' | 'shine' | 'roma'
export type EchartThemeSelection = 'default' | EchartThemeName

type ThemeOption = {
  value: EchartThemeSelection
  label: string
  fileName: string
  description: string
  colors: readonly string[]
  backgroundColor: string
  textColor: string
}

export const ECHART_THEME_STORAGE_KEY = 'skewnono:echarts-theme'
export const DEFAULT_ECHART_THEME_SELECTION: EchartThemeSelection = 'default'

const vintageColors = [
  '#d87c7c',
  '#919e8b',
  '#d7ab82',
  '#6e7074',
  '#61a0a8',
  '#efa18d'
] as const

const darkColors = [
  '#4992ff',
  '#7cffb2',
  '#fddd60',
  '#ff6e76',
  '#58d9f9',
  '#05c091'
] as const

const macaronsColors = [
  '#2ec7c9',
  '#b6a2de',
  '#5ab1ef',
  '#ffb980',
  '#d87a80',
  '#8d98b3'
] as const

const infographicColors = [
  '#C1232B',
  '#27727B',
  '#FCCE10',
  '#E87C25',
  '#B5C334',
  '#FE8463'
] as const

const shineColors = [
  '#c12e34',
  '#e6b600',
  '#0098d9',
  '#2b821d',
  '#005eaa',
  '#339ca8'
] as const

const romaColors = [
  '#E01F54',
  '#001852',
  '#f5e8c8',
  '#b8d2c7',
  '#c6b38e',
  '#a4d8c2'
] as const

export const ECHART_THEME_OPTIONS: readonly ThemeOption[] = [
  {
    value: 'default',
    label: 'Default',
    fileName: 'vintage.js / dark.js',
    description: 'Keeps the current app behavior: vintage in light mode and dark in dark mode.',
    colors: ['#d87c7c', '#919e8b', '#fef8ef', '#100C2A', '#4992ff', '#7cffb2'],
    backgroundColor: '#fef8ef',
    textColor: '#3f3a34'
  },
  {
    value: 'vintage',
    label: 'Vintage',
    fileName: 'vintage.js',
    description: 'Warm paper-like background with muted red, green, and ochre chart colors.',
    colors: vintageColors,
    backgroundColor: '#fef8ef',
    textColor: '#3f3a34'
  },
  {
    value: 'dark',
    label: 'Dark',
    fileName: 'dark.js',
    description: 'High-contrast dark canvas with bright blue, green, yellow, and red accents.',
    colors: darkColors,
    backgroundColor: '#100C2A',
    textColor: '#EEF1FA'
  },
  {
    value: 'macarons',
    label: 'Macarons',
    fileName: 'macarons.js',
    description: 'Soft pastel palette for dashboards that need a lighter, gentler tone.',
    colors: macaronsColors,
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'infographic',
    label: 'Infographic',
    fileName: 'infographic.js',
    description: 'Bold red, teal, yellow, and orange colors suited to presentation-style charts.',
    colors: infographicColors,
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'shine',
    label: 'Shine',
    fileName: 'shine.js',
    description: 'Strong primary colors with a crisp business-report feel.',
    colors: shineColors,
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'roma',
    label: 'Roma',
    fileName: 'roma.js',
    description: 'Deep red and navy with muted cream and green supporting colors.',
    colors: romaColors,
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  }
] as const

const axisLine = (color: string) => ({
  axisLine: { lineStyle: { color } },
  splitLine: { lineStyle: { color: `${color}33` } }
})

const createLightTheme = (colors: readonly string[], axisColor: string) => ({
  color: [...colors],
  title: {
    textStyle: {
      fontWeight: 'normal'
    }
  },
  tooltip: {
    backgroundColor: 'rgba(50,50,50,0.72)',
    textStyle: {
      color: '#fff'
    }
  },
  categoryAxis: axisLine(axisColor),
  valueAxis: axisLine(axisColor),
  line: {
    symbol: 'circle'
  },
  graph: {
    color: [...colors]
  }
})

const themes: Record<EchartThemeName, object> = {
  vintage: {
    color: [...vintageColors],
    backgroundColor: '#fef8ef',
    graph: {
      color: [...vintageColors]
    }
  },
  dark: {
    darkMode: true,
    color: [...darkColors],
    backgroundColor: '#100C2A',
    legend: {
      textStyle: {
        color: '#B9B8CE'
      }
    },
    textStyle: {
      color: '#B9B8CE'
    },
    title: {
      textStyle: {
        color: '#EEF1FA'
      },
      subtextStyle: {
        color: '#B9B8CE'
      }
    },
    categoryAxis: {
      ...axisLine('#B9B8CE'),
      splitLine: {
        show: false
      }
    },
    valueAxis: axisLine('#B9B8CE'),
    line: {
      symbol: 'circle'
    },
    graph: {
      color: [...darkColors]
    }
  },
  macarons: createLightTheme(macaronsColors, '#008acd'),
  infographic: createLightTheme(infographicColors, '#27727B'),
  shine: createLightTheme(shineColors, '#06467c'),
  roma: createLightTheme(romaColors, '#001852')
}

let registered = false

export const isEchartThemeSelection = (value: unknown): value is EchartThemeSelection =>
  ECHART_THEME_OPTIONS.some(option => option.value === value)

export const resolveEchartThemeName = (
  selection: EchartThemeSelection,
  colorMode: string
): EchartThemeName => {
  if (selection !== 'default') return selection
  return colorMode === 'dark' ? 'dark' : 'vintage'
}

export const registerEchartsThemes = (echarts: EchartsModule) => {
  if (registered) return
  Object.entries(themes).forEach(([name, theme]) => {
    echarts.registerTheme(name, theme)
  })
  registered = true
}
