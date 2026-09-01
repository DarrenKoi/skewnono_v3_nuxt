// The reviewer's sub-image pick, remembered per recipe + parameter.
//
// A measurement point shot as several files (HV-SEM -U/-T/-M/-L) offers a
// variant chip bar. Until 2026-08-11 every host reset that pick to the first
// image on each point change, so a reviewer working a wafer at the -M depth
// re-clicked M on every single site. This module is the memory that ends that.
//
// WHY A LABEL AND NOT AN INDEX (the load-bearing decision):
//   The stored value is the chip LABEL ('M', or 'M·TIF' where one sub-position
//   is listed under several extensions), resolved back to a position on each
//   point. An index cannot be reused across points because the suffix set is
//   not fixed — a point whose -T shot is absent renders U/M/L, where index 2
//   is 'L' while the reviewer meant 'M'. Storing the index would silently show
//   the wrong depth; storing the label either finds the same depth or falls
//   back to the first image, and never misattributes.
//
// WHY recipe + parameter IS THE KEY:
//   Which suffixes exist is a property of the recipe's targeting setup for a
//   given parameter (user-confirmed 2026-08-11), so that pair is the narrowest
//   scope over which one pick stays meaningful. A parameter name alone would
//   share one memory between two recipes that shoot different sub-positions.
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import { imageVariantLabels, variantLabelBase } from '../imageKind.ts'

/** recipe+parameter key → the suffix label the reviewer last picked there. */
export type VariantMemory = Record<string, string>

/** Upper bound on remembered pairs. The map is persisted, so without a cap it
 * would grow for the life of the browser profile — one entry per recipe ×
 * parameter a reviewer has ever touched. Eviction is least-recently-picked,
 * which is exactly the entry least likely to be wanted again. */
export const MAX_REMEMBERED_VARIANTS = 200

// ASCII unit separator, written as an escape so the source stays plain text:
// legal in neither a recipe name nor a parameter name, so
// ('A', 'B|C') and ('A|B', 'C') cannot collide into one bucket.
const SEP = '\u001f'

interface VariantRecipeSource {
  msr: string
  exe_detail_info: { recipe_name: string }
}

/** Prefer the loaded file because shared links need no history-row hit. Reject
 * a stale file retained while another MSR loads, then fall back to the row. */
export const resolveVariantMemoryRecipe = (
  focusMsr: string | null,
  file: VariantRecipeSource | null,
  rowRecipe: string | null | undefined
): string | null =>
  (file?.msr === focusMsr ? file.exe_detail_info.recipe_name : null) || rowRecipe || null

/** The memory key for a recipe/parameter pair, or null when either half is not
 * resolved yet. An empty parameter is the valid unnamed settling MP. */
export const variantMemoryKey = (
  recipe: string | null | undefined,
  parameter: string | null | undefined
): string | null => (recipe && parameter != null ? `${recipe}${SEP}${parameter}` : null)

/**
 * Where the remembered label sits among THIS point's image names, or 0 when
 * there is no memory or this point carries nothing like it.
 *
 * Pure and index-free by design: callers derive the index on every render
 * instead of storing one, so a point swap re-resolves rather than going stale.
 *
 * Resolution is against the LIST-AWARE labels (imageVariantLabels), never the
 * per-name label: a point listing one sub-position under two extensions
 * (-U.jpeg + -U.TIF, user-confirmed 2026-08-24) has duplicated per-name labels,
 * and matching those always answered the first file — the chip for the second
 * could be clicked but never stayed selected. An exact miss falls back to the
 * sub-position half ("U·TIF" finds a lone "U", and a pre-disambiguation stored
 * "U" finds "U·JPG"), so a pick keeps meaning "this depth" across points whose
 * rendition sets differ.
 */
export const rememberedVariantIndex = (
  names: string[],
  label: string | null | undefined
): number => {
  if (!label || names.length === 0) return 0
  const labels = imageVariantLabels(names)
  const exact = labels.indexOf(label)
  if (exact >= 0) return exact
  const base = variantLabelBase(label)
  const found = labels.findIndex(candidate => variantLabelBase(candidate) === base)
  return found < 0 ? 0 : found
}

/**
 * Record a pick, returning a NEW map (the persisted ref only writes through on
 * reference change). Re-picking an existing key refreshes its recency: the key
 * is deleted and re-inserted so JS string-key insertion order stays a true
 * least-recently-picked order for the cap below.
 */
export const rememberVariant = (
  memory: VariantMemory,
  key: string | null,
  label: string
): VariantMemory => {
  if (!key) return memory
  // Rebuilt without the key rather than spread-then-delete: re-inserting last
  // is what makes insertion order a recency order for the cap.
  const next: VariantMemory = {}
  for (const [existing, value] of Object.entries(memory)) {
    if (existing !== key) next[existing] = value
  }
  next[key] = label
  return capVariantMemory(next)
}

/** Validate a localStorage payload into a VariantMemory. Never throws — an
 * unreadable or foreign payload degrades to "no memory", which is just the
 * pre-2026-08-11 behaviour. */
export const normalizeVariantMemory = (parsed: unknown): VariantMemory => {
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
  const out: VariantMemory = {}
  for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
    if (typeof value === 'string' && value !== '') out[key] = value
  }
  return capVariantMemory(out)
}

// Keep the most recent MAX_REMEMBERED_VARIANTS entries. Object.entries returns
// string keys in insertion order, so the tail is the most recently picked.
const capVariantMemory = (memory: VariantMemory): VariantMemory => {
  const entries = Object.entries(memory)
  if (entries.length <= MAX_REMEMBERED_VARIANTS) return memory
  return Object.fromEntries(entries.slice(entries.length - MAX_REMEMBERED_VARIANTS))
}
