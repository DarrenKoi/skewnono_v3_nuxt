import { windowReachesBefore } from './activity.ts'
import type { FamilyUsageRow, FeatureCount } from '~/composables/useActivityApi'

/**
 * The 장비군별 페이지 사용 card's labels and its "collected since" note.
 *
 * `family` is the backend's registry slug (`cdsem`), never the dashed page
 * segment (`cd-sem`) — the value in the beacon URL a page open is posted to.
 * See backend/_logging/feature_map.py, which owns the vocabulary.
 */

/** One row of an ActivityUsageRail. */
export interface RailRow {
  key: string
  label: string
  /** A quiet word in front of the label. */
  prefix?: string
  total: number
  pages: FeatureCount[]
}

// `prefix` names the vendor on Hitachi's two only: CD-SEM and HV-SEM are one
// vendor's families, and saying so on each is what tells a reader the other
// three are not more of the same.
const FAMILY_LABELS: Record<string, { label: string, prefix?: string }> = {
  cdsem: { label: 'CD-SEM', prefix: 'Hitachi' },
  hvsem: { label: 'HV-SEM', prefix: 'Hitachi' },
  veritysem: { label: 'VeritySEM' },
  provision: { label: 'Provision' },
  afm: { label: 'AFM' }
}

/**
 * The family rows as the rail draws them. Order and the zero rows are the
 * backend's promise — every family, in registry order — so this only names
 * them. A family with no label here still shows, under its own slug: one
 * registered on the backend must not vanish because this file is behind.
 */
export const familyRail = (rows: readonly FamilyUsageRow[]): RailRow[] =>
  rows.map(row => ({
    key: row.family,
    ...(FAMILY_LABELS[row.family] ?? { label: row.family }),
    total: row.total,
    pages: row.pages
  }))

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
