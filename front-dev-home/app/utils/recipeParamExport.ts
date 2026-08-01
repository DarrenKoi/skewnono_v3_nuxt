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

import type { IdpLocator } from '../composables/useRecipeSearchApi.ts'
import type { ParamDetail, SettingBlock } from '../composables/useRecipeParamDetail.ts'

/**
 * The image-bearing slots, split the way the export offers them.
 *
 * `img_add2` and `img_meas2` are absent because they are SETTING files — they
 * are where `af_pr` and `amp` come from and carry no picture.
 */
export const EXPORT_IMAGE_SLOTS = {
  measure: ['img_meas1'],
  addressing: ['img_add1', 'image_add3']
} as const

/** Stage labels, so a slot with no ParamImage can still be named in the sheet. */
const STAGE_OF: Record<string, string> = {
  img_add1: 'Addressing 1',
  image_add3: 'Addressing 3',
  img_meas1: 'Measure 1'
}

/** The order slots appear within 이미지 — recipe order, not request order. */
const SLOT_ORDER = ['img_add1', 'image_add3', 'img_meas1']

export interface ParamExportInput {
  recipeId: string
  fabName: string
  toolLabel: string
  locator: IdpLocator
  /** The SELECTED idp_image_info row — one image definition, not the parameter. */
  idp: Record<string, unknown>
  detail: ParamDetail | null
  /** Which image slots to include. Order is normalised to SLOT_ORDER. */
  slots: string[]
  exportedAt: string
}

export type ParamCell = string | number | boolean | null

export interface ParamSheet {
  name: string
  /** The file these rows came from, written above the table so a surprising
   *  value can be traced without reading a server log. */
  source?: string | null
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

/** Written in this order, which is the order the screen presents them. */
const IDP_FIELDS = [
  'Parameter', 'SEQ', 'Last_SEQ', 'Region', 'Meas_Counting',
  'Addressing', 'Double_Addressing', 'Mother_Para', 'dnumber_removed',
  'img_add1', 'img_add2', 'image_add3', 'img_meas1', 'img_meas2'
]

const NO_FILE = '파일 없음'

function overviewSheet(input: ParamExportInput): ParamSheet {
  const rows: ParamCell[][] = [
    ['field', 'value'],
    ['recipe_id', input.recipeId],
    ['fab_name', input.fabName],
    ['tool', input.toolLabel]
  ]
  for (const field of IDP_FIELDS) {
    const value = input.idp[field]
    // `?? ''` rather than `|| ''`: three of these fields are booleans and
    // `false` is a real answer, not a missing one.
    rows.push([field, (value ?? '') as ParamCell])
  }
  rows.push(
    ['eqp_ip', input.locator.eqp_ip],
    ['class_name', input.locator.class_name],
    ['idw', input.locator.idw],
    ['idp', input.locator.idp],
    ['exported_at', input.exportedAt]
  )
  return { name: '개요', rows }
}

function blockSheet(
  name: string,
  block: SettingBlock | null | undefined,
  sectioned: boolean
): ParamSheet {
  if (!block) return { name, source: null, rows: [[NO_FILE]] }
  const rows: ParamCell[][] = [sectioned ? ['section', 'key', 'value'] : ['key', 'value']]
  for (const row of block.rows) {
    // section stays its OWN column rather than being folded into the key: a
    // row's identity is (section, key), and two addressing passes carry the
    // same inner keys, so a flat label would show one pass under both.
    rows.push(sectioned ? [row.section ?? '', row.key, row.value] : [row.key, row.value])
  }
  return { name, source: block.source, rows }
}

function imageSheet(
  input: ParamExportInput
): { sheet: ParamSheet, images: ParamImagePlacement[] } {
  const wanted = SLOT_ORDER.filter(slot => input.slots.includes(slot))
  const bySlot = new Map((input.detail?.images ?? []).map(image => [image.slot, image]))
  const rows: ParamCell[][] = []
  const images: ParamImagePlacement[] = []

  for (const slot of wanted) {
    const stage = STAGE_OF[slot] ?? slot
    const image = bySlot.get(slot)
    rows.push([stage, slot])
    if (!image) {
      // The slot holds "non", or the detail never loaded. Named rather than
      // skipped, so a reader can tell "not requested" from "not present".
      rows.push(['없음'])
      rows.push([])
      continue
    }
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

  if (!rows.length) rows.push(['포함된 이미지가 없습니다.'])
  return { sheet: { name: '이미지', rows }, images }
}

export function buildParamWorkbook(input: ParamExportInput): ParamWorkbook {
  const { sheet, images } = imageSheet(input)
  return {
    sheets: [
      overviewSheet(input),
      blockSheet('AMP', input.detail?.amp, false),
      blockSheet('AF_PR', input.detail?.af_pr, true),
      sheet
    ],
    images
  }
}

/** `RCP_001_Para_13.xlsx`. Recipe and parameter names come from the office and
 *  can carry characters a filesystem rejects, so they are sanitised here. */
export function paramExportFilename(recipeId: string, parameter: string): string {
  const safe = (value: string) => (value || 'unknown').replace(/[^\w.-]+/g, '_')
  return `${safe(recipeId)}_${safe(parameter)}.xlsx`
}
