// Pure logic for AFM 팁 모니터링: one tool's measurement list, read as what each
// measurement says about the tip that made it. No DOM/Nuxt imports so it runs
// under `node --test`. A tip is judged against the other measurements of its
// own TYPE (`Tip ID`) — there is no spec yet, so the limits are statistical.
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import { measuredAt } from './afmSearch.ts'
import { controlLimits, isOutside, type ControlLimits, type HealthPoint } from './afmTrend.ts'

export const TIP_PARAMS = ['tipWidth', 'approach', 'mileage', 'notCompleted', 'invalid'] as const
export type TipParam = typeof TIP_PARAMS[number]

export interface TipPoint extends Record<TipParam, number | null> {
  // The filename.
  key: string
  time: number
  recipe: string
  lot: string
  // `Tip ID`: the tip's type, and the category its limits are drawn over.
  type: string
  // The one physical tip: the ID and where it sits (cassette/port/slot).
  tip: string
}

// The measurements that name their tip, oldest first.
export const tipPoints = (rows: AfmFileRow[]): TipPoint[] =>
  rows.flatMap((row) => {
    const type = (row.tip_id ?? '').trim()
    if (!type) return []
    const seat = [row.tip_cassette_id, row.tip_port_no, row.tip_slot_no].map(v => (v ?? '').trim() || '?')
    return [{
      key: row.filename,
      time: Date.parse(measuredAt(row)),
      recipe: row.recipe_name ?? '',
      lot: row.lot_id ?? '',
      type,
      tip: `${type} · ${seat.join('/')}`,
      tipWidth: row.tip_width ?? null,
      approach: row.approach_count_mean ?? null,
      mileage: row.mileage_mean ?? null,
      notCompleted: row.not_completed_count ?? null,
      invalid: row.invalid_count ?? null
    }]
  }).sort((a, b) => a.time - b.time)

// What 시계열 비교's health strip draws. A count the measurement has no rows
// for is drawn as 0 there: a bar chart has no way to say "none".
export const tipHealth = (points: TipPoint[]): HealthPoint[] =>
  points.map(p => ({ ...p, notCompleted: p.notCompleted ?? 0, invalid: p.invalid ?? 0 }))

// Fewer measurements than this say too little about a type's spread to call
// one of them an outlier.
export const TIP_MIN_SAMPLES = 5

export interface TipParamStat {
  param: TipParam
  // Measurements that recorded the value.
  n: number
  limits: ControlLimits | null
  outliers: number
}

export interface TipUnit {
  tip: string
  count: number
  first: number
  last: number
  lastWidth: number | null
  // Measurements of this tip with a value outside its type's limits.
  flagged: number
}

export interface TipFlag {
  point: TipPoint
  params: TipParam[]
}

export interface TipCategory {
  type: string
  points: TipPoint[]
  stats: TipParamStat[]
  // Newest tip first.
  tips: TipUnit[]
  // Newest measurement first.
  flags: TipFlag[]
}

export const tipCategories = (points: TipPoint[]): TipCategory[] => {
  const byType = new Map<string, TipPoint[]>()
  for (const point of points) {
    const group = byType.get(point.type)
    if (group) group.push(point)
    else byType.set(point.type, [point])
  }
  return [...byType.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([type, group]) => {
    const limits = TIP_PARAMS.map((param) => {
      const values = group.flatMap(p => p[param] ?? [])
      return { param, n: values.length, limits: values.length < TIP_MIN_SAMPLES ? null : controlLimits(values) }
    })
    const flags = group.flatMap((point) => {
      const params = limits.flatMap(({ param, limits }) =>
        point[param] !== null && isOutside(point[param], limits) ? [param] : [])
      return params.length ? [{ point, params }] : []
    })
    const flagged = new Set(flags.map(f => f.point.key))
    const tips = new Map<string, TipUnit>()
    for (const point of group) {
      const unit = tips.get(point.tip)
        ?? { tip: point.tip, count: 0, first: point.time, last: point.time, lastWidth: null, flagged: 0 }
      unit.count += 1
      unit.last = point.time
      unit.lastWidth = point.tipWidth ?? unit.lastWidth
      unit.flagged += flagged.has(point.key) ? 1 : 0
      tips.set(point.tip, unit)
    }
    return {
      type,
      points: group,
      stats: limits.map(stat => ({ ...stat, outliers: flags.filter(f => f.params.includes(stat.param)).length })),
      tips: [...tips.values()].sort((a, b) => b.last - a.last),
      flags: flags.reverse()
    }
  })
}
