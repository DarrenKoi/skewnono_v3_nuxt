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
//
// PER-NAME, so it cannot see siblings: one point can list the SAME sub-position
// under two extensions (JPEG preview + TIFF original, user-confirmed
// 2026-08-24), and this function labels both "U". Anything rendering a label
// NEXT TO its siblings must use imageVariantLabels below, which disambiguates
// within the list — two chips both reading "U" are unclickable-apart.
export const imageVariantLabel = (name: string, index: number): string => {
  const stem = name.replace(/\.[^.]+$/, '')
  const match = /-([A-Za-z0-9]{1,3})$/.exec(stem)
  return match?.[1] ?? String(index + 1)
}

// The label separator. Middle dot rather than an ASCII character because the
// base label is alphanumeric ([A-Za-z0-9]{1,3} or a position number) and the
// extension tag is an uppercased extension — neither can contain '·', so
// variantLabelBase can split unambiguously.
const LABEL_SEP = '·'

// Extension → display tag. Spelling variants collapse (jpeg/jpg → JPG,
// tif/tiff → TIF, any case — office listings carry .TIF uppercase,
// user-reported 2026-08-24) because the tag answers "which rendition is this",
// not "what is the exact filename".
const EXT_TAGS: Record<string, string> = { jpeg: 'JPG', jpg: 'JPG', tif: 'TIF', tiff: 'TIF' }

const extTag = (name: string): string => {
  const ext = /\.([^.]+)$/.exec(name)?.[1]
  if (!ext) return ''
  return EXT_TAGS[ext.toLowerCase()] ?? ext.toUpperCase()
}

/**
 * Labels for ALL of a point's images, pairwise distinct. The per-name label
 * alone collides when one sub-position is listed under several extensions
 * (-U.jpeg + -U.TIF → "U", "U"), which made the second chip unselectable: the
 * variant memory stores the LABEL, and resolving a duplicated label always
 * found the first file. Uniqueness here is what makes that round-trip total.
 *
 * A label grows only as far as needed: unique base stays bare ("U"), an
 * extension collision appends the rendition tag ("U·JPG" / "U·TIF"), and a
 * still-colliding pair (same suffix, same rendition — e.g. case-variant
 * duplicates) numbers its occurrences.
 */
export const imageVariantLabels = (names: readonly string[]): string[] => {
  const bases = names.map((name, index) => imageVariantLabel(name, index))
  const baseCounts = new Map<string, number>()
  for (const base of bases) baseCounts.set(base, (baseCounts.get(base) ?? 0) + 1)
  const tagged = bases.map((base, index) => {
    if ((baseCounts.get(base) ?? 0) <= 1) return base
    const tag = extTag(names[index]!)
    return tag ? `${base}${LABEL_SEP}${tag}` : base
  })
  const seen = new Map<string, number>()
  return tagged.map((label) => {
    const occurrence = (seen.get(label) ?? 0) + 1
    seen.set(label, occurrence)
    return occurrence === 1 ? label : `${label}${LABEL_SEP}${occurrence}`
  })
}

/** The sub-position half of a (possibly disambiguated) variant label:
 * "U·TIF" → "U", "U" → "U". What the variant memory falls back to when a
 * remembered label's exact rendition is absent from the current point. */
export const variantLabelBase = (label: string): string => {
  const sep = label.indexOf(LABEL_SEP)
  return sep < 0 ? label : label.slice(0, sep)
}
