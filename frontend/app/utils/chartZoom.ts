// Carry a chart's live dataZoom window across an option rebuild.
//
// `useEchart` applies every option change with `notMerge: true`, which tears
// the chart down and rebuilds it from the option object. That discards all
// runtime state — including how far the user has zoomed — and re-applies the
// option's literal `start`/`end` (or ECharts' 0~100 default when the option
// omits them). The visible symptom: clicking a trend point restyles that
// symbol, which produces a new option, which snaps the view back to the full
// time range just as the reader was inspecting a detail.
//
// `withPreservedZoom` patches the live windows into a *copy* of the incoming
// option. Copying matters: the option comes from a `computed`, so writing into
// it would poison the cached value and make the preserved window the chart's
// new permanent default.

export interface ZoomWindow {
  start?: number
  end?: number
}

// dataZoom entries are index-matched between the live chart and the incoming
// option. Every chart in this app declares dataZoom as a stable array literal,
// so index i is the same component before and after; an entry with no live
// counterpart (a chart that grew a zoom component) keeps its declared window.
export const withPreservedZoom = <T extends { dataZoom?: unknown }>(
  next: T,
  live: ZoomWindow[] | undefined
): T => {
  const declared = next.dataZoom
  if (!Array.isArray(declared) || declared.length === 0) return next
  if (!Array.isArray(live) || live.length === 0) return next

  let changed = false
  const merged = declared.map((zoom, i) => {
    const window = live[i]
    if (!window || !Number.isFinite(window.start) || !Number.isFinite(window.end)) return zoom
    changed = true
    return { ...(zoom as Record<string, unknown>), start: window.start, end: window.end }
  })

  return changed ? { ...next, dataZoom: merged } : next
}
