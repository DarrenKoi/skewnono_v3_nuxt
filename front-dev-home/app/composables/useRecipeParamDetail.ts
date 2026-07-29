/**
 * Per-parameter settings from the raw-recipe folder beside the .idp.
 *
 * Fetched on click rather than with the recipe, because each parameter costs up
 * to five files off the measuring tool's own FTP server and most parameters are
 * never opened. See
 * `docs/superpowers/specs/2026-07-29-raw-recipe-folder-amp-and-conditions-design.md`.
 *
 * The rows are OPEN key/value, not fixed columns: the office parser's field
 * names are still unverified, and an open shape renders an unexpected key
 * instead of dropping it.
 */

import type { IdpImageInfoRow, IdpLocator } from './useRecipeSearchApi.ts'

/** One parsed setting. Order is the office reader's own — never re-sorted. */
export interface SettingRow {
  key: string
  value: string
}

export interface SettingBlock {
  /** The file these rows came from, e.g. `PRMS0000`. Shown so a surprising
   *  value can be traced back to a file without reading a server log. */
  source: string
  rows: SettingRow[]
}

export interface ParamImage {
  /** `img_add1` | `image_add3` | `img_meas1` — the three slots that name an image. */
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

/** Pull the five slot values off an idp_image_info row. */
export function slotsOf(row: Pick<IdpImageInfoRow, typeof SLOT_KEYS[number]>): Record<string, string> {
  return Object.fromEntries(SLOT_KEYS.map(key => [key, row[key]]))
}

/**
 * URL for one raw-recipe image.
 *
 * A plain `<img src>` rather than base64 in JSON: base64 inflates the payload
 * by a third, blocks the JSON parse, and is invisible to the browser cache.
 * Pure, so it is the part of this module that `node --test` can cover.
 */
export function recipeImageUrl(
  toolSlug: string,
  locator: IdpLocator,
  name: string
): string {
  const params = new URLSearchParams({ ...locator, name })
  return `/api/${toolSlug}/recipe-search/recipe-image?${params.toString()}`
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
  return $fetch<ParamDetail[]>(`/api/${toolSlug}/recipe-search/param-detail`, {
    method: 'POST',
    body: { items }
  })
}

/**
 * One parameter's settings, cached per (recipe, parameter) so re-selecting a
 * parameter already viewed costs nothing.
 */
export function useRecipeParamDetail(
  toolSlug: string,
  locator: IdpLocator,
  recipeId: string,
  parameter: string,
  slots: Record<string, string>
) {
  return useAsyncData<ParamDetail | null>(
    `recipe-param-detail:${recipeId}:${parameter}`,
    async () => {
      const rows = await fetchParamDetails(toolSlug, [{ locator, parameter, slots }])
      return rows[0] ?? null
    }
  )
}
