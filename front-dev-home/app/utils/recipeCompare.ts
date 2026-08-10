import type { CompareRecipe, CompareIdpFields, CompareParameter } from '~/composables/useRecipeCompareApi'
import type { ParamDetail, SettingBlock, SettingRow } from '../composables/useRecipeParamDetail.ts'
import { IMAGE_SLOTS, formatSettingValue, type ImageSlotKey } from './recipeView.ts'
import { imageVariantLabel } from './imageKind.ts'
import { recipePairKey } from './recipePair.ts'
import { createWorkbook, writeWorkbook, type WorkbookSheet } from './xlsx.ts'

// Relative `.ts` specifiers, not the `~` alias: `node --test` cannot resolve
// `~`, but it does resolve these, and `nuxt typecheck` accepts them (verified
// 2026-07-29 — an earlier comment here claimed otherwise and had grown three
// copies of the slot table on that false premise). Type-only imports are erased
// before Node sees them; `IMAGE_SLOTS` and `formatSettingValue` are real value
// imports and run fine under both.

export const COMPARE_SLOTS = IMAGE_SLOTS

/**
 * One compared recipe, reduced to what identifies it: the (recipe_id,
 * fab_name) pair. Every compare surface — the parameter selector's columns,
 * the matrix's headers, the chip row, the workbook's column labels — needs
 * exactly this and nothing else, and each had re-declared it inline until
 * 2026-08-09.
 *
 * ON THE NAME. `recipe_id` is canonical: it is the catalog's `"class/recipe"`
 * string, which is simultaneously the registry hash field and meas_hist's
 * `full_name` (recipe_search/MIGRATION.md). The compare REQUEST body spells
 * the same string `recipe_name` (`CompareRecipeRef`) — a wire-contract name,
 * not a second concept, translated in exactly one place
 * (`recipesForCompare`). Inside the frontend, say `recipe_id`.
 */
export interface CompareColumn {
  recipe_id: string
  fab_name: string
}

/**
 * Does this compared set cross fab boundaries?
 *
 * The answer decides whether a bare recipe name is unambiguous. Not cosmetic:
 * the same name can legitimately exist once per fab, so two identically
 * labeled columns over genuinely different data is the exact
 * silent-wrong-answer the compare screens must not produce.
 *
 * One predicate because three variants of it — two inline `new Set(...)`
 * counts and one inside `compareRecipeLabels` — can disagree, and then the fab
 * chip shows in one compare view and not another for the same data.
 */
export const spansFabs = (columns: Array<{ fab_name: string }>): boolean =>
  new Set(columns.map(c => c.fab_name)).size > 1

/** Structurally the compare screen's view of one parameter's settings. */
export type CompareSettingBlock = SettingBlock
export type CompareParamDetail = ParamDetail

/**
 * Which parsed file a slot's settings come from.
 *
 * `img_meas2` IS the AMP file and `img_add2` resolves (PR -> EN) to the AF/PR
 * condition; the other three name images, whose settings are the beam
 * condition in their `.{name}/cond.txt` sidecar.
 */
export function blockForSlot(
  detail: CompareParamDetail | null | undefined,
  slot: ImageSlotKey
): CompareSettingBlock | null {
  if (!detail) return null
  if (slot === 'img_meas2') return detail.amp
  if (slot === 'img_add2') return detail.af_pr
  const matches = detail.images.filter(image => image.slot === slot)
  if (matches.length <= 1) return matches[0]?.cond ?? null
  // HV-SEM: one slot, several stem-suffixed files (2026-08-08), each with its
  // own cond sidecar. Merged into ONE block with the variant label as each
  // row's `section`, so the (section, key) row identity the compare screen
  // already uses (settingRowId) keeps the U/T/M/L passes apart — a bare
  // `find()` here compared only the first file and silently ignored the rest.
  const rows: SettingRow[] = []
  const sources: string[] = []
  matches.forEach((image, index) => {
    if (!image.cond) return
    sources.push(image.cond.source)
    const label = imageVariantLabel(image.name, index)
    for (const row of image.cond.rows) rows.push({ ...row, section: row.section ?? label })
  })
  if (!rows.length) return null
  return { source: sources.join(' · '), rows }
}

export const GROUPING_DEFAULT_THRESHOLD = 8
export const OUTLIER_SHARE = 0.25

export type Coverage = 'all' | 'partial' | 'unique'
export type CoverageFilter = 'all' | 'common' | 'partial' | 'unique'

export interface OverlapRow {
  parameter: string
  /** `recipePairKey(fab_name, recipe_id)` pairs, not bare recipe ids. */
  presentIn: string[]
  count: number
  total: number
  coverage: Coverage
}

export function classifyCoverage(count: number, total: number): Coverage {
  if (total > 0 && count === total) return 'all'
  if (count <= 1) return 'unique'
  return 'partial'
}

export function buildOverlap(recipes: CompareRecipe[]): OverlapRow[] {
  const total = recipes.length
  const order: string[] = []
  const present = new Map<string, Set<string>>()

  for (const recipe of recipes) {
    const key = recipePairKey(recipe.fab_name, recipe.recipe_id)
    const seenInRecipe = new Set<string>()
    for (const p of recipe.parameters) {
      if (seenInRecipe.has(p.Parameter)) continue
      seenInRecipe.add(p.Parameter)
      if (!present.has(p.Parameter)) {
        present.set(p.Parameter, new Set())
        order.push(p.Parameter)
      }
      present.get(p.Parameter)!.add(key)
    }
  }

  return order.map((parameter) => {
    const keys = present.get(parameter)!
    return {
      // (fab, id) pair keys, NOT bare recipe_id — two recipes sharing a name
      // across fabs must be distinguishable here, or a caller matching a
      // specific column against `presentIn` cannot tell them apart.
      parameter,
      presentIn: recipes
        .filter(r => keys.has(recipePairKey(r.fab_name, r.recipe_id)))
        .map(r => recipePairKey(r.fab_name, r.recipe_id)),
      count: keys.size,
      total,
      coverage: classifyCoverage(keys.size, total)
    }
  })
}

export function filterOverlap(rows: OverlapRow[], filter: CoverageFilter): OverlapRow[] {
  if (filter === 'all') return rows
  const want: Coverage = filter === 'common' ? 'all' : filter
  return rows.filter(r => r.coverage === want)
}

export function commonParameters(rows: OverlapRow[]): string[] {
  return rows.filter(r => r.coverage === 'all').map(r => r.parameter)
}

const MISSING = '없음'

export interface MatrixRow {
  /** Row identity. For settings this is `settingRowId(row)`, not the bare key. */
  key: string
  label: string
  unit?: string
  /** Group heading, for the one reader that returns nested settings. */
  section?: string | null
  values: string[]
  differs: boolean
}

/**
 * A setting row's identity across recipes: its group AND its key.
 *
 * Keying on `row.key` alone is wrong for `af_pr`, the one block whose reader
 * returns nested groups: `addressing_pattern_recognition1` and
 * `addressing_pattern_recognition2` are the same settings for two addressing
 * passes and therefore carry identical inner keys. Deduping by key would drop
 * pass 2's rows and then render pass 1's values under both headings — no error,
 * no empty cell, just the wrong number shown confidently.
 *
 * The separator is NUL rather than a space or a dot: ENAP's `Auto Focus` proves
 * office keys contain spaces, and confirmed keys are underscore- and even
 * dot-adjacent (`Edge_Search_Direct.`), so only a character the files cannot
 * hold is safe from collapsing two distinct rows into one.
 */
export function settingRowId(row: SettingRow): string {
  return row.section ? `${row.section}\u0000${row.key}` : row.key
}

interface IdpFieldDescriptor {
  key: keyof CompareIdpFields
  label: string
}

export const IDP_COMPARE_FIELDS: readonly IdpFieldDescriptor[] = [
  { key: 'Addressing', label: 'Addressing' },
  { key: 'Double_Addressing', label: 'Double_Addressing' },
  { key: 'Mother_Para', label: 'Mother_Para' },
  { key: 'Region', label: 'Region' },
  { key: 'Meas_Counting', label: 'Meas_Counting' },
  { key: 'dnumber_removed', label: 'dnumber_removed' }
]

export function cellsDiffer(values: string[]): boolean {
  if (values.length < 2) return false
  return values.some(v => v !== values[0])
}

export function findParameter(recipe: CompareRecipe, parameter: string): CompareParameter | null {
  return recipe.parameters.find(p => p.Parameter === parameter) ?? null
}

export function buildIdpRows(recipes: CompareRecipe[], parameter: string): MatrixRow[] {
  return IDP_COMPARE_FIELDS.map((field) => {
    const values = recipes.map((recipe) => {
      const p = findParameter(recipe, parameter)
      if (!p) return MISSING
      const v = p.idp[field.key]
      if (v === null || v === undefined) return '—'
      // String(true) is 'true', but the open screen's BoolPill says 'True'.
      // Format explicitly so one value does not read two ways across screens.
      return typeof v === 'boolean' ? (v ? 'True' : 'False') : String(v)
    })
    return { key: String(field.key), label: field.label, values, differs: cellsDiffer(values) }
  })
}

/**
 * One row per setting key, one column per recipe, for the visible cell.
 *
 * `details` is aligned with `recipes` by index — index i is recipe i's settings
 * for the currently selected parameter, or `null` when that recipe does not
 * declare it. Rows are the UNION of keys across recipes in first-seen order, so
 * a field only one recipe carries still gets a row (and reads as differing)
 * rather than being invisible.
 */
export function buildSettingRows(
  details: (CompareParamDetail | null)[],
  slot: ImageSlotKey
): MatrixRow[] {
  const blocks = details.map(detail => blockForSlot(detail, slot))
  const ids: string[] = []
  const seen = new Map<string, SettingRow>()
  for (const block of blocks) {
    for (const row of block?.rows ?? []) {
      const id = settingRowId(row)
      if (!seen.has(id)) {
        ids.push(id)
        seen.set(id, row)
      }
    }
  }
  return ids.map((id) => {
    const values = blocks.map((block) => {
      if (!block) return MISSING
      const row = block.rows.find(r => settingRowId(r) === id)
      return row ? formatSettingValue(row.value) : MISSING
    })
    const row = seen.get(id)!
    return {
      key: id,
      label: row.key,
      section: row.section ?? null,
      values,
      differs: cellsDiffer(values)
    }
  })
}

export function imageFilenames(
  recipes: CompareRecipe[],
  parameter: string,
  slot: ImageSlotKey
): (string | null)[] {
  return recipes.map((recipe) => {
    const p = findParameter(recipe, parameter)
    return p ? (p.images[slot] ?? null) : null
  })
}

export interface ValueBucket {
  value: string
  count: number
  labels: string[]
  isOutlier: boolean
}

export interface CompareWorkbook {
  sheets: WorkbookSheet[]
}

/**
 * Display labels for a compared recipe set: bare recipe_id, UNLESS the set
 * spans more than one fab — the same recipe name can legitimately appear once
 * per fab in a cross-fab compare, and two identically-labeled entries over
 * genuinely different data is exactly the kind of silent-wrong-answer the
 * compare screens must not produce. Shared by the workbook export's column
 * headers and CompareGrouping's expanded-bucket recipe list.
 */
export function compareRecipeLabels(recipes: CompareColumn[]): string[] {
  const multiFab = spansFabs(recipes)
  return recipes.map(r => (multiFab ? `${r.recipe_id} (${r.fab_name})` : r.recipe_id))
}

/** `${recipePairKey(fab_name, recipe_id)}::${parameter}` -> that pair's fetched settings. */
export type CompareDetailIndex = Map<string, CompareParamDetail>

export const compareDetailKey = (fabName: string, recipeId: string, parameter: string) =>
  `${recipePairKey(fabName, recipeId)}::${parameter}`

export function buildCompareWorkbook(
  recipes: CompareRecipe[],
  parameters: string[],
  /**
   * Settings for every (recipe, parameter) pair the export covers. Passed in
   * rather than read off `recipes`, because settings are no longer part of the
   * compare payload — they are fetched per cell, and the export bulk-fetches
   * what it needs before calling this. A pair missing from the index exports as
   * 없음 rather than as a silently blank row.
   */
  details: CompareDetailIndex = new Map()
): CompareWorkbook {
  const recipeLabels = compareRecipeLabels(recipes)
  const sheets: WorkbookSheet[] = []

  const overlap = buildOverlap(recipes)
  const overlapRows: (string | number)[][] = [['parameter', 'coverage', ...recipeLabels]]
  for (const row of overlap) {
    overlapRows.push([
      row.parameter,
      row.coverage,
      ...recipes.map(r => (row.presentIn.includes(recipePairKey(r.fab_name, r.recipe_id)) ? '✓' : '—'))
    ])
  }
  sheets.push({ name: 'Overlap', rows: overlapRows })

  const idpRows: (string | number)[][] = [['parameter', 'attr', ...recipeLabels]]
  for (const parameter of parameters) {
    for (const r of buildIdpRows(recipes, parameter)) {
      idpRows.push([parameter, r.label, ...r.values])
    }
  }
  sheets.push({ name: 'IDP', rows: idpRows })

  for (const slot of COMPARE_SLOTS) {
    const rows: (string | number)[][] = [['parameter', 'attr', ...recipeLabels]]
    for (const parameter of parameters) {
      const forParameter = recipes.map(
        recipe => details.get(compareDetailKey(recipe.fab_name, recipe.recipe_id, parameter)) ?? null
      )
      for (const r of buildSettingRows(forParameter, slot.key)) {
        // Grouped settings (af_pr) are qualified rather than rendered as a
        // heading: a sheet is flat, and two addressing passes carry the same
        // inner keys, so a bare label would put identical `attr` values on rows
        // that mean different things.
        rows.push([parameter, r.section ? `${r.section}.${r.label}` : r.label, ...r.values])
      }
    }
    sheets.push({ name: slot.stage, rows })
  }

  return { sheets }
}

export interface CompareImageBlock {
  sheetName: string // 활성 슬롯의 stage 이름 (예: 'Measure 1')
  parameter: string // 활성 파라미터
  images: (string | null)[] // recipe별 이미지 파일명(없으면 null)
}

export async function downloadCompareWorkbook(
  workbook: CompareWorkbook,
  filename: string,
  imageBlock?: CompareImageBlock
): Promise<void> {
  const book = await createWorkbook()

  for (const sheet of workbook.sheets) {
    const ws = book.addWorksheet(sheet.name.slice(0, 31))
    for (const row of sheet.rows) {
      ws.addRow(row)
    }

    if (imageBlock && sheet.name === imageBlock.sheetName) {
      // The image FILENAMES, not the images. Until 2026-07-29 this stamped a
      // browser-rendered fake SEM texture into the sheet — harmless while every
      // other column was fabricated too, actively misleading now that they are
      // real tool data. Embedding the genuine images would mean pulling each
      // one off the tool's FTP server at export time; the names let a reader
      // find them without that cost. (header is row 1)
      ws.spliceRows(2, 0, ['이미지', imageBlock.parameter, ...imageBlock.images.map(f => f ?? '없음')], [])
    }
  }

  await writeWorkbook(book, filename)
}

export function groupFieldValues(pairs: { label: string, value: string }[]): ValueBucket[] {
  const map = new Map<string, string[]>()
  const order: string[] = []
  for (const { label, value } of pairs) {
    if (!map.has(value)) {
      map.set(value, [])
      order.push(value)
    }
    map.get(value)!.push(label)
  }

  const buckets: ValueBucket[] = order.map(value => ({
    value,
    count: map.get(value)!.length,
    labels: map.get(value)!,
    isOutlier: false
  }))
  buckets.sort((a, b) => b.count - a.count)

  const total = pairs.length
  const maxCount = buckets[0]?.count ?? 0
  const largestBuckets = buckets.filter(b => b.count === maxCount).length

  for (const bucket of buckets) {
    const isLargest = bucket.count === maxCount
    const share = total > 0 ? bucket.count / total : 0
    bucket.isOutlier = !isLargest && largestBuckets === 1 && share <= OUTLIER_SHARE
  }

  return buckets
}
