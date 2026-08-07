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
  // Fired as the pointer moves inside a plot area, with the same converted
  // detail `onGridClick` receives. Return the datum the pointer is nearest —
  // normally by running the SAME `nearestPoint` pick the click handler uses —
  // and the tooltip is shown for it; return null and it is hidden.
  //
  // This is what gives an item-triggered tooltip a pick radius. `trigger:
  // 'item'` alone only fires on a literal hit against the drawn symbol, so on a
  // chart with small dots the tooltip is unreachable long before the click is.
  // Supplying this makes both use one radius, so a near-miss that selects a
  // point also explains it.
  //
  // Coordinates in, coordinates out: the ECharts instance stays private to this
  // composable, and the dispatch is done here.
  onGridHover?: (detail: GridClickDetail) => { seriesIndex: number, dataIndex: number } | null
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
  let sizeObserver: ResizeObserver | null = null
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

  // Pixel → axis space, against whichever grid the pointer is over. Shared by
  // the click and hover bindings: they differ only in which ZRender event wakes
  // them and what they do with the result, and a second copy of this conversion
  // is exactly how a chart ends up with a click radius that disagrees with its
  // hover radius. Returns null when the pointer is outside every grid.
  const gridDetailAt = (offsetX: number, offsetY: number): GridClickDetail | null => {
    if (!chart) return null
    const point: [number, number] = [offsetX, offsetY]
    // A chart may stack several grids (e.g. one panel per value type), so
    // find the one the pointer landed in and convert against its axes. Read the
    // grid count off the option we were handed, not chart.getOption() — that
    // deep-clones the whole option (axis category arrays and all series data
    // included) on every event just to read an array length.
    const grids = (optionRef.value as { grid?: unknown[] }).grid
    const gridCount = Array.isArray(grids) ? Math.max(grids.length, 1) : 1
    for (let gridIndex = 0; gridIndex < gridCount; gridIndex++) {
      if (!chart.containPixel({ gridIndex }, point)) continue
      const at = chart.convertFromPixel({ gridIndex }, point)
      if (!Array.isArray(at)) return null
      const x = Number(at[0])
      const y = Number(at[1])
      if (!Number.isFinite(x)) return null
      // One pixel right and down, converted the same way: the difference is
      // what a pixel is worth in data units on each axis. Two conversions
      // instead of one per candidate point, and it costs nothing on a chart
      // with no y component to weigh (the caller simply ignores it).
      const stepped = chart.convertFromPixel({ gridIndex }, [point[0] + 1, point[1] + 1])
      const at1 = Array.isArray(stepped) ? stepped : [x, y]
      return {
        x,
        y,
        gridIndex,
        dataPerPixelX: Math.abs(Number(at1[0]) - x) || 1,
        dataPerPixelY: Math.abs(Number(at1[1]) - y) || 1
      }
    }
    return null
  }

  // Series clicks come from ECharts' own dispatcher, which requires a hit on a
  // rendered element. Grid clicks have to come from the underlying ZRender
  // canvas instead, then be converted from pixels back to axis space.
  const bindGridClick = () => {
    const callback = options.onGridClick
    if (!chart || !callback) return
    chart.getZr().on('click', (event) => {
      const detail = gridDetailAt(event.offsetX, event.offsetY)
      if (detail) callback(detail)
    })
  }

  // Hover counterpart to bindGridClick, and the reason it exists: an
  // item-triggered tooltip only fires on a literal hit against the rendered
  // symbol, so a chart drawing 4–10px dots had a ~44px CLICK target (via
  // onGridClick + nearestPoint) and a 4–10px HOVER target for the tooltip. The
  // near-miss selected the point and showed nothing, which reads as the chart
  // half-responding. Routing the tooltip through the caller's own pick makes one
  // radius govern both.
  //
  // The caller returns coordinates rather than receiving the ECharts instance:
  // this composable hands out converted values and keeps `chart` private, and a
  // getter added for one component would be reachable by every future one.
  const bindGridHover = () => {
    const callback = options.onGridHover
    if (!chart || !callback) return

    // mousemove fires per pixel and the caller's pick is O(points), so coalesce
    // to one resolve per frame. Only the latest position matters — an older
    // pending one would show a tooltip the pointer has already left.
    let pending: [number, number] | null = null
    let frame = 0
    let shown: { seriesIndex: number, dataIndex: number } | null = null

    const resolve = () => {
      frame = 0
      const at = pending
      pending = null
      if (!chart || !at) return
      const detail = gridDetailAt(at[0], at[1])
      const hit = detail ? callback(detail) : null
      if (!hit) {
        // Only hide a tip this binding put up. Blanket-hiding on every empty
        // frame would fight any tooltip ECharts raised on its own.
        if (shown) {
          chart.dispatchAction({ type: 'hideTip' })
          shown = null
        }
        return
      }
      // Re-dispatching the same target every frame makes the tooltip flicker,
      // so only act when the pick actually moves to another datum.
      if (shown && shown.seriesIndex === hit.seriesIndex && shown.dataIndex === hit.dataIndex) return
      shown = hit
      chart.dispatchAction({ type: 'showTip', seriesIndex: hit.seriesIndex, dataIndex: hit.dataIndex })
    }

    chart.getZr().on('mousemove', (event) => {
      pending = [event.offsetX, event.offsetY]
      if (!frame) frame = requestAnimationFrame(resolve)
    })

    // Leaving the canvas entirely never produces a mousemove inside a grid, so
    // without this the last tooltip would stay pinned after the pointer is gone.
    chart.getZr().on('globalout', () => {
      pending = null
      if (frame) {
        cancelAnimationFrame(frame)
        frame = 0
      }
      if (shown && chart) {
        chart.dispatchAction({ type: 'hideTip' })
        shown = null
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
    bindGridHover()
    mountDownloadButton()
    // Observe the HOST, not the window: a window listener misses hosts whose
    // size is driven by their own props — ParamMatrix's height is a function of
    // its row count, so 평가 불가 숨기기 shrinks the div while the canvas kept
    // its init-time size and overflowed the panel. Element resize also covers
    // every window resize that matters (the hosts are width-bound to layout).
    if (!sizeObserver) {
      sizeObserver = new ResizeObserver(() => chart?.resize())
    }
    sizeObserver.disconnect()
    sizeObserver.observe(elRef.value)
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
    sizeObserver?.disconnect()
    sizeObserver = null
    unmountDownloadButton()
    chart?.dispose()
    chart = null
  })
}
