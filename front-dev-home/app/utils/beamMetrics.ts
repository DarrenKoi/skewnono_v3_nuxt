// Pure helpers that derive BSM panel selectors straight off the faithful
// beam_shape docs — no per-key frontend edits (spec §7.1). A doc key whose
// value is a length-16 numeric array is a radar metric; a numeric scalar is a
// trend metric. Adding a future key to the mock surfaces it automatically.

export interface BeamMetricOption { key: string; label: string }

// Keys that look like profile arrays but are NOT selectable metrics.
const PROFILE_DENY = new Set(['degree', 'Reso EB Focus Range'])

// Prettify known keys; unknown keys fall through verbatim (source spellings
// like "Ellipicity" / "Apature angle factor" are intentional).
export const BEAM_LABELS: Record<string, string> = {
  'Reso EB': 'Reso EB',
  'Reso Detector': 'Reso Detector',
  'Noise': 'Noise',
  'Focus offset': 'Focus offset',
  'Apature angle factor': 'Apature angle factor',
  'Reso EB Focus': 'Reso EB Focus',
  'Ellipicity': 'Ellipicity',
  'Major Axis': 'Major Axis',
  'Minor Axis': 'Minor Axis',
  'Tilt': 'Tilt',
  'X range': 'X range',
  'Y range': 'Y range',
  'Area': 'Area',
  'Ave. Reso Detector': 'Ave. Reso Detector',
  'Ave. Noise': 'Ave. Noise',
  'Ave. Apature angle factor': 'Ave. Apature angle factor'
}

export const prettyLabel = (key: string): string => BEAM_LABELS[key] ?? key

const toNum = (v: unknown): number => {
  if (typeof v === 'number') return v
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v)
    return Number.isFinite(n) ? n : NaN
  }
  return NaN
}

const isLen16NumberArray = (v: unknown): v is unknown[] =>
  Array.isArray(v) && v.length === 16 && v.every(x => Number.isFinite(toNum(x)))

const isScalarNumber = (v: unknown): boolean =>
  (typeof v === 'number' || typeof v === 'string') && Number.isFinite(toNum(v))

const option = (key: string): BeamMetricOption => ({ key, label: prettyLabel(key) })

// Use the first doc that actually owns each key to classify it.
const classify = (docs: Record<string, unknown>[]): { profile: Set<string>; scalar: Set<string> } => {
  const profile = new Set<string>()
  const scalar = new Set<string>()
  for (const d of docs) {
    for (const [k, v] of Object.entries(d)) {
      if (profile.has(k) || scalar.has(k)) continue
      if (!PROFILE_DENY.has(k) && isLen16NumberArray(v)) profile.add(k)
      else if (!Array.isArray(v) && isScalarNumber(v)) scalar.add(k)
    }
  }
  return { profile, scalar }
}

export const profileMetricKeys = (docs: Record<string, unknown>[]): BeamMetricOption[] =>
  [...classify(docs).profile].sort().map(option)

export const scalarMetricKeys = (docs: Record<string, unknown>[]): BeamMetricOption[] =>
  [...classify(docs).scalar].sort().map(option)

export const radialRange = (
  docs: Record<string, unknown>[],
  key: string
): { min: number; max: number } => {
  let lo = Infinity
  let hi = -Infinity
  for (const d of docs) {
    const v = d[key]
    if (!Array.isArray(v)) continue
    for (const cell of v) {
      const n = toNum(cell)
      if (!Number.isFinite(n)) continue
      if (n < lo) lo = n
      if (n > hi) hi = n
    }
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return { min: 0, max: 1 }
  const span = hi - lo
  const pad = Math.max(span * 0.05, 0.001)
  const round6 = (n: number) => Number(n.toFixed(6))
  return { min: round6(lo - pad), max: round6(hi + pad) }
}

export const degreeLabels = (docs: Record<string, unknown>[]): string[] => {
  const first = docs.find(d => Array.isArray(d.degree))
  if (first && Array.isArray(first.degree)) return (first.degree as unknown[]).map(String)
  return Array.from({ length: 16 }, (_, i) => String(i * 22.5))
}
