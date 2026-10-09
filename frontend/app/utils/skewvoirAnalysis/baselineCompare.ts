// Skewvoir — the hand-split baseline ↔ target comparison (S7).
//
// Every other set-scope statistic is computed FROM the set the user picked, so
// its reference moves with the selection. Here the engineer names some members
// of the set as the baseline (URL `base`) and the rest become the target; the
// answer is how far the target moved against that fixed group.
//
// It reports a difference and the sample sizes behind it — never a judgement.
// There is no spec, no Cp/Cpk and no limit derived from the baseline: the
// baseline is "이 세트 안에서 손으로 나눈 기준", not an official reference.
//
// REUSE, do not re-derive: cdu.ts's cduMetrics owns level/spread (and the
// measured↔missing gate behind it); waferChip.ts's parseChipXY is the site key
// 위치 비교's set-scope composite map already pairs sites by.
//
// Runs under raw `node --test` — sibling imports carry an explicit `.ts`.
import type { MsrFileResponse } from '~/composables/useMsrFileApi'
import { cduMetrics, type CduMetrics } from './cdu.ts'
import { isMeasuredRow } from '../msrRows.ts'
import { mean } from '../stats.ts'
import { parseChipXY } from '../waferChip.ts'

type SetFiles = ReadonlyMap<string, MsrFileResponse>

/** Above this share of a side's pooled points, one MSR is doing the talking. */
export const DOMINANCE_NOTE = 0.6

/** Baseline and target ids, each narrowed to the manifest's `included` list —
 *  which is what keeps a unit/recipe-incompatible MSR out of both sides. */
export const splitBaseline = (
  msrList: readonly string[],
  baseline: readonly string[],
  included: readonly string[]
): { base: string[], target: string[] } => {
  const ok = new Set(included)
  const isBase = new Set(baseline)
  return {
    base: baseline.filter(id => ok.has(id)),
    target: msrList.filter(id => ok.has(id) && !isBase.has(id))
  }
}

export interface BaselineSide {
  /** Ids handed in — `msrs` can be shorter (file not loaded, parameter absent). */
  requested: number
  /** The MSRs that contributed at least one measured point, each on its own. */
  msrs: { msr: string, metrics: CduMetrics }[]
  /** Every contributing point pooled with equal weight. */
  pooled: CduMetrics
  /** Largest single MSR's share of the pooled points (0 when there are none). */
  dominance: number
  /** Two or more MSRs, and one of them holds more than DOMINANCE_NOTE of the points. */
  dominated: boolean
}

export interface BaselineComparison {
  parameter: string
  unit: string
  base: BaselineSide
  target: BaselineSide
  /** null (with `reason`) unless both sides have at least two measured points. */
  comparison: {
    /** target mean − baseline mean. */
    shift: number
    /** `shift` in units of the baseline's 3σ; null when the baseline is flat. */
    shiftInBaseSigma: number | null
    /** target 3σ / baseline 3σ; null when the baseline is flat. */
    threeSigmaRatio: number | null
    /** target range − baseline range. */
    rangeDelta: number
  } | null
  reason: string | null
}

const side = (files: SetFiles, ids: readonly string[], parameter: string, unit: string): BaselineSide => {
  const msrs = ids.flatMap((msr) => {
    const metrics = cduMetrics(files.get(msr)?.rows ?? [], parameter, unit)
    return metrics.n > 0 ? [{ msr, metrics }] : []
  })
  const pooled = cduMetrics(msrs.flatMap(m => files.get(m.msr)?.rows ?? []), parameter, unit)
  const dominance = pooled.n > 0 ? Math.max(...msrs.map(m => m.metrics.n)) / pooled.n : 0
  return { requested: ids.length, msrs, pooled, dominance, dominated: msrs.length > 1 && dominance > DOMINANCE_NOTE }
}

export const baselineComparison = (
  files: SetFiles,
  baseIds: readonly string[],
  targetIds: readonly string[],
  parameter: string,
  unit = ''
): BaselineComparison => {
  const base = side(files, baseIds, parameter, unit)
  const target = side(files, targetIds, parameter, unit)
  const out = { parameter, unit, base, target }

  const b = base.pooled
  const t = target.pooled
  if (!b.level || !b.spread) return { ...out, comparison: null, reason: '기준 측정의 측정 site 가 2개 미만입니다.' }
  if (!t.level || !t.spread) {
    return {
      ...out,
      comparison: null,
      reason: targetIds.length
        ? '대상 측정의 측정 site 가 2개 미만입니다.'
        : '대상으로 남은 측정이 없습니다. 세트의 일부만 기준으로 지정하세요.'
    }
  }

  const flat = b.spread.threeSigma === 0
  return {
    ...out,
    comparison: {
      shift: t.level.mean - b.level.mean,
      shiftInBaseSigma: flat ? null : (t.level.mean - b.level.mean) / b.spread.threeSigma,
      threeSigmaRatio: flat ? null : t.spread.threeSigma / b.spread.threeSigma,
      rangeDelta: t.spread.range - b.spread.range
    },
    reason: null
  }
}

/** 위치 비교's baseline-versus-target layer: per chip, the target group's mean
 *  minus the baseline group's — over the measurement points (MP) BOTH groups
 *  measured on that chip. A chip holds several MPs, and averaging every row of
 *  it would turn "the groups measured different MPs" into a movement of the
 *  value. A chip with no MP in common is NOT a point (and never a 0): it is
 *  counted in `unpaired`. */
export const baselineDeltaMap = (
  files: SetFiles,
  baseIds: readonly string[],
  targetIds: readonly string[],
  parameter: string
): { points: [number, number, number][], unpaired: number } => {
  type Chip = { xy: [number, number], byMp: Map<number, number[]> }
  const collect = (ids: readonly string[]) => {
    const acc = new Map<string, Chip>()
    for (const id of ids) {
      for (const r of files.get(id)?.rows ?? []) {
        if (r.parameter !== parameter || !isMeasuredRow(r)) continue
        const xy = parseChipXY(r.chip_number)
        if (!xy) continue
        const key = `${xy[0]},${xy[1]}`
        const chip = acc.get(key) ?? { xy, byMp: new Map() }
        chip.byMp.set(r.mp_number, [...(chip.byMp.get(r.mp_number) ?? []), r.cd_value])
        acc.set(key, chip)
      }
    }
    return acc
  }
  const base = collect(baseIds)
  const target = collect(targetIds)

  const points: [number, number, number][] = []
  for (const [key, t] of target) {
    const b = base.get(key)
    const deltas = b
      ? [...t.byMp].flatMap(([mp, values]) => b.byMp.has(mp) ? [mean(values) - mean(b.byMp.get(mp)!)] : [])
      : []
    if (deltas.length) points.push([t.xy[0], t.xy[1], Number(mean(deltas).toFixed(3))])
  }
  const chips = new Set([...base.keys(), ...target.keys()])
  return { points, unpaired: chips.size - points.length }
}

/** The block's one sentence. States the movement; judges nothing. */
export const baselineSentence = (r: BaselineComparison): string => {
  const c = r.comparison
  if (!c) return `평가 불가 — ${r.reason}`
  const head = `기준 ${r.base.msrs.length}건보다 대상 ${r.target.msrs.length}건의 평균이 `
    + `${c.shift >= 0 ? '+' : ''}${c.shift.toFixed(2)}${r.unit ? ` ${r.unit}` : ''}`
  if (c.shiftInBaseSigma == null || c.threeSigmaRatio == null) {
    return `${head} 이동했습니다. 기준 3σ 가 0 이라 배율은 계산하지 않습니다.`
  }
  return `${head}(기준 3σ 의 ${Math.abs(c.shiftInBaseSigma).toFixed(1)}배) 이동했고 3σ 는 ${c.threeSigmaRatio.toFixed(1)}배입니다.`
}
