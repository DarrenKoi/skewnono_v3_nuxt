// Options every image-URL builder accepts. Named once because the rule that
// governs the flag is one rule, not one per builder: DISPLAY urls (an <img>, a
// blob for the viewer) pass `preview: true` and get a browser-renderable
// rendition — TIFF converts to WebP server-side (2026-08-08,
// msr_image/preview.py), anything already renderable passes through
// byte-identical. DOWNLOAD links omit it, because 원본 다운로드 promises the
// untouched file. It was three anonymous inline `{ preview?: boolean }` copies
// until 2026-08-09; an anonymous shape cannot carry that rule with it.
export interface ImagePreviewOptions {
  preview?: boolean
}

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
