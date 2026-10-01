import { windowReachesBefore } from './activity.ts'
import type { FamilyUsageRow, FeatureCount } from '~/composables/useActivityApi'

/**
 * The 장비군별 페이지 사용 card's vocabulary and arithmetic.
 *
 * `family` is the backend's registry slug (`cdsem`), never the dashed page
 * segment (`cd-sem`) — the value in the beacon URL a page open is posted to.
 * See backend/_logging/feature_map.py, which owns the vocabulary.
 */

interface KnownFamily {
  family: string
  label: string
  /** Shown as a quiet prefix. Only Hitachi's two carry one: CD-SEM and HV-SEM
   *  are one vendor's families, and saying so on each is what tells a reader
   *  the other three are not more of the same. */
  vendor?: string
}

// The order the rail draws them in: the families that exist today first, the
// ones being added after. A family missing from this list is not dropped —
// see familyRail.
const KNOWN_FAMILIES: KnownFamily[] = [
  { family: 'cdsem', label: 'CD-SEM', vendor: 'Hitachi' },
  { family: 'hvsem', label: 'HV-SEM', vendor: 'Hitachi' },
  { family: 'veritysem', label: 'VeritySEM' },
  { family: 'provision', label: 'Provision' },
  { family: 'afm', label: 'AFM' }
]

export const toolFamilyLabel = (family: string): string =>
  KNOWN_FAMILIES.find(known => known.family === family)?.label ?? family

export interface FamilyRailItem extends KnownFamily {
  /** Distinct people who opened a page of this family — not an active-user
   *  count, and not additive across families. */
  total: number
  pages: FeatureCount[]
}

/**
 * The rail's rows: every known family in a fixed order, joined to whatever the
 * backend counted for it, followed by any family the backend sent that this
 * file has no label for.
 *
 * Fixed order rather than busiest-first: the list is five names a reader
 * learns the position of, and re-sorting it between the 7- and 30-day tabs
 * would move them under the cursor.
 */
export const familyRail = (rows: readonly FamilyUsageRow[]): FamilyRailItem[] => {
  const byFamily = new Map(rows.map(row => [row.family, row]))
  const known = KNOWN_FAMILIES.map(item => ({
    ...item,
    total: byFamily.get(item.family)?.total ?? 0,
    pages: byFamily.get(item.family)?.pages ?? []
  }))
  const unknown = rows
    .filter(row => !KNOWN_FAMILIES.some(item => item.family === row.family))
    .map(row => ({ family: row.family, label: row.family, total: row.total, pages: row.pages }))
  return [...known, ...unknown]
}

/** The day page opens began being posted to a per-family beacon URL. Opens
 *  before it all went to the plain URL, so they carry no family and cannot be
 *  back-filled — a window reaching past this date shows only part of itself.
 *
 *  DEPLOY STEP, same as PAGE_VIEW_SINCE: this is the HOME date. Reset it to
 *  the day this frontend build goes live at the office (and again, in
 *  production). See backend/activity/MIGRATION.md, "Deploy step: tool family". */
export const TOOL_FAMILY_SINCE = '2026-10-02'

export const toolFamilyNotice = (windowDays: number, today: Date): string | null =>
  windowReachesBefore(TOOL_FAMILY_SINCE, windowDays, today)
    ? `${TOOL_FAMILY_SINCE}부터 장비군을 기록합니다. 그 이전의 페이지 조회는 포함되지 않습니다`
    : null
