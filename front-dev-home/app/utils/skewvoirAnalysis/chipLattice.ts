// Die-lattice placement for the SEM gallery: every gallery item carries a
// chip_number "col,row" (the die index the wafer map plots), so the gallery can
// lay thumbnails out on the same lattice instead of a reading-order grid.
//
// Pure and geometry-free on purpose, and COMPACTED: only the die columns and
// rows that carry at least one chip get a line, labelled with their real index.
// A recipe measures a handful of dies spread over a 26×33 wafer, so a to-scale
// grid was ~800 empty cells around 22 pictures (2026-08-27 screenshot); the
// compacted table keeps the relative order (left→right, top→bottom = +row up,
// matching the wafer map's y-up axis) and the gaps show in the labels.
//
// Runs under raw `node --test` — sibling imports carry an explicit `.ts`.
import { parseChipXY } from '../waferChip.ts'

export interface LatticeCell {
  col: number // 1-based CSS grid column
  row: number // 1-based CSS grid row (top = largest chip row)
}

export interface ChipLattice {
  colLabels: number[] // chip col index per grid column, left → right
  rowLabels: number[] // chip row index per grid row, top → bottom
  cells: Map<string, LatticeCell> // by chip string, placeable chips only
}

/** Compacted lattice of the given chips. Chips that do not parse as "col,row"
 * are left out of `cells` — the caller lists them separately rather than
 * piling them onto a guessed die. */
export const buildChipLattice = (chips: Iterable<string>): ChipLattice => {
  const parsed = new Map<string, [number, number]>()
  const colSet = new Set<number>()
  const rowSet = new Set<number>()
  for (const chip of chips) {
    const xy = parseChipXY(chip)
    if (!xy) continue
    parsed.set(chip, xy)
    colSet.add(xy[0])
    rowSet.add(xy[1])
  }
  const colLabels = [...colSet].sort((a, b) => a - b)
  const rowLabels = [...rowSet].sort((a, b) => b - a)
  const colAt = new Map(colLabels.map((c, i) => [c, i + 1]))
  const rowAt = new Map(rowLabels.map((r, i) => [r, i + 1]))
  const cells = new Map<string, LatticeCell>()
  for (const [chip, [x, y]] of parsed) cells.set(chip, { col: colAt.get(x)!, row: rowAt.get(y)! })
  return { colLabels, rowLabels, cells }
}
