// Parse a wafer `chip_number` string ("x, y") into numeric grid coordinates.
// Returns null for anything that isn't two finite numbers — note Number.isNaN
// alone is NOT enough here: a single-token string makes y `undefined`, and
// Number.isNaN(undefined) is false, so we check both length and finiteness.
export const parseChipXY = (chip: string): [number, number] | null => {
  const parts = chip.split(',')
  if (parts.length !== 2) return null
  const x = Number(parts[0]!.trim())
  const y = Number(parts[1]!.trim())
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  return [x, y]
}
