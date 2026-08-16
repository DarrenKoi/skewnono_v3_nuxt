// Pure, dependency-free classical MDS (Torgerson) over a tool×tool skew matrix.
//
// This is a RENDERER, not an estimator: every number it reads is already
// asserted by the server in `fleet_today.matrix`. It recovers no hidden
// quantity, so it needs no ground truth to be checkable — the whole file is a
// pure function of its input and is tested as one. Contrast `tttmGrouping.ts`,
// which also only re-expresses what the server said.
//
// What it buys the reader: `consensus_deviation` collapses each tool onto ONE
// signed number against the fleet mean, so two tools that are both +0.10 nm
// look identical even when they are 0.20 nm apart from each other. The 2D map
// keeps the pairwise structure, so clusters and a genuinely detached tool are
// visible as position rather than as magnitude.
//
// Read positions RELATIVELY. MDS is defined only up to rotation, reflection and
// translation, so the axes carry no unit and no meaning — only the distances
// between points do. `orientDeterministically` below pins one of the many
// equally-correct orientations so the chart does not flip between renders.

import type { SkewMatrix } from './tttmGrouping'

export interface FleetPoint {
  eqp_id: string
  // Map coordinates in nm-like units (the embedding preserves the input scale),
  // but meaningful only as distances between points — never read alone.
  x: number
  y: number
  // Mean skew to every other retained tool: the doc's Score_i. Large = far from
  // the fleet as a whole, which is what makes a point an anomaly candidate.
  score: number
  // Skew to this tool's CLOSEST neighbour. This is the one that may be compared
  // against the tolerance, because the tolerance is a PAIRWISE spec: a tool is
  // unmatchable when even its best partner sits outside it. `score` is a mean
  // over the whole fleet and is not comparable to a pairwise threshold — in a
  // fleet holding one distant tool, every mean exceeds it and the comparison
  // marks the entire fleet as anomalous.
  nearest: number
}

export interface FleetMapResult {
  points: FleetPoint[]
  // Tools left out of the embedding because they have no usable distances.
  // A point with no distance to anything cannot be placed — see `fleetMap`.
  detached: string[]
  // Kruskal stress-1 over the retained pairs. 0 = the 2D picture reproduces the
  // matrix exactly; the conventional "poor" threshold is 0.20, above which the
  // reader should go back to the pairwise matrix instead of trusting positions.
  stress: number
}

// --- linear algebra -------------------------------------------------------
// Jacobi eigenvalue iteration for a real symmetric matrix. Exact enough at the
// sizes involved (a fab holds ~5-12 CD-SEMs) and keeps the file dependency-free,
// which matters here: the cloud numpy incident is why this project does not add
// a numeric dependency for something it can do in 40 lines.
function jacobiEigen(input: number[][], sweeps = 100): { values: number[], vectors: number[][] } {
  const n = input.length
  const m = input.map(row => [...row])
  const v: number[][] = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => (i === j ? 1 : 0))
  )

  for (let sweep = 0; sweep < sweeps; sweep++) {
    let off = 0
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) off += m[i]![j]! ** 2
    }
    if (off < 1e-20) break

    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) {
        const apq = m[p]![q]!
        if (Math.abs(apq) < 1e-20) continue
        const theta = (m[q]![q]! - m[p]![p]!) / (2 * apq)
        const t = (theta >= 0 ? 1 : -1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1))
        const c = 1 / Math.sqrt(t * t + 1)
        const s = t * c

        for (let k = 0; k < n; k++) {
          const kp = m[k]![p]!
          const kq = m[k]![q]!
          m[k]![p] = c * kp - s * kq
          m[k]![q] = s * kp + c * kq
        }
        for (let k = 0; k < n; k++) {
          const pk = m[p]![k]!
          const qk = m[q]![k]!
          m[p]![k] = c * pk - s * qk
          m[q]![k] = s * pk + c * qk
        }
        for (let k = 0; k < n; k++) {
          const kp = v[k]![p]!
          const kq = v[k]![q]!
          v[k]![p] = c * kp - s * kq
          v[k]![q] = s * kp + c * kq
        }
      }
    }
  }

  return { values: m.map((row, i) => row[i]!), vectors: v }
}

// --- null handling --------------------------------------------------------
// Classical MDS needs a COMPLETE distance matrix, but the contract permits null
// ("this pair has no data, never TTTM") anywhere in `values` — and the office
// adapter will emit them even though today's mock never does. A tool whose
// every off-diagonal entry is null has no distance to anything and therefore no
// position: there is no coordinate that is "right" for it, so inventing one
// would be the map lying.
//
// So: greedily drop whichever tool still has the most nulls until the remaining
// submatrix is complete. Greedy because dropping the worst offender first
// usually clears several nulls at once and retains the most tools; exact
// maximum-complete-submatrix is NP-hard and pointless at n ≈ 10. Dropped tools
// come back as `detached` so the UI can say they were left out and why, rather
// than silently showing a smaller fleet than the user has.
function retainComplete(values: (number | null)[][]): number[] {
  const n = values.length
  const keep = new Set<number>(Array.from({ length: n }, (_, i) => i))

  const nullCount = (i: number) =>
    [...keep].filter(j => j !== i && !Number.isFinite(values[i]?.[j] ?? null)).length

  for (;;) {
    let worst = -1
    let worstCount = 0
    for (const i of keep) {
      const c = nullCount(i)
      if (c > worstCount) {
        worstCount = c
        worst = i
      }
    }
    if (worst < 0) break
    keep.delete(worst)
  }

  return [...keep].sort((a, b) => a - b)
}

// MDS coordinates are arbitrary up to sign, and an unpinned sign makes the chart
// mirror itself between renders for no reason the reader can see. Force each
// axis so its largest-magnitude coordinate is positive.
function orientDeterministically(coords: number[][]): void {
  for (let axis = 0; axis < 2; axis++) {
    let extreme = 0
    for (const row of coords) {
      if (Math.abs(row[axis]!) > Math.abs(extreme)) extreme = row[axis]!
    }
    if (extreme < 0) for (const row of coords) row[axis] = -row[axis]!
  }
}

/**
 * Embed a tool×tool skew matrix into 2D by classical MDS.
 *
 * Returns points in the matrix's own tool order (minus detached tools), the
 * tools that could not be placed, and the stress of the 2D approximation.
 * Fewer than two placeable tools yields no points — a map of one tool shows
 * nothing a label does not.
 */
export function fleetMap(matrix: SkewMatrix): FleetMapResult {
  const keep = retainComplete(matrix.values)
  const detached = matrix.tools.filter((_, i) => !keep.includes(i))
  const n = keep.length

  if (n < 2) return { points: [], detached: [...matrix.tools], stress: 0 }

  // Distances of the retained submatrix, symmetrized: the contract promises
  // symmetry but an office adapter joining two sources could break it, and
  // averaging is cheaper than discovering the asymmetry as a complex eigenvalue.
  const d: number[][] = keep.map((i, a) =>
    keep.map((j, b) => {
      if (a === b) return 0
      const ij = matrix.values[i]?.[j] ?? 0
      const ji = matrix.values[j]?.[i] ?? 0
      return (Math.abs(ij) + Math.abs(ji)) / 2
    })
  )

  // Double-centre the squared distances: B = -1/2 · J D² J.
  const sq = d.map(row => row.map(x => x * x))
  const rowMean = sq.map(row => row.reduce((s, x) => s + x, 0) / n)
  const grand = rowMean.reduce((s, x) => s + x, 0) / n
  const b = sq.map((row, i) =>
    row.map((x, j) => -0.5 * (x - rowMean[i]! - rowMean[j]! + grand))
  )

  const { values, vectors } = jacobiEigen(b)
  // Top two eigenvalues. Negatives mean the distances are not Euclidean — normal
  // for measured skews — and clamp to zero, collapsing that axis rather than
  // producing NaN from a square root.
  const order = values
    .map((val, idx) => ({ val, idx }))
    .sort((p, q) => q.val - p.val)
    .slice(0, 2)

  const coords: number[][] = Array.from({ length: n }, () => [0, 0])
  order.forEach(({ val, idx }, axis) => {
    const scale = Math.sqrt(Math.max(val, 0))
    for (let i = 0; i < n; i++) coords[i]![axis] = vectors[i]![idx]! * scale
  })
  orientDeterministically(coords)

  // Kruskal stress-1 of the embedding against the distances it came from.
  let num = 0
  let den = 0
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const dx = coords[i]![0]! - coords[j]![0]!
      const dy = coords[i]![1]! - coords[j]![1]!
      const fitted = Math.sqrt(dx * dx + dy * dy)
      num += (fitted - d[i]![j]!) ** 2
      den += d[i]![j]! ** 2
    }
  }
  const stress = den > 0 ? Math.sqrt(num / den) : 0

  const points: FleetPoint[] = keep.map((toolIdx, i) => ({
    eqp_id: matrix.tools[toolIdx] ?? String(toolIdx),
    x: coords[i]![0]!,
    y: coords[i]![1]!,
    score: d[i]!.reduce((s, x) => s + x, 0) / (n - 1),
    nearest: Math.min(...d[i]!.filter((_, j) => j !== i))
  }))

  return { points, detached, stress }
}
