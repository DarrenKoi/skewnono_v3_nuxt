// Pure: turn the mdc settings dict-of-dict into a tools×beam_condition matrix
// and a per-cell deviation-from-selected scaling for the skew heat-table (§7.4).

export interface MdcMatrix {
  tools: string[]
  conditions: string[]
  values: (number | null)[][]
}

const toNum = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

export const buildMdcMatrix = (
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string
): MdcMatrix => {
  const allTools = Object.keys(settings)
  // Selected eqp first (if present), then the rest in stable sorted order.
  const rest = allTools.filter(t => t !== selectedEqp).sort()
  const tools = settings[selectedEqp] ? [selectedEqp, ...rest] : rest

  const condSet = new Set<string>()
  for (const t of tools) for (const c of Object.keys(settings[t] ?? {})) condSet.add(c)
  const conditions = [...condSet].sort()

  const values = tools.map(t =>
    conditions.map(c => toNum(settings[t]?.[c]))
  )

  return { tools, conditions, values }
}

export const cellDeviation = (matrix: MdcMatrix, row: number, col: number): number => {
  const v = matrix.values[row]?.[col]
  const baseline = matrix.values[0]?.[col] // row 0 = selected tool
  if (v === null || v === undefined || baseline === null || baseline === undefined) return 0

  // Normalize against the column's largest abs deviation so colors are
  // comparable within a column.
  let maxAbs = 0
  for (let r = 0; r < matrix.values.length; r++) {
    const cell = matrix.values[r]?.[col]
    if (cell === null || cell === undefined) continue
    maxAbs = Math.max(maxAbs, Math.abs(cell - baseline))
  }
  if (maxAbs === 0) return 0
  return (v - baseline) / maxAbs
}
