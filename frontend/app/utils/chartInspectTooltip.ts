import { escapeHtml } from './html.ts'

// A chart tooltip carrying a button ("이 시점 측정 recipe 보기") the reader can
// move into and press, so opening a detail is their decision, not a side effect
// of hovering or clicking the plot. Shared by the Sharpness trend and the FDC
// charts. The host element listens for clicks and reads the key back with
// `inspectKeyOf`; ECharts renders the tooltip inside that element.

// Offset-less KST wall clock (or any string key) goes out on the button.
export const inspectButtonHtml = (key: string, label: string): string =>
  `<button type="button" data-inspect-key="${escapeHtml(key)}" style="margin-top:6px;padding:2px 8px;border-radius:6px;border:1px solid var(--sk-border);background:var(--sk-surface);color:var(--sk-ink);font-size:11px;cursor:pointer">${escapeHtml(label)}</button>`

export const inspectKeyOf = (event: Event): string | undefined =>
  (event.target as HTMLElement | null)?.closest<HTMLElement>('[data-inspect-key]')?.dataset.inspectKey

type TooltipParam = { name?: string } | undefined

// ECharts re-positions on every pointer move, so the spot is pinned per point:
// otherwise the tooltip stays 6 px ahead of a slowly moving pointer and the
// button is never reached (Codex review). Held only while the pointer travels
// from where it opened straight down into the tooltip (inside its width, below
// the opening point); the same point hovered again from anywhere else re-opens
// it under the pointer. One instance per chart - it keeps the pin between calls.
export const pinnedTooltipPosition = () => {
  let pinned: { key: string, at: number[], fromX: number, fromY: number } | null = null
  return (point: number[], params: unknown, _dom: unknown, _rect: unknown, size: { contentSize: number[] }): number[] => {
    const key = (Array.isArray(params) ? params[0] as TooltipParam : params as TooltipParam)?.name ?? ''
    const [x, y] = [point[0]!, point[1]!]
    const [w, h] = [size.contentSize[0]!, size.contentSize[1]!]
    const travelling = pinned?.key === key && Math.abs(x - pinned.fromX) <= w / 2
      && y >= pinned.fromY - 2 && y <= pinned.at[1]! + h
    if (!travelling) pinned = { key, at: [x - w / 2, y + 6], fromX: x, fromY: y }
    return pinned!.at
  }
}

// The tooltip settings every inspect tooltip shares; the caller adds trigger
// and formatter. Build it once per chart (setup), not inside an option computed.
export const inspectTooltipBase = () => ({
  enterable: true,
  confine: true,
  hideDelay: 400,
  position: pinnedTooltipPosition()
})
