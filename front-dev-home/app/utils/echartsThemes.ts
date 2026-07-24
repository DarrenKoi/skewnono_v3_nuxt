type EchartsModule = { registerTheme: (name: string, theme: object) => void }

export type EchartThemeName
  = | 'vintage'
    | 'dark'
    | 'macarons'
    | 'infographic'
    | 'shine'
    | 'roma'
    | 'matlab'
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

// Full upstream palettes, transcribed from the theme files kept in
// app/assets/echarts-theme/. Those files are UMD bundles that call
// echarts.registerTheme themselves, so we cannot import them into the SPA --
// they are reference copies, and these constants are the port. An earlier port
// took only the first six of each; ECharts cycles through the whole array once
// a chart has more series than colors, so the tail matters as soon as a panel
// draws seven or more series.

const vintageColors = [
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
] as const

const darkColors = [
  '#4992ff',
  '#7cffb2',
  '#fddd60',
  '#ff6e76',
  '#58d9f9',
  '#05c091',
  '#ff8a45',
  '#8d48e3',
  '#dd79ff'
] as const

const macaronsColors = [
  '#2ec7c9',
  '#b6a2de',
  '#5ab1ef',
  '#ffb980',
  '#d87a80',
  '#8d98b3',
  '#e5cf0d',
  '#97b552',
  '#95706d',
  '#dc69aa',
  '#07a2a4',
  '#9a7fd1',
  '#588dd5',
  '#f5994e',
  '#c05050',
  '#59678c',
  '#c9ab00',
  '#7eb00a',
  '#6f5553',
  '#c14089'
] as const

const infographicColors = [
  '#C1232B',
  '#27727B',
  '#FCCE10',
  '#E87C25',
  '#B5C334',
  '#FE8463',
  '#9BCA63',
  '#FAD860',
  '#F3A43B',
  '#60C0DD',
  '#D7504B',
  '#C6E579',
  '#F4E001',
  '#F0805A',
  '#26C0C0'
] as const

const shineColors = [
  '#c12e34',
  '#e6b600',
  '#0098d9',
  '#2b821d',
  '#005eaa',
  '#339ca8',
  '#cda819',
  '#32a487'
] as const

const romaColors = [
  '#E01F54',
  '#001852',
  '#f5e8c8',
  '#b8d2c7',
  '#c6b38e',
  '#a4d8c2',
  '#f3d999',
  '#d3758f',
  '#dcc392',
  '#2e4783',
  '#82b6e9',
  '#ff6347',
  '#a092f1',
  '#0a915d',
  '#eaf889',
  '#6699FF',
  '#ff6666',
  '#3cb371',
  '#d5b158',
  '#38b6b6'
] as const

// MATLAB's default color order from R2014b onward, as published at
// math.loyola.edu/~loberbro/matlab/html/colorsInMatlab.html. That page lists
// only 0-1 RGB triplets, so each channel here is round(v * 255) -- e.g.
// [0, 0.4470, 0.7410] -> rgb(0, 114, 189) -> #0072BD. The pre-R2014b order on
// the same page is deliberately not used: its third and fifth entries are both
// pure red, so two series would be indistinguishable.
//
// Kept separate from the extension below so the boundary is structural rather
// than a comment someone can drift past: indices 0-6 are MATLAB's, verbatim, so
// any chart with <= 7 series is colored exactly as MATLAB would color it.
const matlabBaseColors = [
  '#0072BD',
  '#D95319',
  '#EDB120',
  '#7E2F8E',
  '#77AC30',
  '#4DBEEE',
  '#A2142F'
] as const

// OURS, not MATLAB's -- MathWorks publishes no 8th, 9th or 10th entry for this
// order. Needed because assignCompareColors() withholds index 0 for the
// selected tool, so a 7-color palette could only tell 6 compared tools apart.
//
// Picked by measurement, not by eye (CIEDE2000 in CIELAB, plus Vienot-Brettel-
// Mollon dichromat simulation). Two findings shaped the result:
//
//   1. MATLAB's own closest pair is only dE00 6.5 apart under deuteranopia and
//      5.6 under protanopia. So the bar for an addition is relative -- don't be
//      closer to an existing color than MATLAB already is to itself -- not some
//      absolute ideal these seven would fail. All three clear it: the tightest
//      pair involving an addition is 9.0 (deutan) and 11.3 (protan).
//   2. Only two hue arcs are genuinely free inside MATLAB's own L*/C* envelope:
//      124-243 (the big one, 119 degrees) and 322-24. Everything between
//      #0072BD and #7E2F8E is already covered -- nothing there clears dE00 20
//      from both. Hence two colors out of the wide arc at different lightness
//      (dark forest green, mid teal) and one out of the narrow one (rose).
//
// In normal vision the closest pair drops from 24.0 to 20.8. That is not a
// regression to fix: adding three colors to an already-covered wheel must
// tighten the minimum, and dE00 20 is still a large, unambiguous difference.
// Ordered so each is far from the one before it: red -> teal -> rose -> green.
const matlabExtendedColors = [
  '#148F81',
  '#E72784',
  '#285D38'
] as const

const matlabColors = [...matlabBaseColors, ...matlabExtendedColors] as const

// The picker paints one dot per entry at a fixed 16px, so a 20-color palette
// would overflow the card. The swatch is a taste sample, not the full palette.
const swatch = (colors: readonly string[]): readonly string[] => colors.slice(0, 6)

export const ECHART_THEME_OPTIONS: readonly ThemeOption[] = [
  {
    value: 'default',
    label: 'Default',
    fileName: 'MATLAB colororder / dark.js',
    description: '밝은 화면에서는 MATLAB, 어두운 화면에서는 Dark 테마를 자동으로 사용합니다.',
    colors: ['#0072BD', '#D95319', '#EDB120', '#100C2A', '#4992ff', '#7cffb2'],
    backgroundColor: '#ffffff',
    textColor: '#262626'
  },
  {
    value: 'vintage',
    label: 'Vintage',
    fileName: 'vintage.js',
    description: '종이처럼 따뜻한 배경에 차분한 빨강, 초록, 황토색을 사용합니다.',
    colors: swatch(vintageColors),
    backgroundColor: '#fef8ef',
    textColor: '#3f3a34'
  },
  {
    value: 'dark',
    label: 'Dark',
    fileName: 'dark.js',
    description: '어두운 배경에 밝은 파랑, 초록, 노랑, 빨강을 사용합니다.',
    colors: swatch(darkColors),
    backgroundColor: '#100C2A',
    textColor: '#EEF1FA'
  },
  {
    value: 'macarons',
    label: 'Macarons',
    fileName: 'macarons.js',
    description: '밝고 부드러운 느낌의 연한 색을 사용하며, 꺾은선을 부드럽게 그립니다.',
    colors: swatch(macaronsColors),
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'infographic',
    label: 'Infographic',
    fileName: 'infographic.js',
    description: '발표용 차트에 어울리는 선명한 빨강, 청록, 노랑, 주황을 사용합니다.',
    colors: swatch(infographicColors),
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'shine',
    label: 'Shine',
    fileName: 'shine.js',
    description: '업무 보고서에 어울리는 또렷한 기본 색을 사용합니다.',
    colors: swatch(shineColors),
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'roma',
    label: 'Roma',
    fileName: 'roma.js',
    description: '짙은 빨강과 남색에 차분한 크림색과 초록을 함께 사용합니다.',
    colors: swatch(romaColors),
    backgroundColor: '#ffffff',
    textColor: '#1f2937'
  },
  {
    value: 'matlab',
    label: 'MATLAB',
    fileName: 'MATLAB colororder (R2014b+) · +3',
    description: 'MATLAB R2014b 이후의 기본 색 순서 7색에 3색을 더해 10색으로 사용합니다.',
    colors: swatch(matlabColors),
    backgroundColor: '#ffffff',
    textColor: '#262626'
  }
] as const

// Axis furniture for the two themes whose upstream file says nothing about axes
// (shine, roma). Kept from the first port so every theme draws a tinted axis
// line instead of falling back to ECharts' neutral gray. Where upstream *does*
// specify axes -- macarons, infographic, dark -- those values win over this.
const tintedAxis = (color: string) => ({
  axisLine: { lineStyle: { color } },
  splitLine: { lineStyle: { color: `${color}33` } }
})

// dark.js builds every axis from one shared factory, so the four axis types
// stay in sync. Reproduced as a function for the same reason.
const darkAxisCommon = () => ({
  axisLine: { lineStyle: { color: '#B9B8CE' } },
  splitLine: { lineStyle: { color: '#484753' } },
  splitArea: {
    areaStyle: { color: ['rgba(255,255,255,0.02)', 'rgba(255,255,255,0.05)'] }
  },
  minorSplitLine: { lineStyle: { color: '#20203B' } }
})

// Registered themes render with a transparent canvas so each chart inherits its
// card's --sk-surface. The theme's own backgroundColor (kept in the theme-picker
// swatch metadata above) otherwise painted an opaque rectangle that never
// matched the card. Only vintage and dark declare one upstream; the light
// alt-themes omit it already, and ECharts defaults to transparent.
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
    axisPointer: {
      lineStyle: { color: '#817f91' },
      crossStyle: { color: '#817f91' },
      label: { color: '#fff' }
    },
    legend: {
      textStyle: { color: '#B9B8CE' }
    },
    textStyle: {
      color: '#B9B8CE'
    },
    title: {
      textStyle: { color: '#EEF1FA' },
      subtextStyle: { color: '#B9B8CE' }
    },
    toolbox: {
      iconStyle: { borderColor: '#B9B8CE' }
    },
    dataZoom: {
      borderColor: '#71708A',
      textStyle: { color: '#B9B8CE' },
      brushStyle: { color: 'rgba(135,163,206,0.3)' },
      handleStyle: { color: '#353450', borderColor: '#C5CBE3' },
      moveHandleStyle: { color: '#B0B6C3', opacity: 0.3 },
      fillerColor: 'rgba(135,163,206,0.2)',
      emphasis: {
        handleStyle: { borderColor: '#91B7F2', color: '#4D587D' },
        moveHandleStyle: { color: '#636D9A', opacity: 0.7 }
      },
      dataBackground: {
        lineStyle: { color: '#71708A', width: 1 },
        areaStyle: { color: '#71708A' }
      },
      selectedDataBackground: {
        lineStyle: { color: '#87A3CE' },
        areaStyle: { color: '#87A3CE' }
      }
    },
    visualMap: {
      textStyle: { color: '#B9B8CE' }
    },
    timeline: {
      lineStyle: { color: '#B9B8CE' },
      label: { color: '#B9B8CE' },
      controlStyle: { color: '#B9B8CE', borderColor: '#B9B8CE' }
    },
    calendar: {
      // The one place dark.js's #100C2A survives: these are cells drawn inside
      // the chart, not the canvas we deliberately made transparent.
      itemStyle: { color: '#100C2A' },
      dayLabel: { color: '#B9B8CE' },
      monthLabel: { color: '#B9B8CE' },
      yearLabel: { color: '#B9B8CE' }
    },
    timeAxis: darkAxisCommon(),
    logAxis: darkAxisCommon(),
    valueAxis: darkAxisCommon(),
    categoryAxis: {
      ...darkAxisCommon(),
      // dark.js sets this after building the object, so the styling survives.
      splitLine: { lineStyle: { color: '#484753' }, show: false }
    },
    line: {
      symbol: 'circle'
    },
    graph: {
      color: [...darkColors]
    },
    gauge: {
      title: { color: '#B9B8CE' }
    },
    candlestick: {
      itemStyle: {
        color: '#FD1050',
        color0: '#0CF49B',
        borderColor: '#FD1050',
        borderColor0: '#0CF49B'
      }
    }
  },
  macarons: {
    color: [...macaronsColors],
    title: {
      textStyle: { fontWeight: 'normal', color: '#008acd' }
    },
    visualMap: {
      itemWidth: 15,
      color: ['#5ab1ef', '#e0ffff']
    },
    toolbox: {
      iconStyle: { borderColor: macaronsColors[0] }
    },
    tooltip: {
      borderWidth: 0,
      backgroundColor: 'rgba(50,50,50,0.5)',
      textStyle: { color: '#FFF' },
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#008acd' },
        crossStyle: { color: '#008acd' },
        shadowStyle: { color: 'rgba(200,200,200,0.2)' }
      }
    },
    dataZoom: {
      dataBackgroundColor: '#efefff',
      fillerColor: 'rgba(182,162,222,0.2)',
      handleColor: '#008acd'
    },
    grid: {
      borderColor: '#eee'
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: '#008acd' } },
      splitLine: { lineStyle: { color: ['#eee'] } }
    },
    valueAxis: {
      axisLine: { lineStyle: { color: '#008acd' } },
      splitArea: {
        show: true,
        areaStyle: { color: ['rgba(250,250,250,0.1)', 'rgba(200,200,200,0.1)'] }
      },
      splitLine: { lineStyle: { color: ['#eee'] } }
    },
    timeline: {
      lineStyle: { color: '#008acd' },
      controlStyle: { color: '#008acd', borderColor: '#008acd' },
      symbol: 'emptyCircle',
      symbolSize: 3
    },
    // Upstream macarons draws smoothed lines; that is part of its look, not an
    // accident, so it ships as-is rather than being flattened to match ours.
    line: {
      smooth: true,
      symbol: 'emptyCircle',
      symbolSize: 3
    },
    candlestick: {
      itemStyle: { color: '#d87a80', color0: '#2ec7c9' },
      lineStyle: { width: 1, color: '#d87a80', color0: '#2ec7c9' },
      areaStyle: { color: '#2ec7c9', color0: '#b6a2de' }
    },
    scatter: {
      symbol: 'circle',
      symbolSize: 4
    },
    map: {
      itemStyle: { color: '#ddd' },
      areaStyle: { color: '#fe994e' },
      label: { color: '#d87a80' }
    },
    graph: {
      itemStyle: { color: '#d87a80' },
      linkStyle: { color: '#2ec7c9' }
    },
    gauge: {
      axisLine: {
        lineStyle: {
          color: [
            [0.2, '#2ec7c9'],
            [0.8, '#5ab1ef'],
            [1, '#d87a80']
          ],
          width: 10
        }
      },
      axisTick: { splitNumber: 10, length: 15, lineStyle: { color: 'auto' } },
      splitLine: { length: 22, lineStyle: { color: 'auto' } },
      pointer: { width: 5 }
    }
  },
  infographic: {
    color: [...infographicColors],
    title: {
      textStyle: { fontWeight: 'normal', color: '#27727B' }
    },
    visualMap: {
      color: ['#C1232B', '#FCCE10']
    },
    toolbox: {
      iconStyle: { borderColor: infographicColors[0] }
    },
    tooltip: {
      backgroundColor: 'rgba(50,50,50,0.5)',
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#27727B', type: 'dashed' },
        crossStyle: { color: '#27727B' },
        shadowStyle: { color: 'rgba(200,200,200,0.3)' }
      }
    },
    dataZoom: {
      dataBackgroundColor: 'rgba(181,195,52,0.3)',
      fillerColor: 'rgba(181,195,52,0.2)',
      handleColor: '#27727B'
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: '#27727B' } },
      splitLine: { show: false }
    },
    valueAxis: {
      axisLine: { show: false },
      splitArea: { show: false },
      splitLine: { lineStyle: { color: ['#ccc'], type: 'dashed' } }
    },
    timeline: {
      itemStyle: { color: '#27727B' },
      lineStyle: { color: '#27727B' },
      controlStyle: { color: '#27727B', borderColor: '#27727B' },
      symbol: 'emptyCircle',
      symbolSize: 3
    },
    line: {
      // The nested itemStyle.lineStyle is how infographic.js writes it.
      itemStyle: { borderWidth: 2, borderColor: '#fff', lineStyle: { width: 3 } },
      emphasis: { itemStyle: { borderWidth: 0 } },
      symbol: 'circle',
      symbolSize: 3.5
    },
    candlestick: {
      itemStyle: { color: '#c1232b', color0: '#b5c334' },
      lineStyle: { width: 1, color: '#c1232b', color0: '#b5c334' },
      areaStyle: { color: '#c1232b', color0: '#27727b' }
    },
    graph: {
      itemStyle: { color: '#c1232b' },
      linkStyle: { color: '#b5c334' }
    },
    map: {
      itemStyle: { color: '#f2385a', areaColor: '#ddd', borderColor: '#eee' },
      areaStyle: { color: '#fe994e' },
      label: { color: '#c1232b' }
    },
    gauge: {
      axisLine: {
        lineStyle: {
          color: [
            [0.2, '#B5C334'],
            [0.8, '#27727B'],
            [1, '#C1232B']
          ]
        }
      },
      axisTick: { splitNumber: 2, length: 5, lineStyle: { color: '#fff' } },
      axisLabel: { color: '#fff' },
      splitLine: { length: '5%', lineStyle: { color: '#fff' } },
      title: { offsetCenter: [0, -20] }
    }
  },
  shine: {
    color: [...shineColors],
    title: {
      textStyle: { fontWeight: 'normal' }
    },
    visualMap: {
      color: ['#1790cf', '#a2d4e6']
    },
    toolbox: {
      iconStyle: { borderColor: '#06467c' }
    },
    tooltip: {
      backgroundColor: 'rgba(0,0,0,0.6)'
    },
    dataZoom: {
      dataBackgroundColor: '#dedede',
      fillerColor: 'rgba(154,217,247,0.2)',
      handleColor: '#005eaa'
    },
    timeline: {
      lineStyle: { color: '#005eaa' },
      controlStyle: { color: '#005eaa', borderColor: '#005eaa' }
    },
    // shine.js declares no axes; ours fill the gap.
    categoryAxis: tintedAxis('#06467c'),
    valueAxis: tintedAxis('#06467c'),
    line: {
      symbol: 'circle'
    },
    candlestick: {
      itemStyle: { color: '#c12e34', color0: '#2b821d' },
      lineStyle: { width: 1, color: '#c12e34', color0: '#2b821d' },
      areaStyle: { color: '#e6b600', color0: '#005eaa' }
    },
    graph: {
      itemStyle: { color: '#e6b600' },
      linkStyle: { color: '#005eaa' }
    },
    map: {
      itemStyle: { color: '#f2385a', borderColor: '#eee', areaColor: '#ddd' },
      areaStyle: { color: '#ddd' },
      label: { color: '#c12e34' }
    },
    gauge: {
      axisLine: {
        show: true,
        lineStyle: {
          color: [
            [0.2, '#2b821d'],
            [0.8, '#005eaa'],
            [1, '#c12e34']
          ],
          width: 5
        }
      },
      axisTick: { splitNumber: 10, length: 8, lineStyle: { color: 'auto' } },
      axisLabel: { color: 'auto' },
      splitLine: { length: 12, lineStyle: { color: 'auto' } },
      pointer: { length: '90%', width: 3, color: 'auto' },
      title: { color: '#333' },
      detail: { color: 'auto' }
    }
  },
  roma: {
    color: [...romaColors],
    visualMap: {
      color: ['#e01f54', '#e7dbc3'],
      textStyle: { color: '#333' }
    },
    candlestick: {
      itemStyle: { color: '#e01f54', color0: '#001852' },
      lineStyle: { width: 1, color: '#f5e8c8', color0: '#b8d2c7' },
      areaStyle: { color: '#a4d8c2', color0: '#f3d999' }
    },
    graph: {
      itemStyle: { color: '#a4d8c2' },
      linkStyle: { color: '#f3d999' }
    },
    gauge: {
      axisLine: {
        lineStyle: {
          color: [
            [0.2, '#E01F54'],
            [0.8, '#b8d2c7'],
            [1, '#001852']
          ],
          width: 8
        }
      }
    },
    // roma.js declares no title, tooltip, axes or line style; ours fill the gap.
    title: {
      textStyle: { fontWeight: 'normal' }
    },
    tooltip: {
      backgroundColor: 'rgba(50,50,50,0.72)',
      textStyle: { color: '#fff' }
    },
    categoryAxis: tintedAxis('#001852'),
    valueAxis: tintedAxis('#001852'),
    line: {
      symbol: 'circle'
    }
  },
  matlab: {
    color: [...matlabColors],
    title: {
      textStyle: { fontWeight: 'normal', color: '#262626' }
    },
    // MATLAB's default colormap is parula, which runs dark blue -> yellow. A
    // theme's visualMap.color lists the high stop first, as the bundled themes do.
    visualMap: {
      color: ['#f9fb0e', '#352a87']
    },
    toolbox: {
      iconStyle: { borderColor: '#262626' }
    },
    tooltip: {
      backgroundColor: 'rgba(50,50,50,0.72)',
      textStyle: { color: '#fff' },
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#262626' },
        crossStyle: { color: '#262626' }
      }
    },
    dataZoom: {
      dataBackgroundColor: '#e6e6e6',
      fillerColor: 'rgba(0,114,189,0.2)',
      handleColor: '#0072BD'
    },
    // MATLAB axes are a near-black box with ticks; the grid is 15%-alpha black
    // over white, which lands on roughly #d9d9d9.
    categoryAxis: {
      axisLine: { lineStyle: { color: '#262626' } },
      axisTick: { lineStyle: { color: '#262626' } },
      splitLine: { show: false }
    },
    valueAxis: {
      axisLine: { lineStyle: { color: '#262626' } },
      axisTick: { lineStyle: { color: '#262626' } },
      splitLine: { lineStyle: { color: ['#d9d9d9'] } }
    },
    // MATLAB draws bare lines with no markers, but our tooltips hover-target
    // the symbol, so keep a small circle instead of symbol: 'none'.
    line: {
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2 }
    },
    scatter: {
      symbol: 'circle',
      symbolSize: 6
    },
    graph: {
      color: [...matlabColors]
    },
    candlestick: {
      itemStyle: {
        color: '#A2142F',
        color0: '#0072BD',
        borderColor: '#A2142F',
        borderColor0: '#0072BD'
      }
    },
    gauge: {
      axisLine: {
        lineStyle: {
          color: [
            [0.2, '#77AC30'],
            [0.8, '#0072BD'],
            [1, '#A2142F']
          ],
          width: 8
        }
      }
    }
  }
}

const themePalettes: Record<EchartThemeName, readonly string[]> = {
  vintage: vintageColors,
  dark: darkColors,
  macarons: macaronsColors,
  infographic: infographicColors,
  shine: shineColors,
  roma: romaColors,
  matlab: matlabColors
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
  roma: '#ffffff',
  matlab: '#ffffff'
}

export const getEchartThemeBackground = (name: EchartThemeName): string =>
  themeBackgrounds[name]

let registered = false

export const isEchartThemeSelection = (value: unknown): value is EchartThemeSelection =>
  ECHART_THEME_OPTIONS.some(option => option.value === value)

// 'default' is the only selection that is not itself a theme: it defers to the
// color mode. Light resolves to MATLAB -- the project default, chosen because
// its color order is what the metrology plots it sits next to already use.
// Dark cannot: these themes draw on a transparent canvas that inherits the card
// surface, and MATLAB's furniture (#262626 axes, ticks and title) assumes a
// white one, so on a dark card it would be black on black.
export const resolveEchartThemeName = (
  selection: EchartThemeSelection,
  colorMode: string
): EchartThemeName => {
  if (selection !== 'default') return selection
  return colorMode === 'dark' ? 'dark' : 'matlab'
}

export const registerEchartsThemes = (echarts: EchartsModule) => {
  if (registered) return
  Object.entries(themes).forEach(([name, theme]) => {
    echarts.registerTheme(name, theme)
  })
  registered = true
}
