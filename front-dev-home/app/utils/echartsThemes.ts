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
    description: '밝은 화면에서는 Vintage, 어두운 화면에서는 Dark 테마를 자동으로 사용합니다.',
    colors: ['#d87c7c', '#919e8b', '#fef8ef', '#100C2A', '#4992ff', '#7cffb2'],
    backgroundColor: '#fef8ef',
    textColor: '#3f3a34'
  },
  {
    value: 'vintage',
    label: 'Vintage',
    fileName: 'vintage.js',
    description: '종이처럼 따뜻한 배경에 차분한 빨강, 초록, 황토색을 사용합니다.',
    colors: vintageColors,
    backgroundColor: '#fef8ef',
    textColor: '#3f3a34'
  },
  {
    value: 'dark',
    label: 'Dark',
    fileName: 'dark.js',
    description: '어두운 배경에 밝은 파랑, 초록, 노랑, 빨강을 사용합니다.',
    colors: darkColors,
    backgroundColor: '#100C2A',
    textColor: '#EEF1FA'
  },
  {
    value: 'macarons',
    label: 'Macarons',
    fileName: 'macarons.js',
    description: '밝고 부드러운 느낌의 연한 색을 사용합니다.',
    colors: macaronsColors,
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'infographic',
    label: 'Infographic',
    fileName: 'infographic.js',
    description: '발표용 차트에 어울리는 선명한 빨강, 청록, 노랑, 주황을 사용합니다.',
    colors: infographicColors,
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'shine',
    label: 'Shine',
    fileName: 'shine.js',
    description: '업무 보고서에 어울리는 또렷한 기본 색을 사용합니다.',
    colors: shineColors,
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'roma',
    label: 'Roma',
    fileName: 'roma.js',
    description: '짙은 빨강과 남색에 차분한 크림색과 초록을 함께 사용합니다.',
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

// Registered themes render with a transparent canvas so each chart inherits its
// card's --sk-surface. The theme's own backgroundColor (kept in the theme-picker
// swatch metadata above) otherwise painted an opaque rectangle that never
// matched the card. The light alt-themes below (createLightTheme) already omit
// backgroundColor, so only the two defaults need the override.
const themes: Record<EchartThemeName, object> = {
  vintage: {
    color: [...vintageColors],
    backgroundColor: 'transparent',
    graph: {
      color: [...vintageColors]
    }
  },
  dark: {
    darkMode: true,
    color: [...darkColors],
    backgroundColor: 'transparent',
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

const themePalettes: Record<EchartThemeName, readonly string[]> = {
  vintage: vintageColors,
  dark: darkColors,
  macarons: macaronsColors,
  infographic: infographicColors,
  shine: shineColors,
  roma: romaColors
}

// The color array a given theme cycles through for its series. Components that
// must hardcode a color reference (tooltip HTML, axis-name text) read from here
// so those literals track the same palette ECharts auto-assigns to the series.
export const getEchartThemePalette = (name: EchartThemeName): readonly string[] =>
  themePalettes[name]

// Themes render on a transparent canvas so charts inherit their card surface.
// A PNG export, however, needs a solid backdrop or it comes out transparent and
// looks broken on light backgrounds. These match each theme's intended tone:
// vintage's warm paper, dark's navy, and white for the light alt-themes.
const themeBackgrounds: Record<EchartThemeName, string> = {
  vintage: '#fef8ef',
  dark: '#100C2A',
  macarons: '#ffffff',
  infographic: '#ffffff',
  shine: '#ffffff',
  roma: '#ffffff'
}

export const getEchartThemeBackground = (name: EchartThemeName): string =>
  themeBackgrounds[name]

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
