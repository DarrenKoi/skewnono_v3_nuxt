// Pure: per-date SCE history docs (bidaily MinIO archive) → numeric trend
// series. A doc is one collection-date snapshot: { date, FileInfo, SemCond,
// ImgCond, SCEParam, Coefficients } — the same block shape `settings` holds
// per eqp, plus `date`.

export interface SceTrendPoint { ts: string, key: string, value: number }

const toNum = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

const paramBlock = (doc: Record<string, unknown>): Record<string, unknown> => {
  const sub = doc.SCEParam
  return sub && typeof sub === 'object' && !Array.isArray(sub)
    ? (sub as Record<string, unknown>)
    : {}
}

// Union of SCEParam keys across the window (a mid-window settings-file swap
// may add/remove keys), stripped of the `SCEParam_` prefix for chip labels.
export const sceParamKeys = (docs: Record<string, unknown>[]): string[] => {
  const keys = new Set<string>()
  for (const doc of docs) {
    for (const k of Object.keys(paramBlock(doc))) keys.add(k)
  }
  return [...keys].sort()
}

export const sceParamLabel = (key: string): string => key.replace(/^SCEParam_/, '')

// One point per collection date carrying a numeric value for `key`; the date
// doubles as the point key (BsmTrendChart contract, same as MDC).
export const sceParamSeries = (
  docs: Record<string, unknown>[],
  key: string
): SceTrendPoint[] => {
  const out: SceTrendPoint[] = []
  for (const doc of docs) {
    const ts = typeof doc.date === 'string' ? doc.date : ''
    const value = toNum(paramBlock(doc)[key])
    if (ts && value !== null) out.push({ ts, key: ts, value })
  }
  return out
}
