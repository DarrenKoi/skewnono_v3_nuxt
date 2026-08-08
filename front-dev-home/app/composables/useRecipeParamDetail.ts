/**
 * Per-parameter settings from the raw-recipe folder beside the .idp.
 *
 * Fetched on click rather than with the recipe, because each parameter costs up
 * to five files off the measuring tool's own FTP server and most parameters are
 * never opened. See `docs/datatables/recipe_idp.txt`.
 *
 * The rows are OPEN key/value, not fixed columns: the office parser's field
 * names are still unverified, and an open shape renders an unexpected key
 * instead of dropping it.
 */

import { joinApiPath } from '../utils/apiPath.ts'
import type { IdpLocator } from './useRecipeSearchApi.ts'

/** One parsed setting. Order is the office reader's own — never re-sorted. */
export interface SettingRow {
  key: string
  value: string
  /**
   * Which nested group this row came from, for readers that return a dict OF
   * dicts. ENMP (`af_pr`) is the only one today — eight groups covering the
   * addressing and measurement sequences (office 확인 2026-07-30). The other
   * four readers are flat and omit this entirely.
   *
   * ★ A row's identity is (section, key), NOT key. Addressing pass 1 and pass 2
   *   are the same kind of settings twice, so they carry the SAME inner keys;
   *   anything deduping or joining on key alone shows pass 1's value under both
   *   headings without erroring. See `settingRowId` in `utils/recipeCompare`.
   */
  section?: string | null
}

export interface SettingBlock {
  /** The file these rows came from, e.g. `PRMS0000`. Shown so a surprising
   *  value can be traced back to a file without reading a server log. */
  source: string
  rows: SettingRow[]
}

export interface ParamImage {
  /** `img_add1` | `image_add3` | `img_meas1` — the three slots that name an image.
   *
   * ★ NOT unique within `ParamDetail.images` (2026-08-08): an HV-SEM slot
   *   expands to several stem-suffixed files (`IMMS0001-U.jpeg` / -T / -M /
   *   -L), one entry per FILE, each with its own cond. Key on (slot, name). */
  slot: string
  /** Human label, e.g. `Addressing 1`. */
  stage: string
  /** Full filename, ready to hand to `recipeImageUrl`. */
  name: string
  cond: SettingBlock | null
}

export interface ParamDetail {
  parameter: string
  /** From `img_meas2`. `null` when the slot is `non`, the file is absent, or
   *  it could not be parsed — all three render 파일 없음. */
  amp: SettingBlock | null
  /** Auto-focus + pattern recognition, from `img_add2` with `PR` → `EN`. */
  af_pr: SettingBlock | null
  images: ParamImage[]
}

/** The five `img_*` values, posted back verbatim as `slots`. */
export const SLOT_KEYS = [
  'img_add1',
  'img_add2',
  'image_add3',
  'img_meas1',
  'img_meas2'
] as const

/** Pull the five slot values off an idp_image_info row (or a compare `images` map). */
export function slotsOf(row: Record<string, string>): Record<string, string> {
  return Object.fromEntries(SLOT_KEYS.map(key => [key, row[key] ?? '']))
}

/**
 * Identity of one param-detail request: the parameter AND its five slot values.
 *
 * ★ The parameter alone is NOT the identity. A row of idp_image_info is one image
 *   DEFINITION, not one parameter (`docs/datatables/recipe_idp.txt`), so the same
 *   parameter can appear in several rows naming different files — Para_13 at
 *   SEQ 4/6 and SEQ 11/15 resolve to `IMMP0004…` and `IMMP0011…`. A cache keyed
 *   on the parameter served the first row's images and settings under the second
 *   row's heading with no cue that it had done so.
 *
 * Built from the same `parameter` and `slots` that go INTO the request, so the
 * key cannot drift from what was actually fetched, and read through SLOT_KEYS so
 * it does not depend on the object's insertion order.
 *
 * NUL-separated because every part is an office-supplied string: `/`, `:` and `_`
 * all occur in real recipe and file names, and any of them as a separator lets
 * one pair forge another's key.
 */
export function paramDetailKey(parameter: string, slots: Record<string, string>): string {
  return [parameter, ...SLOT_KEYS.map(key => slots[key] ?? '')].join('\u0000')
}

/** Base for every raw-folder call, so a Phase-3 apiBase change reaches them
 *  the same way it reaches the rest of the feature. Callers in components read
 *  it once; `recipeImageUrl` takes it as an argument so it stays pure and
 *  `node --test`-able — the only automated guard this layer has. */
export const recipeApiBase = () => useRuntimeConfig().public.apiBase as string

/**
 * URL for one raw-recipe image.
 *
 * A plain `<img src>` rather than base64 in JSON: base64 inflates the payload
 * by a third, blocks the JSON parse, and is invisible to the browser cache.
 * Pure, so it is the part of this module that `node --test` can cover.
 */
export function recipeImageUrl(
  base: string,
  toolSlug: string,
  locator: IdpLocator,
  name: string
): string {
  const params = new URLSearchParams({ ...locator, name })
  return `${joinApiPath(base, `/${toolSlug}/recipe-search/recipe-image`)}?${params.toString()}`
}

export interface ParamDetailRequestItem {
  locator: IdpLocator
  parameter: string
  slots: Record<string, string>
}

/**
 * Fetch settings for one or more (recipe, parameter) pairs in ONE request.
 *
 * List-shaped because compare fans one parameter out across every selected
 * recipe, and `/api/*` allows 20 requests per 5 s per user — as N separate GETs
 * a 20-recipe compare would trip the limit on the first cell a user looked at.
 */
export function fetchParamDetails(
  toolSlug: string,
  items: ParamDetailRequestItem[]
): Promise<ParamDetail[]> {
  return $fetch<ParamDetail[]>(
    joinApiPath(recipeApiBase(), `/${toolSlug}/recipe-search/param-detail`),
    { method: 'POST', body: { items } }
  )
}

/** Server cap on `param-detail`'s item list, mirrored so callers chunk instead
 *  of getting a 400 on a wide compare. */
export const PARAM_DETAIL_MAX_ITEMS = 200

/**
 * Same as `fetchParamDetails`, but splits an over-cap list across requests.
 *
 * Used by the compare export, which needs every (recipe, parameter) pair at
 * once — 20 recipes x 30 parameters is 600 items, over the server's 200 cap.
 */
export async function fetchParamDetailsChunked(
  toolSlug: string,
  items: ParamDetailRequestItem[]
): Promise<ParamDetail[]> {
  const out: ParamDetail[] = []
  for (let i = 0; i < items.length; i += PARAM_DETAIL_MAX_ITEMS) {
    out.push(...await fetchParamDetails(toolSlug, items.slice(i, i + PARAM_DETAIL_MAX_ITEMS)))
  }
  return out
}

export interface AlignPoint {
  P_No: number
  image: string | null
  cond: SettingBlock | null
  setting: SettingBlock | null
}

/** Every wafer-align point's image, beam condition and AF/PR setting. */
export async function fetchAlignDetail(
  toolSlug: string,
  locator: IdpLocator,
  pNumbers: number[]
): Promise<AlignPoint[]> {
  if (!pNumbers.length) return []
  const response = await $fetch<{ points: AlignPoint[] }>(
    joinApiPath(recipeApiBase(), `/${toolSlug}/recipe-search/align-detail`),
    { query: { ...locator, p_numbers: pNumbers.join(',') } }
  )
  return response.points
}
