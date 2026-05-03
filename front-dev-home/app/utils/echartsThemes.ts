// Theme objects mirror app/assets/echarts-theme/{vintage,dark}.js. The
// originals are UMD files that rely on `root.echarts`; in Vite/ESM `root` is
// undefined so we replicate the same theme objects here for ESM consumers.
// Importing this file does NOT pull echarts into the bundle — the caller
// passes its echarts module in.

type EchartsModule = { registerTheme: (name: string, theme: object) => void }

const vintageColorPalette = [
  '#d87c7c',
  '#919e8b',
  '#d7ab82',
  '#6e7074',
  '#61a0a8',
  '#efa18d',
  '#787464',
  '#cc7e63',
  '#724e58',
  '#4b565b'
]

const vintageTheme = {
  color: vintageColorPalette,
  backgroundColor: '#fef8ef',
  graph: {
    color: vintageColorPalette
  }
}

const darkContrastColor = '#B9B8CE'
const darkBackgroundColor = '#100C2A'

const darkAxisCommon = () => ({
  axisLine: { lineStyle: { color: darkContrastColor } },
  splitLine: { lineStyle: { color: '#484753' } },
  splitArea: { areaStyle: { color: ['rgba(255,255,255,0.02)', 'rgba(255,255,255,0.05)'] } },
  minorSplitLine: { lineStyle: { color: '#20203B' } }
})

const darkColorPalette = [
  '#4992ff',
  '#7cffb2',
  '#fddd60',
  '#ff6e76',
  '#58d9f9',
  '#05c091',
  '#ff8a45',
  '#8d48e3',
  '#dd79ff'
]

const darkTheme = {
  darkMode: true,
  color: darkColorPalette,
  backgroundColor: darkBackgroundColor,
  axisPointer: {
    lineStyle: { color: '#817f91' },
    crossStyle: { color: '#817f91' },
    label: { color: '#fff' }
  },
  legend: { textStyle: { color: darkContrastColor } },
  textStyle: { color: darkContrastColor },
  title: {
    textStyle: { color: '#EEF1FA' },
    subtextStyle: { color: '#B9B8CE' }
  },
  toolbox: { iconStyle: { borderColor: darkContrastColor } },
  visualMap: { textStyle: { color: darkContrastColor } },
  timeline: {
    lineStyle: { color: darkContrastColor },
    label: { color: darkContrastColor },
    controlStyle: { color: darkContrastColor, borderColor: darkContrastColor }
  },
  calendar: {
    itemStyle: { color: darkBackgroundColor },
    dayLabel: { color: darkContrastColor },
    monthLabel: { color: darkContrastColor },
    yearLabel: { color: darkContrastColor }
  },
  timeAxis: darkAxisCommon(),
  logAxis: darkAxisCommon(),
  valueAxis: darkAxisCommon(),
  categoryAxis: { ...darkAxisCommon(), splitLine: { show: false } },
  line: { symbol: 'circle' },
  graph: { color: darkColorPalette },
  gauge: { title: { color: darkContrastColor } },
  candlestick: {
    itemStyle: {
      color: '#FD1050',
      color0: '#0CF49B',
      borderColor: '#FD1050',
      borderColor0: '#0CF49B'
    }
  }
}

let registered = false

export const registerEchartsThemes = (echarts: EchartsModule) => {
  if (registered) return
  echarts.registerTheme('vintage', vintageTheme)
  echarts.registerTheme('dark', darkTheme)
  registered = true
}
