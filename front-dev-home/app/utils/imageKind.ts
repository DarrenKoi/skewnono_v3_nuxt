// SEM tools store JPEG previews alongside TIFF originals (office-confirmed
// 2026-07-24), and the backend lists/serves both. Chromium cannot decode TIFF
// in an <img> or blob URL, so every image consumer must branch to a download
// fallback for these instead of attempting a render that always errors.
export const isTiffName = (name: string | null | undefined): boolean =>
  typeof name === 'string' && /\.tiff?$/i.test(name)
