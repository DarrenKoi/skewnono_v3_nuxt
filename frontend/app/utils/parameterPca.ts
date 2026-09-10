// PCA placement of tools over their per-parameter offsets — the 장비 그룹
// 배치도 when the reader has said which parameters matter.
//
// The server ships `parameter_profile`: one row per tool, one column per
// measured parameter of the picked recipe, each entry the tool's offset from
// the fleet median FOR THAT PARAMETER (nm). This file turns the selected
// columns into 2D positions by principal components, so tools that drift the
// same way across many parameters land together and a tool that is off on one
// parameter only is visibly off along one direction.
//
// Why PCA rather than the classical-MDS map in fleetMap.ts: MDS places tools
// from ONE pairwise matrix (today's fleet matrix), which already folds every
// parameter into a single number per pair. With the profile the parameters
// are separate columns, and PCA is the method that (a) finds the directions
// along which the fleet actually spreads, (b) says how much of the spread the
// two drawn axes carry (`explained`), and (c) names which parameters make up
// each axis (`loadings`) — the three things an engineer asks of the picture.
//
// Units. Every column is first expressed as a fraction of ITS OWN action
// limit (1% of that parameter's CD — `fractionOfLimit`), the same index the
// cells are judged in. Without that a 68 nm feature's offsets dwarf a 32 nm
// feature's simply because they are bigger numbers, and PC1 becomes "which
// parameter is largest" instead of "which tools drift together". No further
// standardisation: z-scoring would inflate a parameter on which the whole
// fleet agrees to the same weight as one on which it splits, and the split
// is what the map is for.
//
// Distances. Positions are Euclidean over the used columns (exact when two
// components carry everything, approximate otherwise — `explained` says how
// approximate). The red rule, however, reads the CHEBYSHEV distance — a pair's
// worst single parameter — because the tolerance is per cell: a pair fails
// N배화 when any one parameter puts them apart, not when their RMS does.
//
// Dependency-free like fleetMap.ts, and for the same reason (the cloud numpy
// incident). The eigen-solver is fleetMap's Jacobi, exported from there.

import { jacobiEigen } from './fleetMap.ts'
import { mean } from './stats.ts'
import { fractionOfLimit, isMeasured, resolveNominalCd } from './tttmLimits.ts'

export interface ProfileAxis {
  name: string
  median_cd_nm: number | null
  /** Distinct tools that measured it; below 2 the column is all null. */
  tools: number
}

export interface ParameterProfile {
  parameters: ProfileAxis[]
  tools: string[]
  /** tool × parameter: offset from the fleet median (nm), null = not measured. */
  values: (number | null)[][]
}

export interface PcaPoint {
  eqp_id: string
  x: number
  y: number
  /** Mean Chebyshev distance (× action limit) to every other placed tool. */
  score: number
  /** Chebyshev distance to the closest placed tool — compare to the tolerance index. */
  nearest: number
}

export interface PcaLoading {
  name: string
  pc1: number
  pc2: number
}

export interface PcaResult {
  points: PcaPoint[]
  /** Tools left out because a used column is null for them — no honest position exists. */
  detached: string[]
  /** The columns the picture was computed over, in profile order. */
  parameters: string[]
  /** Fraction of the total variance on PC1 and PC2. */
  explained: [number, number]
  /** Each used parameter's weight on the two drawn axes. */
  loadings: PcaLoading[]
}

/**
 * Place `tools` by PCA over the `selected` columns of `profile` (every usable
 * column when `selected` is empty).
 *
 * Returns null when there is nothing to compute over — no usable column at
 * all — so the caller can fall back to the fleet-matrix map. Fewer than two
 * placeable tools yields no points but still reports what was used and who
 * was dropped, because "cannot draw" and "nothing selected" are different
 * captions.
 */
/** A profile column the picture is computed over, with its own action limit. */
export interface UsedColumn {
  name: string
  /** Index into `profile.parameters` / each row of `profile.values`. */
  index: number
  /** The CD this column's action limit is drawn against. */
  limitCd: number
}

/**
 * The profile columns a selection resolves to — every usable column when
 * `selected` is empty.
 *
 * A column one tool measured is all null by contract, so using it would drop
 * every tool; it is skipped rather than allowed to empty the map.
 *
 * Exported because the 배치도 and the 튜닝 목표 table MUST run over the same
 * columns: the table states where the group's centre is in this space, and a
 * table computed over a different column set would be describing a centre the
 * map does not draw.
 */
export const usableColumns = (
  profile: ParameterProfile,
  selected: readonly string[]
): UsedColumn[] => {
  const wanted = new Set(selected)
  return profile.parameters
    .flatMap((axis, index) =>
      axis.tools >= 2 && (wanted.size === 0 || wanted.has(axis.name))
        ? [{ name: axis.name, index, limitCd: resolveNominalCd(axis.median_cd_nm).nm }]
        : []
    )
}

/**
 * Each tool's readings on `columns`, in the profile's own nanometres.
 *
 * A tool is PLACED only when it measured every used column: a hole has no
 * honest position and no honest distance, and filling it with the consensus
 * would place an unmeasured tool exactly at the centre — the one place that
 * asserts it matches the fleet. The rest come back as `detached`.
 *
 * Shared with pmTuningTarget for the same reason `usableColumns` is: the
 * centroid the table quotes has to be the mean of the tools the map actually
 * drew, or the two surfaces describe different groups.
 */
export const profileRows = (
  profile: ParameterProfile,
  columns: readonly UsedColumn[],
  tools: readonly string[]
): { placed: { eqp_id: string, row: number[] }[], detached: string[] } => {
  const rowOf = new Map(profile.tools.map((eqp, i) => [eqp, i]))
  const placed: { eqp_id: string, row: number[] }[] = []
  const detached: string[] = []

  for (const eqp of tools) {
    const r = rowOf.get(eqp)
    const raw = r === undefined ? undefined : profile.values[r]
    const row: number[] = []
    let complete = raw !== undefined
    if (raw) {
      for (const c of columns) {
        const v = raw[c.index]
        if (!isMeasured(v)) {
          complete = false
          break
        }
        row.push(v)
      }
    }
    if (complete) placed.push({ eqp_id: eqp, row })
    else detached.push(eqp)
  }

  return { placed, detached }
}

export function parameterPca(
  profile: ParameterProfile,
  selected: readonly string[],
  tools: readonly string[]
): PcaResult | null {
  const columns = usableColumns(profile, selected)
  if (columns.length === 0) return null

  const parameters = columns.map(c => c.name)
  const { placed, detached } = profileRows(profile, columns, tools)

  const n = placed.length
  const k = columns.length
  if (n < 2) return { points: [], detached, parameters, explained: [0, 0], loadings: [] }

  // Into index units — each column as a fraction of ITS OWN action limit —
  // before anything else, so a 68 nm feature's offsets cannot dwarf a 32 nm
  // feature's simply for being bigger numbers. Then centre each column on its
  // mean: PCA is about spread around the centre, and the server's
  // median-centring is per column over ALL tools, not the placed subset.
  const centred = placed.map(p => p.row.map((v, j) => fractionOfLimit(v, columns[j]!.limitCd)))
  for (let j = 0; j < k; j++) {
    const m = mean(centred.map(row => row[j]!))
    for (const row of centred) row[j] = row[j]! - m
  }

  // Covariance (k × k) and its eigen-decomposition. k is the parameter count
  // — tens at most — so Jacobi is instant.
  const cov: number[][] = Array.from({ length: k }, () => Array<number>(k).fill(0))
  for (const row of centred) {
    for (let a = 0; a < k; a++) {
      for (let b = a; b < k; b++) {
        cov[a]![b] = cov[a]![b]! + row[a]! * row[b]!
      }
    }
  }
  for (let a = 0; a < k; a++) {
    for (let b = a; b < k; b++) {
      const v = cov[a]![b]! / (n - 1)
      cov[a]![b] = v
      cov[b]![a] = v
    }
  }
  const { values, vectors } = jacobiEigen(cov)
  const order = values
    .map((val, idx) => ({ val: Math.max(val, 0), idx }))
    .sort((p, q) => q.val - p.val)
  const total = order.reduce((sum, e) => sum + e.val, 0)
  const first = order[0]!
  const second = order[1] ?? null

  // Component vectors (columns of `vectors`), a zero vector when there is no
  // second component — one parameter selected gives a line, honestly.
  const component = (entry: { idx: number } | null) =>
    entry ? Array.from({ length: k }, (_, j) => vectors[j]![entry.idx]!) : Array<number>(k).fill(0)
  const v1 = component(first)
  const v2 = component(second)

  const project = (row: number[], v: number[]) => row.reduce((sum, x, j) => sum + x * v[j]!, 0)
  const coords = centred.map(row => [project(row, v1), project(row, v2)])

  // Eigenvectors are defined up to sign; pin each axis so its largest
  // coordinate is positive, and flip the loadings with it so the two agree.
  for (const [axis, v] of [[0, v1], [1, v2]] as const) {
    let extreme = 0
    for (const c of coords) if (Math.abs(c[axis]!) > Math.abs(extreme)) extreme = c[axis]!
    if (extreme < 0) {
      for (const c of coords) c[axis] = -c[axis]!
      for (let j = 0; j < k; j++) v[j] = -v[j]!
    }
  }

  // Chebyshev — the pair's worst parameter — is what the tolerance is about.
  //
  // Read off `centred`, not `placed`: `placed` rows are the profile's raw
  // nanometres now, and `nearest` is compared against a CD-relative tolerance
  // index. Centring is a per-column constant, so it cancels in a difference —
  // these are the index-space distances, with no second conversion to drift.
  const cheb = (a: number[], b: number[]) => {
    let worst = 0
    for (let j = 0; j < k; j++) worst = Math.max(worst, Math.abs(a[j]! - b[j]!))
    return worst
  }
  const points: PcaPoint[] = placed.map((p, i) => {
    const others = centred.filter((_, j) => j !== i).map(q => cheb(centred[i]!, q))
    return {
      eqp_id: p.eqp_id,
      x: coords[i]![0]!,
      y: coords[i]![1]!,
      score: mean(others),
      nearest: Math.min(...others)
    }
  })

  return {
    points,
    detached,
    parameters,
    explained: [
      total > 0 ? first.val / total : 0,
      total > 0 && second ? second.val / total : 0
    ],
    loadings: parameters.map((name, j) => ({ name, pc1: v1[j]!, pc2: v2[j]! }))
  }
}
