// Skewvoir Time-Series — tool (eqp_id) identity colors, shared by the
// multi-measurement trend chart AND the Sequence Trend overlay so the same tool
// never wears two colors on one screen.
//
// Pure and framework-free (mirrors the rest of utils/skewvoirAnalysis) so the
// ranking rule runs under raw `node --test`.
import { SK_SITE, SK_SITE_OVERFLOW } from '../chartPalette.ts'

/** Tools ranked by how many items they contributed get an identity color; the
 *  rest collapse into one labelled 기타 bucket. A shared gray silently spread
 *  across many tools would read as one series. */
export const TOOL_COLOR_LIMIT = 9
export const TOOL_OTHER_LABEL = '기타'

/** eqp_id → color, ranked by contribution count (desc), ties by id. Pass one
 *  entry per DRAWN item (one per measurement) — a hidden measurement must not
 *  spend an identity color. Tools past the palette cap share the overflow
 *  neutral. */
export const rankToolColors = (eqpIds: readonly string[]): Map<string, string> => {
  const counts = new Map<string, number>()
  for (const id of eqpIds) counts.set(id, (counts.get(id) ?? 0) + 1)
  const ranked = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([id]) => id)
  const map = new Map<string, string>()
  ranked.forEach((id, i) => {
    map.set(id, i < TOOL_COLOR_LIMIT ? SK_SITE[i]! : SK_SITE_OVERFLOW)
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
