// Pure: shape the mdc `docs` history (long-format {timestamp, beam_condition,
// mdc_value} records) into per-family 0°/90° series for the MDC 시계열 view.
// Families pair `<family>_0Deg` / `<family>_90Deg`; a condition without a
// degree suffix (e.g. "Valley") is its own single-axis family.

export interface MdcHistoryPoint {
  ts: string
  value: number
}

export interface MdcFamily {
  key: string
  zero: MdcHistoryPoint[]
  ninety: MdcHistoryPoint[]
}

const DEG_RE = /_(0|90)Deg$/

const toNum = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}

export const buildMdcFamilies = (docs: Record<string, unknown>[]): MdcFamily[] => {
  // Map preserves first-appearance order → the mock's 800V-first ordering
  // becomes the chip order without extra sorting rules.
  const byKey = new Map<string, MdcFamily>()
  for (const d of docs) {
    const cond = String(d.beam_condition ?? '')
    const ts = String(d.timestamp ?? '')
    const value = toNum(d.mdc_value)
    if (!cond || !ts || !Number.isFinite(value)) continue
    const m = cond.match(DEG_RE)
    const key = m ? cond.slice(0, -m[0].length) : cond
    let fam = byKey.get(key)
    if (!fam) {
      fam = { key, zero: [], ninety: [] }
      byKey.set(key, fam)
    }
    ;(m?.[1] === '90' ? fam.ninety : fam.zero).push({ ts, value })
  }
  const byTs = (a: MdcHistoryPoint, b: MdcHistoryPoint) => a.ts.localeCompare(b.ts)
  for (const fam of byKey.values()) {
    fam.zero.sort(byTs)
    fam.ninety.sort(byTs)
  }
  return [...byKey.values()]
}

// (0°, 90°) pairs matched by timestamp — a recalibration event refreshes both
// axes at once, so timestamps align; unmatched events are skipped.
export const trajectoryPoints = (
  family: MdcFamily
): { ts: string, x: number, y: number }[] => {
  const ninetyByTs = new Map(family.ninety.map(p => [p.ts, p.value]))
  const out: { ts: string, x: number, y: number }[] = []
  for (const p of family.zero) {
    const y = ninetyByTs.get(p.ts)
    if (y !== undefined) out.push({ ts: p.ts, x: p.value, y })
  }
  return out
}
