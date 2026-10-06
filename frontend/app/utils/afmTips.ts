// Pure logic for AFM 팁 모니터링: one tool's measurement list, read as what each
// measurement says about the tip that made it. No DOM/Nuxt imports so it runs
// under `node --test`. A tip is judged against the other measurements of its
// own TYPE (`Tip ID`) — there is no spec yet, so the limits are statistical.
// Two values are not judged that way (office 확인 2026-10-07): Mileage is a
// counter that only runs up until the tip is changed, so it has no limits at
// all, and an MCNT tip's Tip Width is held against that one tip's own readings.
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import { measuredAt } from './afmSearch.ts'
import { isOutside, robustSd, type ControlLimits, type HealthPoint } from './afmTrend.ts'
import { median } from './stats.ts'

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

export type TipState = 'bad' | 'warn' | 'ok' | 'hold'

// A tip's state speaks for now, so it reads this many of its latest
// measurements: two or more outside a limit is 이상, one is 주의.
export const TIP_RECENT = 5

export interface TipUnit {
  tip: string
  type: string
  // Its measurements, oldest first.
  points: TipPoint[]
  // The recipes it measured, most used first.
  recipes: { recipe: string, count: number }[]
  // What its Tip Width is held against: the type's limits, or its own on MCNT.
  widthLimits: ControlLimits | null
  // Measurements of this tip with a value outside its limits.
  flagged: number
  // The same, among its last TIP_RECENT — and which values those were.
  recentOut: number
  recentParams: TipParam[]
  // 'hold' where the type has too few measurements to draw any limit.
  state: TipState
}

export interface TipFlag {
  point: TipPoint
  params: TipParam[]
}

export interface TipCategory {
  type: string
  points: TipPoint[]
  stats: TipParamStat[]
  // Worst state first, then the tip used last.
  tips: TipUnit[]
  // Newest measurement first.
  flags: TipFlag[]
}

// Median ± 3σ, σ from the MAD. Not 시계열 비교's controlLimits, whose centre is
// the mean: a tip going bad drags a mean towards itself and puts the healthy
// measurements outside instead. Here the excursions are what is being looked for.
const tipLimits = (values: number[]): ControlLimits => {
  const mu = median(values)
  const sigma = robustSd(values)
  return { mu, sigma, ucl: mu + 3 * sigma, lcl: mu - 3 * sigma }
}

// MCNT widths run 33.96–39.11 across slots and move both ways within one, so a
// type-wide band would flag healthy tips. Every other type's width is in effect
// one value. ponytail: told by the name — a list per tool if an ID proves otherwise.
export const widthIsPerTip = (type: string): boolean => /MCNT/i.test(type)

const limitsOf = (values: number[]): ControlLimits | null =>
  values.length < TIP_MIN_SAMPLES ? null : tipLimits(values)

const STATE_RANK: Record<TipState, number> = { bad: 0, warn: 1, ok: 2, hold: 3 }

// The recipes a set of measurements ran, most used first.
export const tipRecipes = (points: TipPoint[]): { recipe: string, count: number }[] => {
  const counts = new Map<string, number>()
  for (const point of points) counts.set(point.recipe, (counts.get(point.recipe) ?? 0) + 1)
  return [...counts.entries()]
    .map(([recipe, count]) => ({ recipe, count }))
    .sort((a, b) => b.count - a.count || a.recipe.localeCompare(b.recipe))
}

// The tip on the tool now: the one that made its latest measurement.
export const mountedTip = (points: TipPoint[]): string | null => points.at(-1)?.tip ?? null

export const tipCategories = (points: TipPoint[]): TipCategory[] => {
  const byType = new Map<string, TipPoint[]>()
  for (const point of points) {
    const group = byType.get(point.type)
    if (group) group.push(point)
    else byType.set(point.type, [point])
  }
  return [...byType.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([type, group]) => {
    const byTip = new Map<string, TipPoint[]>()
    for (const point of group) {
      const own = byTip.get(point.tip)
      if (own) own.push(point)
      else byTip.set(point.tip, [point])
    }
    const perTip = widthIsPerTip(type)
    const limits = TIP_PARAMS.map((param) => {
      const values = group.flatMap(p => p[param] ?? [])
      const unjudged = param === 'mileage' || (param === 'tipWidth' && perTip)
      return { param, n: values.length, limits: unjudged ? null : limitsOf(values) }
    })
    const typeWidth = limits.find(stat => stat.param === 'tipWidth')!.limits
    const widthOf = new Map([...byTip].map(([tip, own]) =>
      [tip, perTip ? limitsOf(own.flatMap(p => p.tipWidth ?? [])) : typeWidth]))
    const flags = group.flatMap((point) => {
      const params = limits.flatMap(({ param, limits }) =>
        point[param] !== null && isOutside(point[param], param === 'tipWidth' ? widthOf.get(point.tip)! : limits) ? [param] : [])
      return params.length ? [{ point, params }] : []
    })
    const outside = new Map(flags.map(f => [f.point.key, f.params]))
    const judged = limits.some(stat => stat.limits !== null) || [...widthOf.values()].some(Boolean)
    const tips = [...byTip.entries()].map(([tip, own]): TipUnit => {
      const recent = own.slice(-TIP_RECENT).flatMap(p => outside.get(p.key) ? [outside.get(p.key)!] : [])
      return {
        tip,
        type,
        points: own,
        recipes: tipRecipes(own),
        widthLimits: widthOf.get(tip)!,
        flagged: own.filter(p => outside.has(p.key)).length,
        recentOut: recent.length,
        recentParams: TIP_PARAMS.filter(param => recent.some(params => params.includes(param))),
        state: !judged ? 'hold' : recent.length >= 2 ? 'bad' : recent.length === 1 ? 'warn' : 'ok'
      }
    })
    return {
      type,
      points: group,
      stats: limits.map(stat => ({ ...stat, outliers: flags.filter(f => f.params.includes(stat.param)).length })),
      tips: tips.sort((a, b) => STATE_RANK[a.state] - STATE_RANK[b.state] || b.points.at(-1)!.time - a.points.at(-1)!.time),
      flags: flags.reverse()
    }
  })
}
