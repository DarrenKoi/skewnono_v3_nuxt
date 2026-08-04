import * as echarts from 'echarts'
import type { ComputedRef, Ref } from 'vue'
import type { ECharts, EChartsOption } from 'echarts'
import { registerEchartsThemes } from '~/utils/echartsThemes'
import { chartExportFilename } from '~/utils/chartExport'
import { withPreservedZoom, type ZoomWindow } from '~/utils/chartZoom'

export interface GridClickDetail {
  // Axis values under the cursor: a fractional category position for a category
  // axis (round it for the index), the data value for a value/time axis.
  x: number
  y: number
  // Which grid was hit — matters for multi-grid charts (small multiples, matrix
  // cells) where the same x means a different series per pane.
  gridIndex: number
  // Data units per screen pixel on each axis, for weighing x against y.
  dataPerPixelX: number
  dataPerPixelY: number
}

interface UseEchartOptions {
  // Fired when a series element (e.g. a bar) is clicked. Receives the
  // x-axis category for category-bucketed series — for our charts that's
  // the lot_cd, since xAxis.data is built from lot labels.
  onClick?: (name: string) => void
  // Fired when the user clicks anywhere inside a plot area — including empty
  // space no series covers. `onClick` only fires on a hit against a series
  // element, so it never fires for curves drawn with `showSymbol: false`
  // (nothing to hit) — use this instead for "pick the x position I clicked".
  // Receives the x-axis value under the cursor: a fractional category position
  // for a category axis (round it to get the index), the data value for a
  // value/time axis. Both callbacks fire if both are supplied.
  //
  // Also receives the index of the grid that was hit. That matters for
  // multi-grid charts — small multiples, matrix cells — where the same x value
  // means a different series depending on which pane was clicked. Single-grid
  // callers can ignore it.
  //
  // `y` is the value-axis counterpart of `x`. Comparing the two directly is a
  // mistake — they carry different units (nm against seconds, say) — so the
  // detail also reports how much data one pixel is worth on each axis. Dividing
  // by those converts a data-space gap into the on-screen gap the reader
  // actually judged, which is what `nearestPoint` in utils/chartNearest.ts
  // wants. See that file for why pixels are the only fair space to pick in.
  onGridClick?: (detail: GridClickDetail) => void
  // Fired when a series element is clicked, carrying the datum's index within
  // its series. `onClick` forwards the category NAME, which is not an identity
  // for charts whose labels are display strings rather than ids — the caller
  // maps the index back to its own data array. All supplied callbacks fire.
  onDataIndex?: (dataIndex: number, seriesIndex: number) => void
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

  const { themeId, surface } = useEchartsTheme()

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

  // Same 'click' source as bindClick, bound separately so a chart can ask for
  // the index without also being handed a name it has no use for.
  const bindDataIndex = () => {
    const callback = options.onDataIndex
    if (!chart || !callback) return
    chart.on('click', (params) => {
      if (params.componentType !== 'series') return
      const hit = params as { dataIndex?: number, seriesIndex?: number }
      if (typeof hit.dataIndex !== 'number') return
      callback(hit.dataIndex, hit.seriesIndex ?? 0)
    })
  }

  // Series clicks come from ECharts' own dispatcher, which requires a hit on a
  // rendered element. Grid clicks have to come from the underlying ZRender
  // canvas instead, then be converted from pixels back to axis space.
  const bindGridClick = () => {
    const callback = options.onGridClick
    if (!chart || !callback) return
    chart.getZr().on('click', (event) => {
      if (!chart) return
      const point: [number, number] = [event.offsetX, event.offsetY]
      // A chart may stack several grids (e.g. one panel per value type), so
      // find the one the click landed in and convert against its axes. Read the
      // grid count off the option we were handed, not chart.getOption() — that
      // deep-clones the whole option (axis category arrays and all series data
      // included) on every click just to read an array length.
      const grids = (optionRef.value as { grid?: unknown[] }).grid
      const gridCount = Array.isArray(grids) ? Math.max(grids.length, 1) : 1
      for (let gridIndex = 0; gridIndex < gridCount; gridIndex++) {
        if (!chart.containPixel({ gridIndex }, point)) continue
        const at = chart.convertFromPixel({ gridIndex }, point)
        if (!Array.isArray(at)) return
        const x = Number(at[0])
        const y = Number(at[1])
        if (!Number.isFinite(x)) return
        // One pixel right and down, converted the same way: the difference is
        // what a pixel is worth in data units on each axis. Two conversions
        // instead of one per candidate point, and it costs nothing on a chart
        // with no y component to weigh (the caller simply ignores it).
        const stepped = chart.convertFromPixel({ gridIndex }, [point[0] + 1, point[1] + 1])
        const at1 = Array.isArray(stepped) ? stepped : [x, y]
        callback({
          x,
          y,
          gridIndex,
          dataPerPixelX: Math.abs(Number(at1[0]) - x) || 1,
          dataPerPixelY: Math.abs(Number(at1[1]) - y) || 1
        })
        return
      }
    })
  }

  const downloadChartImage = () => {
    if (!chart) return
    const url = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: surface.value.surface
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
    chart = echarts.init(elRef.value, themeId.value)
    chart.setOption(optionRef.value)
    bindClick()
    bindDataIndex()
    bindGridClick()
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
  watch(themeId, () => {
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
