// Skewvoir Time-Series — tool (eqp_id) identity colors, shared by the
// multi-measurement trend chart AND the Sequence Trend overlay so the same tool
// never wears two colors on one screen.
//
// Pure and framework-free (mirrors the rest of utils/skewvoirAnalysis) so the
// ranking rule runs under raw `node --test`.
import { SK_SITE, SK_SITE_OVERFLOW, SK_STATE } from '../chartPalette.ts'

/**
 * SK_SITE entries a tool must never wear, because the charts that color by tool
 * draw severity onto the SAME marks — a tool whose identity color IS a severity
 * color makes the two legends interchangeable at a glance.
 *
 * SK_SITE's docstring already states the rule ("an identity halo must never read
 * as severity"); nothing enforced it, and the palette breaks it three times:
 *
 *  - `#3E8E5E` green — byte-identical to SK_STATE.ok (RadiusChart draws it).
 *  - `#C98A2E` amber — byte-identical to SK_STATE.warn (the 주의 swatch).
 *  - `#B0413A` brick — not an SK_STATE value, but a hair off SK_STATE.bad
 *    `#C4453B`, which is the 이상 dot. Excluded by hex rather than by reference
 *    for that reason: equality cannot catch a near miss, and this one sits
 *    beside a red dot often enough to matter.
 *
 * The first two are written as SK_STATE references so the filter follows any
 * future retone of the semantic palette instead of silently going stale.
 */
const SEVERITY_ADJACENT: readonly string[] = [SK_STATE.ok, SK_STATE.warn, '#B0413A']

/** The severity-safe subset of SK_SITE, in SK_SITE's own order — the colors a
 *  tool may actually be assigned. Derived rather than hand-copied so a palette
 *  edit cannot reintroduce a collision without also editing SEVERITY_ADJACENT. */
export const TOOL_PALETTE: readonly string[] = SK_SITE.filter(c => !SEVERITY_ADJACENT.includes(c))

/** Tools ranked by how many items they contributed get an identity color; the
 *  rest collapse into one labelled 기타 bucket. A shared gray silently spread
 *  across many tools would read as one series.
 *
 *  Derived from TOOL_PALETTE, so the cap is a consequence of the disjointness
 *  rule rather than a number somebody has to keep in sync with it. */
export const TOOL_COLOR_LIMIT = TOOL_PALETTE.length
export const TOOL_OTHER_LABEL = '기타'

/** eqp_id → color, ranked by contribution count (desc), ties by id. Pass one
 *  entry per DRAWN item (one per measurement) — a hidden measurement must not
 *  spend an identity color. Tools past TOOL_PALETTE share the overflow
 *  neutral. */
export const rankToolColors = (eqpIds: readonly string[]): Map<string, string> => {
  const counts = new Map<string, number>()
  for (const id of eqpIds) counts.set(id, (counts.get(id) ?? 0) + 1)
  const ranked = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([id]) => id)
  const map = new Map<string, string>()
  ranked.forEach((id, i) => {
    map.set(id, i < TOOL_COLOR_LIMIT ? TOOL_PALETTE[i]! : SK_SITE_OVERFLOW)
  })
  return map
}

export interface ToolLegendChip {
  label: string
  color: string
}

/** Named tools keep their own chip; the overflow becomes ONE `기타 (n)` chip,
 *  so the strip never claims a gray line belongs to a particular tool. */
export const toolLegendChips = (toolColor: ReadonlyMap<string, string>): ToolLegendChip[] => {
  const chips: ToolLegendChip[] = []
  let overflow = 0
  for (const [id, color] of toolColor) {
    if (color === SK_SITE_OVERFLOW) overflow++
    else chips.push({ label: id, color })
  }
  if (overflow) chips.push({ label: `${TOOL_OTHER_LABEL} (${overflow})`, color: SK_SITE_OVERFLOW })
  return chips
}
