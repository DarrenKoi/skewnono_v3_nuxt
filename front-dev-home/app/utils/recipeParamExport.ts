/**
 * One parameter of one recipe, as a workbook.
 *
 * Separate from `utils/recipeCompare.ts` on purpose: that builder is shaped
 * around an N-recipes-wide matrix, and its filenames-only image decision was
 * driven by a cost — one FTP pull per recipe per image — that does not apply to
 * a single parameter's at-most-three slots.
 *
 * The build is PURE and returns image PLACEMENTS rather than bytes, so the
 * layout is `node --test`-able while the fetching stays in the browser half.
 *
 * Spec: `docs/superpowers/specs/2026-08-02-recipe-param-export-and-api-design.md`
 */

import type { IdpImageInfoRow, IdpLocator, WaferMpInfoRow } from '../composables/useRecipeSearchApi.ts'
import type { ParamDetail, ParamImage, SettingBlock } from '../composables/useRecipeParamDetail.ts'
import { IMAGE_SLOTS } from './recipeView.ts'
import { createWorkbook, writeWorkbook } from './xlsx.ts'
import { safeFileNamePart } from './csvDownload.ts'

// Relative `.ts` specifier, not the `~` alias, for the same reason
// `recipeCompare.ts` uses one: `node --test` cannot resolve `~`, but resolves
// this, and `nuxt typecheck` accepts it. `IMAGE_SLOTS` is a real value import.

/**
 * The slots that carry a picture, in recipe order.
 *
 * DERIVED from `IMAGE_SLOTS` rather than restated. `hasImage` encodes a
 * user-confirmed office fact — `image_add3` breaks the `img_*` naming run but
 * IS an image, while `img_add2`/`img_meas2` are the SETTING files `af_pr` and
 * `amp` come from. `recipeCompare.ts` records that a false premise about
 * `node --test` imports once grew three copies of this table; a fourth would
 * mean a corrected `stage` or `hasImage` silently not reaching the export.
 */
const PICTURE_SLOTS = IMAGE_SLOTS.filter(slot => slot.hasImage)

/** The order slots appear within 이미지 — recipe order, not request order. */
const SLOT_ORDER = PICTURE_SLOTS.map(slot => slot.key)

/** Stage labels, so a slot with no ParamImage can still be named in the sheet. */
const STAGE_OF: Record<string, string> = Object.fromEntries(
  PICTURE_SLOTS.map(slot => [slot.key, slot.stage])
)

/**
 * The picture slots split the way the export offers them: 측정 is
 * unconditional, Addressing is opt-in because it is the larger half of the
 * tool reads and the part a reader most often does not need.
 */
export const EXPORT_IMAGE_SLOTS = {
  measure: PICTURE_SLOTS.filter(slot => slot.role === 'measure').map(slot => slot.key),
  addressing: PICTURE_SLOTS.filter(slot => slot.role === 'address').map(slot => slot.key)
}

export interface ParamExportInput {
  recipeId: string
  fabName: string
  toolLabel: string
  locator: IdpLocator
  /** The SELECTED idp_image_info row — one image definition, not the parameter.
   *  Typed precisely rather than as a string bag, so a renamed office column is
   *  a compile error instead of a blank cell in a shipped workbook. */
  idp: IdpImageInfoRow
  detail: ParamDetail | null
  /** wafer_mp_info already filtered to this parameter — what the 측정 위치
   *  tab shows. Filtering stays with the caller so the sheet and the screen
   *  cannot disagree about which points belong to the row. */
  mpRows: WaferMpInfoRow[]
  /** Which image slots to include. Order is normalised to SLOT_ORDER. */
  slots: string[]
  exportedAt: string
}

/** The whole recipe: every parameter row and every measurement location.
 *  No images and no settings, so building it costs no tool I/O. */
export interface RecipeExportInput {
  recipeId: string
  fabName: string
  toolLabel: string
  locator: IdpLocator
  idpRows: IdpImageInfoRow[]
  mpRows: WaferMpInfoRow[]
  exportedAt: string
}

export type ParamCell = string | number | boolean | null

export interface ParamSheet {
  name: string
  /**
   * Every row the sheet contains, including its `source: …` line where it has
   * one. The source is a ROW rather than a field on purpose: `anchorRow` is an
   * index into this array, so anything the writer prepended on its own would
   * shift every embedded picture down by one — an invariant spanning two
   * functions and enforced only by a comment. Here the writer is uniform.
   */
  rows: ParamCell[][]
}

export interface ParamImagePlacement {
  slot: string
  stage: string
  name: string
  /** 0-based index into the 이미지 sheet's rows. That row is blank and is where
   *  the picture is anchored; the writer sets its height. */
  anchorRow: number
}

export interface ParamWorkbook {
  sheets: ParamSheet[]
  images: ParamImagePlacement[]
}

/** Written in this order, which is the order the screen presents them.
 *  `keyof`-typed so a column renamed in the API type fails the build here. */
const IDP_FIELDS: (keyof IdpImageInfoRow)[] = [
  'Parameter', 'SEQ', 'Last_SEQ', 'Region', 'Meas_Counting',
  'Addressing', 'Double_Addressing', 'Mother_Para', 'dnumber_removed',
  'img_add1', 'img_add2', 'image_add3', 'img_meas1', 'img_meas2'
]

/** wafer_mp_info columns, in table order. `img_meas2` is left out: in THIS
 *  table it is P_No again (user-confirmed 2026-08-05), and MpTable.vue omits it
 *  for the same reason — two columns of one integer read as two facts. */
const MP_FIELDS: (keyof WaferMpInfoRow)[] = [
  'Parameter', 'ChipNo_X', 'ChipNo_Y', 'Coordinate_X', 'Coordinate_Y',
  'P_No', 'D_No', 'Diff', 'Rel', 'Rel_MoveX', 'Rel_MoveY',
  'Coordinate_X_r', 'Coordinate_Y_r'
]

const NO_FILE = '파일 없음'
const MP_SHEET = '측정 위치'
const NO_POINTS = '매칭되는 측정 포인트가 없습니다.'

type Meta = Pick<ParamExportInput, 'recipeId' | 'fabName' | 'toolLabel' | 'locator' | 'exportedAt'>

function metaRows(input: Meta): ParamCell[][] {
  return [
    ['field', 'value'],
    ['recipe_id', input.recipeId],
    ['fab_name', input.fabName],
    ['tool', input.toolLabel]
  ]
}

function locatorRows(input: Meta): ParamCell[][] {
  return [
    ['eqp_ip', input.locator.eqp_ip],
    ['class_name', input.locator.class_name],
    ['idw', input.locator.idw],
    ['idp', input.locator.idp],
    ['exported_at', input.exportedAt]
  ]
}

function overviewSheet(input: ParamExportInput): ParamSheet {
  const rows = metaRows(input)
  for (const field of IDP_FIELDS) {
    const value = input.idp[field]
    // `?? ''` rather than `|| ''`: three of these fields are booleans and
    // `false` is a real answer, not a missing one.
    rows.push([field, (value ?? '') as ParamCell])
  }
  rows.push(...locatorRows(input))
  return { name: '개요', rows }
}

/** One header row of `fields`, then one row per record. */
function tableSheet<T>(
  name: string,
  fields: (keyof T)[],
  records: T[],
  empty: string
): ParamSheet {
  const rows: ParamCell[][] = [fields.map(String)]
  for (const record of records) {
    rows.push(fields.map(field => (record[field] ?? '') as ParamCell))
  }
  if (!records.length) rows.push([empty])
  return { name, rows }
}

function blockSheet(
  name: string,
  block: SettingBlock | null | undefined,
  /** Sheets whose shape is promised regardless of the data. AF_PR is
   *  section/key/value by contract — a file that happened to carry no section
   *  must not silently demote it to two columns and change the sheet a script
   *  is parsing. Derivation can only ADD the column, never remove it. */
  alwaysSectioned = false
): ParamSheet {
  if (!block) return { name, rows: [[NO_FILE]] }
  const sectioned = alwaysSectioned || block.rows.some(row => row.section != null)
  const rows: ParamCell[][] = [
    [`source: ${block.source}`],
    sectioned ? ['section', 'key', 'value'] : ['key', 'value']
  ]
  for (const row of block.rows) {
    // section stays its OWN column rather than being folded into the key: a
    // row's identity is (section, key), and two addressing passes carry the
    // same inner keys, so a flat label would show one pass under both.
    rows.push(sectioned ? [row.section ?? '', row.key, row.value] : [row.key, row.value])
  }
  return { name, rows }
}

function imageSheet(
  input: ParamExportInput
): { sheet: ParamSheet, images: ParamImagePlacement[] } {
  const wanted = SLOT_ORDER.filter(slot => input.slots.includes(slot))
  // GROUPED, not one-per-slot: an HV-SEM slot expands to several stem-suffixed
  // files (2026-08-08). A `Map(images.map(...))` here silently kept only the
  // last file per slot, dropping the rest from the export.
  const bySlot = new Map<string, ParamImage[]>()
  for (const image of input.detail?.images ?? []) {
    const list = bySlot.get(image.slot)
    if (list) list.push(image)
    else bySlot.set(image.slot, [image])
  }
  const rows: ParamCell[][] = []
  const images: ParamImagePlacement[] = []

  for (const slot of wanted) {
    const stage = STAGE_OF[slot] ?? slot
    const slotImages = bySlot.get(slot) ?? []
    rows.push([stage, slot])
    if (!slotImages.length) {
      // The slot holds "non", or the detail never loaded. Named rather than
      // skipped, so a reader can tell "not requested" from "not present".
      rows.push(['없음'])
      rows.push([])
      continue
    }
    for (const image of slotImages) {
      rows.push([image.name])
      images.push({ slot, stage, name: image.name, anchorRow: rows.length })
      rows.push([])
      if (image.cond) {
        rows.push(['key', 'value', image.cond.source])
        for (const row of image.cond.rows) rows.push([row.key, row.value])
      } else {
        rows.push([NO_FILE])
      }
      rows.push([])
    }
  }

  if (!rows.length) rows.push(['포함된 이미지가 없습니다.'])
  return { sheet: { name: '이미지', rows }, images }
}

export function buildParamWorkbook(input: ParamExportInput): ParamWorkbook {
  const { sheet, images } = imageSheet(input)
  return {
    sheets: [
      overviewSheet(input),
      blockSheet('AMP', input.detail?.amp),
      blockSheet('AF_PR', input.detail?.af_pr, true),
      sheet,
      tableSheet(MP_SHEET, MP_FIELDS, input.mpRows, NO_POINTS)
    ],
    images
  }
}

/** Every parameter row and every measurement location, one sheet each. */
export function buildRecipeWorkbook(input: RecipeExportInput): ParamWorkbook {
  const overview = metaRows(input)
  overview.push(
    ['parameter_rows', input.idpRows.length],
    ['points', input.mpRows.length],
    ...locatorRows(input)
  )
  return {
    sheets: [
      { name: '개요', rows: overview },
      tableSheet('파라미터', IDP_FIELDS, input.idpRows, '파라미터가 없습니다.'),
      tableSheet(MP_SHEET, MP_FIELDS, input.mpRows, NO_POINTS)
    ],
    images: []
  }
}

/** `RCP_001_Para_13.xlsx`. Recipe and parameter names come from the office and
 *  can carry characters a filesystem rejects, so they go through the shared
 *  `safeFileNamePart` — the same one every other export filename uses. */
export function paramExportFilename(recipeId: string, parameter: string): string {
  return `${safeFileNamePart(recipeId)}_${safeFileNamePart(parameter)}.xlsx`
}

/** `RCP_001_all.xlsx` — the whole-recipe workbook. */
export function recipeExportFilename(recipeId: string): string {
  return `${safeFileNamePart(recipeId)}_all.xlsx`
}

/** Roughly 4:3 at a readable size in Excel's default zoom. */
const IMAGE_BOX = { width: 320, height: 240 }
/** Excel row height is in points; the anchored row must clear the picture. */
const ANCHOR_ROW_POINTS = 190
/** Every sheet gets at least this many sized columns; wide tables get more. */
const SHEET_COLUMNS = 3

/**
 * Write the workbook, embedding each placement's actual picture.
 *
 * `resolveImageUrl` is injected so this module never reaches for
 * `useRuntimeConfig()` — the pure half above stays importable under
 * `node --test`, which has no Nuxt runtime.
 *
 * A picture that cannot be fetched is labelled in place rather than failing the
 * export: the source is a live FTP server on a production tool, and one 404
 * should not cost the user the other three sheets.
 */
export async function downloadParamWorkbook(
  workbook: ParamWorkbook,
  filename: string,
  resolveImageUrl: (name: string) => string
): Promise<void> {
  const book = await createWorkbook()

  let imageWorksheet: ReturnType<typeof book.addWorksheet> | null = null
  for (const sheet of workbook.sheets) {
    const ws = book.addWorksheet(sheet.name.slice(0, 31))
    // Uniform over every sheet, which is what keeps `anchorRow` a plain index
    // into `sheet.rows`: nothing is written that the builder did not lay out.
    for (const row of sheet.rows) ws.addRow(row)
    // getColumn, not `ws.columns.forEach`: `columns` is only populated when the
    // sheet was given a column definition, and these are built from addRow.
    const columns = Math.max(SHEET_COLUMNS, ...sheet.rows.map(row => row.length))
    for (let column = 1; column <= columns; column += 1) {
      ws.getColumn(column).width = 28
    }
    if (sheet.name === '이미지') imageWorksheet = ws
  }

  if (imageWorksheet) {
    for (const placement of workbook.images) {
      try {
        const response = await fetch(resolveImageUrl(placement.name), {
          credentials: 'include'
        })
        if (!response.ok) throw new Error(String(response.status))
        const buffer = await response.arrayBuffer()
        const extension = placement.name.toLowerCase().endsWith('.png') ? 'png' : 'jpeg'
        const id = book.addImage({
          // exceljs types this as its own Node Buffer alias; the browser build
          // accepts an ArrayBuffer at runtime.
          buffer: buffer as unknown as ArrayBuffer,
          extension
        })
        imageWorksheet.getRow(placement.anchorRow + 1).height = ANCHOR_ROW_POINTS
        imageWorksheet.addImage(id, {
          tl: { col: 0, row: placement.anchorRow },
          ext: IMAGE_BOX
        })
      } catch {
        imageWorksheet.getRow(placement.anchorRow + 1).getCell(1).value
          = `${placement.name} (이미지를 가져오지 못했습니다)`
      }
    }
  }

  await writeWorkbook(book, filename)
}
