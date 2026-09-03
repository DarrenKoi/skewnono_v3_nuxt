// Where the tool put its marks on an image, read off the image's cond.txt rows.
//
// A Hitachi cond.txt carries a `!Cursor_info` line (spelled `!Cursor_inf` on
// some tools) of comma-separated ints in a frame TEN times the `Pixel` size
// (user-confirmed 2026-09-03; rules of record in
// back_dev_home/_core/cond_cursor.py and docs/datatables/hitachi/recipe_idp.txt):
//   [4],[5]   crosshair — the align / measurement point; -1,-1 = none drawn
//   [6..9]    white box (left, top, right, bottom) — the recipe's unique area
//
// Everything leaves here as FRACTIONS of the frame (0..1). The overlay is an
// SVG whose viewBox is the Pixel size and whose preserveAspectRatio mirrors the
// <img>'s object-fit, so a fraction is right at any rendered size or zoom, and
// even on a copy the tool saved at a different resolution.

export interface CondRowLike {
  key: string
  value: string
}

export interface CondMarks {
  pixel: [number, number]
  crosshair: [number, number] | null
  box: [number, number, number, number] | null
}

export const CURSOR_OVERSAMPLE = 10

const toInt = (token: string): number | null => {
  const n = Number.parseInt(token.trim(), 10)
  return Number.isNaN(n) ? null : n
}

const present = (values: (number | null)[], idx: number[]) =>
  idx.every(i => i < values.length && values[i] !== null && values[i] !== -1)

export const condMarks = (
  rows: readonly CondRowLike[] | null | undefined
): CondMarks | null => {
  if (!rows) return null
  const value = (test: (key: string) => boolean) =>
    rows.find(row => test(row.key.replace(/^!/, '').toLowerCase()))?.value
  const pixelRaw = value(key => key === 'pixel')
  const cursorRaw = value(key => key.startsWith('cursor_inf'))
  if (!pixelRaw || !cursorRaw) return null

  const px = pixelRaw.split(',').map(toInt)
  const [pw, ph] = [px[0] ?? 0, px[1] ?? 0]
  if (px.length < 2 || pw <= 0 || ph <= 0) return null
  const w = pw * CURSOR_OVERSAMPLE
  const h = ph * CURSOR_OVERSAMPLE

  const v = cursorRaw.split(',').map(toInt)
  const crosshair = present(v, [4, 5]) ? [v[4]! / w, v[5]! / h] as [number, number] : null
  const box = present(v, [6, 7, 8, 9])
    ? [v[6]! / w, v[7]! / h, v[8]! / w, v[9]! / h] as [number, number, number, number]
    : null
  if (!crosshair && !box) return null
  return { pixel: [pw, ph], crosshair, box }
}
