// SEM tools store JPEG previews alongside TIFF originals (office-confirmed
// 2026-07-24), and the backend lists/serves both. Chromium cannot decode TIFF
// in an <img> or blob URL, so every image consumer must branch to a download
// fallback for these instead of attempting a render that always errors.
export const isTiffName = (name: string | null | undefined): boolean =>
  typeof name === 'string' && /\.tiff?$/i.test(name)

// Short label for one of a measurement point's several images. HV-SEM suffixes
// the shared stem per targeting sub-position (S04_M0004-01MP-U.jpeg → "U",
// user-confirmed 2026-08-08); a name with no such suffix falls back to its
// 1-based position. Chrome, not data — it names which sub-image is showing.
export const imageVariantLabel = (name: string, index: number): string => {
  const stem = name.replace(/\.[^.]+$/, '')
  const match = /-([A-Za-z0-9]{1,3})$/.exec(stem)
  return match?.[1] ?? String(index + 1)
}
