import * as echarts from 'echarts'
import type { ComputedRef, Ref } from 'vue'
import type { ECharts, EChartsOption } from 'echarts'
import { registerEchartsThemes, getEchartThemeBackground } from '~/utils/echartsThemes'
import { chartExportFilename } from '~/utils/chartExport'
import { withPreservedZoom, type ZoomWindow } from '~/utils/chartZoom'

interface UseEchartOptions {
  // Fired when a series element (e.g. a bar) is clicked. Receives the
  // x-axis category for category-bucketed series — for our charts that's
  // the lot_cd, since xAxis.data is built from lot labels.
  onClick?: (name: string) => void
  // Preferred base name for the downloaded PNG (before the date stamp). Falls
  // back to the chart's title text, then 'chart'.
  exportName?: string
  // Opt out of the hover download button — for charts whose own corner controls
  // would collide with the overlay (e.g. skewvoir/WaferMap.vue).
  disableDownload?: boolean
}

const DOWNLOAD_STYLE_ID = 'sk-chart-dl-style'

// Injected once for the whole app. The button is invisible until its chart host
// is hovered or the button itself is keyboard-focused.
const ensureDownloadStyles = () => {
  if (!import.meta.client) return
  if (document.getElementById(DOWNLOAD_STYLE_ID)) return
  const style = document.createElement('style')
  style.id = DOWNLOAD_STYLE_ID
  style.textContent = `
.sk-chart-host { position: relative; }
.sk-chart-dl-btn {
  position: absolute; top: 6px; right: 6px; z-index: 5;
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; padding: 0; margin: 0;
  border: none; border-radius: 6px;
  background: rgba(127, 127, 127, 0.14); color: currentColor;
  cursor: pointer; opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease;
}
.sk-chart-host:hover .sk-chart-dl-btn,
.sk-chart-dl-btn:focus-visible { opacity: 1; }
.sk-chart-dl-btn:hover { background: rgba(127, 127, 127, 0.28); }
.sk-chart-dl-btn svg { width: 15px; height: 15px; display: block; }
`
  document.head.appendChild(style)
}

const DOWNLOAD_ICON_SVG = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
</svg>`

export const useEchart = (
  elRef: Ref<HTMLDivElement | null>,
  optionRef: ComputedRef<EChartsOption>,
  options: UseEchartOptions = {}
) => {
  registerEchartsThemes(echarts)

  const { resolvedThemeName } = useEchartsTheme()

  let chart: ECharts | null = null
  let resizeHandler: (() => void) | null = null
  let dlButton: HTMLButtonElement | null = null

  const bindClick = () => {
    const callback = options.onClick
    if (!chart || !callback) return
    chart.on('click', (params) => {
      if (params.componentType !== 'series') return
      const name = (params as { name?: string }).name
      if (typeof name === 'string' && name.length > 0) callback(name)
    })
  }

  const downloadChartImage = () => {
    if (!chart) return
    const url = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: getEchartThemeBackground(resolvedThemeName.value)
    })
    const title = (optionRef.value.title as { text?: string } | undefined)?.text
    const filename = chartExportFilename(options.exportName, title, new Date())
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const mountDownloadButton = () => {
    if (options.disableDownload || !import.meta.client) return
    if (dlButton || !elRef.value) return
    ensureDownloadStyles()
    elRef.value.classList.add('sk-chart-host')
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'sk-chart-dl-btn'
    button.title = 'Download chart image'
    button.setAttribute('aria-label', 'Download chart image')
    button.innerHTML = DOWNLOAD_ICON_SVG
    button.addEventListener('click', downloadChartImage)
    elRef.value.appendChild(button)
    dlButton = button
  }

  const unmountDownloadButton = () => {
    if (!dlButton) return
    dlButton.removeEventListener('click', downloadChartImage)
    dlButton.remove()
    dlButton = null
  }

  const ensureChart = () => {
    if (chart || !elRef.value) return
    chart = echarts.init(elRef.value, resolvedThemeName.value)
    chart.setOption(optionRef.value)
    bindClick()
    mountDownloadButton()
    if (!resizeHandler) {
      resizeHandler = () => chart?.resize()
      window.addEventListener('resize', resizeHandler)
    }
  }

  onMounted(() => {
    ensureChart()
  })

  // Containers may be inside a v-if and toggle on/off. When the previous
  // element unmounts, dispose the instance bound to it (and drop its detached
  // button); when a fresh element mounts, init against the new node.
  watch(elRef, (next, prev) => {
    if (prev && prev !== next) {
      chart?.dispose()
      chart = null
      unmountDownloadButton()
    }
    if (next) ensureChart()
  })

  // Rebuilding with `notMerge` is what keeps stale series/axes from lingering,
  // but it also drops the user's zoom window — and a new option arrives on any
  // change, including a click that merely restyles the selected symbol. Carry
  // the live window over so an interaction can't yank the view back to the
  // full range under the reader.
  watch(optionRef, (next) => {
    if (!chart) return
    const live = (chart.getOption() as { dataZoom?: ZoomWindow[] }).dataZoom
    chart.setOption(withPreservedZoom(next, live), true)
  })

  // ECharts binds a theme at init time; swapping themes requires dispose +
  // re-init on the same DOM node. dispose() clears the host div's children,
  // detaching the download button, so it must be torn down and re-mounted
  // rather than assumed to persist.
  watch(resolvedThemeName, () => {
    if (!elRef.value) return
    chart?.dispose()
    chart = null
    unmountDownloadButton()
    ensureChart()
  })

  onBeforeUnmount(() => {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    unmountDownloadButton()
    chart?.dispose()
    chart = null
  })
}
