// Pure: SCE settings comparison (selected eqp vs in-fab siblings) + the
// Coefficients[0..359] curve series. §7.5.

const SECTIONS = ['SemCond', 'ImgCond', 'SCEParam'] as const

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

export const compareSettings = (
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string
): SceCompareRow[] => {
  const selectedFlat = flattenSettings(settings[selectedEqp] ?? {})
  const siblingIds = Object.keys(settings).filter(id => id !== selectedEqp).sort()
  const siblingFlats = siblingIds.map(id => [id, flattenSettings(settings[id] ?? {})] as const)

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
  })
}

export const coefficientSeries = (
  eqpSettings: Record<string, unknown> | undefined
): { v0: number[]; v1: number[] } => {
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
