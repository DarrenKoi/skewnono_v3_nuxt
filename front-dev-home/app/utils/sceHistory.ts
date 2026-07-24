// Pure: per-date SCE history docs (bidaily MinIO archive) → numeric trend
// series. A doc is one collection-date snapshot: { date, FileInfo, SemCond,
// ImgCond, SCEParam, Coefficients } — the same block shape `settings` holds
// per eqp, plus `date`.

export interface SceTrendPoint { ts: string, key: string, value: number }
export interface SceTrendKey { block: string, key: string, label: string }

// Blocks holding trendable settings, in display order. FileInfo is excluded —
// it carries file paths, not measurements.
const TREND_BLOCKS = ['SCEParam', 'SemCond', 'ImgCond'] as const

const toNum = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

// A field is trendable if it parses as a number, or is a non-empty list whose
// first element does — ImgCond stores its values boxed (['1024','1024'], ['-2']).
const fieldNum = (v: unknown): number | null => {
  if (Array.isArray(v)) return v.length > 0 ? toNum(v[0]) : null
  return toNum(v)
}

const blockOf = (doc: Record<string, unknown>, name: string): Record<string, unknown> => {
  const sub = doc[name]
  return sub && typeof sub === 'object' && !Array.isArray(sub)
    ? (sub as Record<string, unknown>)
    : {}
}

export const sceParamLabel = (key: string): string =>
  key.replace(/^(SCEParam|SemCond|ImgCond)_/, '')

// Union of numeric field keys across the window (a mid-window settings-file
// swap may add/remove keys), each tagged with its block so the chip strip can
// group them. Ordered by block, then key.
export const sceTrendKeys = (docs: Record<string, unknown>[]): SceTrendKey[] => {
  const found = new Map<string, string>()
  for (const doc of docs) {
    for (const block of TREND_BLOCKS) {
      for (const [k, v] of Object.entries(blockOf(doc, block))) {
        if (!found.has(k) && fieldNum(v) !== null) found.set(k, block)
      }
    }
  }
  const rank = (b: string) => TREND_BLOCKS.indexOf(b as (typeof TREND_BLOCKS)[number])
  return [...found.entries()]
    .map(([key, block]) => ({ block, key, label: sceParamLabel(key) }))
    .sort((a, b) => rank(a.block) - rank(b.block) || a.key.localeCompare(b.key))
}

// One point per collection date carrying a numeric value for `key`; the date
// doubles as the point key (BsmTrendChart contract, same as MDC). Field names
// are block-prefixed, so a key resolves in exactly one block.
export const sceParamSeries = (
  docs: Record<string, unknown>[],
  key: string
): SceTrendPoint[] => {
  const out: SceTrendPoint[] = []
  for (const doc of docs) {
    const ts = typeof doc.date === 'string' ? doc.date : ''
    if (!ts) continue
    let value: number | null = null
    for (const block of TREND_BLOCKS) {
      const sub = blockOf(doc, block)
      if (key in sub) {
        value = fieldNum(sub[key])
        break
      }
    }
    if (value !== null) out.push({ ts, key: ts, value })
  }
  return out
}

// Collection dates present in the window, in doc order (asc). Docs without a
// usable `date` are dropped — a snapshot with no date can neither be labelled
// nor picked, so it must not occupy a slot in the date picker.
export const sceDocDates = (docs: Record<string, unknown>[]): string[] =>
  docs.map(d => (typeof d.date === 'string' ? d.date : '')).filter(Boolean)

// The `count` most recent dates, still in ascending order. Used as the default
// selection for the evolution overlay: the whole bidaily window drawn at once
// is an unreadable thicket, so it opens on the newest few and the user widens
// from there.
export const sceLatestDates = (dates: string[], count: number): string[] =>
  count <= 0 ? [] : dates.slice(Math.max(0, dates.length - count))

export interface SceCoeffRevision {
  /** First collection date this curve appeared on — the revision's identity. */
  date: string
  /** Last collection date it was still in force. */
  through: string
  /** Every collection date the curve was read back unchanged, ascending. */
  dates: string[]
}

// Coefficients equality between two docs. Compares structurally and bails on
// the first difference rather than fingerprinting: a curve is 360 entries, and
// only ADJACENT docs are ever compared, so the common "it changed" case costs
// one comparison instead of building two ~8KB keys. It also cannot collide the
// way a hash can — two genuinely different re-tunes must never merge.
const sameCoefficients = (a: unknown, b: unknown): boolean => {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    const ea = a[i] as { index?: unknown, values?: unknown }
    const eb = b[i] as { index?: unknown, values?: unknown }
    if (ea?.index !== eb?.index) return false
    const va = ea?.values
    const vb = eb?.values
    if (!Array.isArray(va) || !Array.isArray(vb) || va.length !== vb.length) return false
    for (let j = 0; j < va.length; j++) if (va[j] !== vb[j]) return false
  }
  return true
}

// Collapse consecutive collection dates carrying the SAME curve into one
// revision. SCE is re-tuned at PM, not per collection, so a 2-week window is
// typically one or two distinct curves read back a dozen times — plotting all
// of them draws the same line on top of itself and tells the reader nothing.
//
// Only CONSECUTIVE runs merge. A curve that reverts to an earlier value is a
// new revision, not a re-join: "it went back" is a real event and folding it
// into the older entry would hide it.
export const sceCoeffRevisions = (docs: Record<string, unknown>[]): SceCoeffRevision[] => {
  const out: SceCoeffRevision[] = []
  let prev: Record<string, unknown> | null = null
  for (const doc of docs) {
    const date = typeof doc.date === 'string' ? doc.date : ''
    if (!date) continue
    const last = out[out.length - 1]
    if (last && prev && sameCoefficients(prev.Coefficients, doc.Coefficients)) {
      last.dates.push(date)
      last.through = date
    } else {
      out.push({ date, through: date, dates: [date] })
    }
    prev = doc
  }
  return out
}

// Picker label. A revision read back once is just its date; a run shows the
// span and how many collections confirmed it — that count IS the "이 값이
// 유지된 기간" signal. The end date drops its year: same-year spans are the
// norm and the repetition costs width in a narrow menu.
export const sceRevisionLabel = (rev: SceCoeffRevision): string => {
  if (rev.dates.length <= 1) return rev.date
  const sameYear = rev.through.slice(0, 4) === rev.date.slice(0, 4)
  return `${rev.date} ~ ${sameYear ? rev.through.slice(5) : rev.through} · ${rev.dates.length}회`
}

// values[0] / values[1] at a single Coefficients index across the window —
// "how did this one point of the curve move?". Reads only the target entry, so
// no 360-array is built per doc.
export const sceCoeffIndexSeries = (
  docs: Record<string, unknown>[],
  index: number
): { v0: SceTrendPoint[], v1: SceTrendPoint[] } => {
  const v0: SceTrendPoint[] = []
  const v1: SceTrendPoint[] = []
  for (const doc of docs) {
    const ts = typeof doc.date === 'string' ? doc.date : ''
    if (!ts) continue
    const coeffs = doc.Coefficients
    if (!Array.isArray(coeffs)) continue
    for (const entry of coeffs) {
      const c = entry as Record<string, unknown>
      if (Number(c?.index) !== index) continue
      const vals = c?.values
      if (Array.isArray(vals)) {
        const a = toNum(vals[0])
        const b = toNum(vals[1])
        if (a !== null) v0.push({ ts, key: ts, value: a })
        if (b !== null) v1.push({ ts, key: ts, value: b })
      }
      break
    }
  }
  return { v0, v1 }
}
