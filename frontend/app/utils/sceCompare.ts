// Pure: SCE settings comparison (selected eqp vs in-fab siblings) + the
// Coefficients[0..359] curve series. §7.5.
import { mean as meanOf, median } from './stats.ts'

const SECTIONS = ['SemCond', 'ImgCond', 'SCEParam'] as const

export const SCE_FLEET_CONSTANT_FIELDS = new Set([
  'SemCond.SemCond_Detector', 'SemCond.SemCond_Ip', 'SemCond.SemCond_IpMode', 'SemCond.SemCond_Optics',
  'ImgCond.ImgCond_Pixel',
  ...['CycleUpperTh', 'CycleLowerTh', 'SmoothRadius', 'SmoothTheta', 'FitRangeSt', 'FitRangeEd', 'CorrCoefLimit']
    .map(key => `SCEParam.SCEParam_${key}`)
])

const leafValue = (v: unknown): string => {
  if (Array.isArray(v)) return v.map(String).join(',')
  if (v === null || v === undefined) return ''
  return String(v)
}

export const flattenSettings = (node: Record<string, unknown>): Record<string, string> => {
  const out: Record<string, string> = {}
  for (const section of SECTIONS) {
    const sub = node[section]
    if (!sub || typeof sub !== 'object' || Array.isArray(sub)) continue
    for (const [k, v] of Object.entries(sub as Record<string, unknown>)) {
      out[`${section}.${k}`] = leafValue(v)
    }
  }
  return out
}

export interface SceCompareRow {
  path: string
  selected: string
  siblings: Record<string, string>
  differs: boolean
}

// `compareIds` (when given) scopes both the emitted `siblings` map and the
// `differs` flag to just those tools, so the flag reflects exactly the columns
// on screen. Omit it to compare against every in-fab sibling (default).
// The compare table's one FileInfo row: no single reference tool exists per
// fab, but tools group by a shared base file (office 확인 2026-09-28).
// SharpCharFile is left out — it differs per tool and per re-tune.
const compareFlat = (node: Record<string, unknown>): Record<string, string> => {
  const fileInfo = node.FileInfo
  const base: Record<string, string> = fileInfo && typeof fileInfo === 'object' && !Array.isArray(fileInfo)
    ? { 'FileInfo.BaseSharpCharFile': leafValue((fileInfo as Record<string, unknown>).BaseSharpCharFile) }
    : {}
  return { ...base, ...flattenSettings(node) }
}

export const compareSettings = (
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string,
  compareIds?: string[]
): SceCompareRow[] => {
  const selectedFlat = compareFlat(settings[selectedEqp] ?? {})
  const allSiblings = Object.keys(settings).filter(id => id !== selectedEqp)
  const siblingIds = (compareIds ? allSiblings.filter(id => compareIds.includes(id)) : allSiblings).sort()
  const siblingFlats = siblingIds.map(id => [id, compareFlat(settings[id] ?? {})] as const)

  const paths = new Set<string>(Object.keys(selectedFlat))
  for (const [, flat] of siblingFlats) for (const p of Object.keys(flat)) paths.add(p)

  return [...paths].sort().map((path): SceCompareRow => {
    const selected = selectedFlat[path] ?? ''
    const siblings: Record<string, string> = {}
    let differs = false
    for (const [id, flat] of siblingFlats) {
      const val = flat[path] ?? ''
      siblings[id] = val
      if (val !== selected) differs = true
    }
    return { path, selected, siblings, differs }
  }).filter(row => !SCE_FLEET_CONSTANT_FIELDS.has(row.path) || row.differs)
}

// values[0] reduced to scalars: the mean and the amplitudes of harmonics 1-4
// (a direct DFT at those four orders), plus the share of the variance they
// carry. Office 확인 2026-09-28: that share is 82-97 % for v0 (so the scalars
// stand in for the curve) but only 64-91 % for v1 (which stays a curve).
export const sceHarmonics = (values: number[]): { mean: number, amp: number[], share: number } => {
  if (values.length === 0 || values.some(v => !Number.isFinite(v))) {
    return { mean: Number.NaN, amp: [Number.NaN, Number.NaN, Number.NaN, Number.NaN], share: Number.NaN }
  }
  const n = values.length
  const mean = meanOf(values)
  const variance = values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / n
  const amp = [1, 2, 3, 4].map((k) => {
    let re = 0
    let im = 0
    for (let i = 0; i < n; i++) {
      const angle = 2 * Math.PI * k * i / n
      re += values[i]! * Math.cos(angle)
      im -= values[i]! * Math.sin(angle)
    }
    return 2 * Math.hypot(re, im) / n
  })
  return { mean, amp, share: variance === 0 ? 0 : amp.reduce((sum, a) => sum + a ** 2 / 2, 0) / variance }
}

// Every tool of the fab (the settings map IS the fab), selected pinned first,
// plus a fab-median row.
export const sceHarmonicRows = (settings: Record<string, Record<string, unknown>>, selectedEqp: string) => {
  const ids = Object.keys(settings)
    .sort((a, b) => Number(b === selectedEqp) - Number(a === selectedEqp) || a.localeCompare(b))
  const rows = ids.map(id => ({ id, ...sceHarmonics(coefficientSeries(settings[id]).v0) }))
  const center = (values: number[]) => median(values.filter(Number.isFinite))
  return [...rows, {
    id: 'fab 중앙값',
    mean: center(rows.map(r => r.mean)),
    amp: [0, 1, 2, 3].map(i => center(rows.map(r => r.amp[i]!))),
    share: center(rows.map(r => r.share))
  }]
}

export const coefficientSeries = (
  eqpSettings: Record<string, unknown> | undefined
): { v0: number[], v1: number[] } => {
  const v0 = Array.from({ length: 360 }, () => NaN)
  const v1 = Array.from({ length: 360 }, () => NaN)
  const coeffs = eqpSettings?.Coefficients
  if (Array.isArray(coeffs)) {
    for (const c of coeffs) {
      const idx = Number((c as Record<string, unknown>)?.index)
      const vals = (c as Record<string, unknown>)?.values
      if (!Number.isInteger(idx) || idx < 0 || idx > 359 || !Array.isArray(vals)) continue
      v0[idx] = Number(vals[0])
      v1[idx] = Number(vals[1])
    }
  }
  return { v0, v1 }
}
