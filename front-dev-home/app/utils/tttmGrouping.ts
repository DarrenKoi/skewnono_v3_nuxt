// Pure skew-grouping engine (its one import, tttmLimits, is pure too). The
// server sends raw pairwise skew matrices; the client computes N배화
// (= maximal cliques) at a tolerance.
//
// The tolerance the GROUPING uses is CD-relative, not nanometres. Cells sit at
// different pattern sizes and the matching requirement scales with pattern
// size, so intersecting cliques from a 32 nm cell and a 68 nm cell against one
// absolute nm number compares quantities that are not comparable — it holds the
// large-pattern cell to a standard twice as strict as the small one, for no
// stated reason. Each cell is judged against its own CD instead.

// All CD-ratio arithmetic — the index type, the nm conversion, the measured
// predicate — lives in tttmLimits, so a component never imports one half of
// the concept from here and the other half from there.
import {
  effectiveToleranceNm,
  fractionOfLimit,
  isMeasured,
  type ToleranceIndex
} from './tttmLimits.ts'

export type ToleranceNm = number

export interface SkewMatrix {
  tools: string[]
  // Symmetric, diagonal 0. null = the pair has no data (never TTTM).
  values: (number | null)[][]
}

export type Confidence = 'High' | 'Med' | 'Low'
export type Tier = 'direct' | 'predicted'

// Bron–Kerbosch (no pivot — fleets are small, ~5-12 tools). Returns every
// MAXIMAL clique, including singletons (a tool TTTM with nobody).
export function maximalCliques(adj: boolean[][]): number[][] {
  const n = adj.length
  const all = new Set<number>(Array.from({ length: n }, (_, i) => i))
  const out: number[][] = []

  const neighbors = (v: number): Set<number> => {
    const s = new Set<number>()
    for (let u = 0; u < n; u++) if (adj[v]![u]) s.add(u)
    return s
  }

  const bk = (R: Set<number>, P: Set<number>, X: Set<number>) => {
    if (P.size === 0 && X.size === 0) {
      out.push([...R].sort((a, b) => a - b))
      return
    }
    for (const v of [...P]) {
      const Nv = neighbors(v)
      bk(
        new Set([...R, v]),
        new Set([...P].filter(u => Nv.has(u))),
        new Set([...X].filter(u => Nv.has(u)))
      )
      P.delete(v)
      X.add(v)
    }
  }

  bk(new Set(), all, new Set())
  return out
}

// Two tools are mutually TTTM when their pairwise skew is <= tolerance.
export function buildAdjacency(matrix: SkewMatrix, tolerance: ToleranceNm): boolean[][] {
  const n = matrix.tools.length
  const adj: boolean[][] = Array.from({ length: n }, () => Array<boolean>(n).fill(false))
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const v = matrix.values[i]?.[j]
      const tttm = isMeasured(v) && v <= tolerance
      adj[i]![j] = tttm
      adj[j]![i] = tttm
    }
  }
  return adj
}

export interface GroupCell {
  tier: Tier
  confidence: Confidence
  matrix: SkewMatrix // use direct_skew_matrix ?? predicted_skew_matrix at the call site
  /**
   * The CD (nm) this cell was measured at — already resolved, so a cell with no
   * median CD arrives carrying the monitor-wafer fallback rather than a null
   * this engine would have to interpret. Use `resolveNominalCd().nm`.
   */
  cdNm: number
}

export interface NbaGroup {
  tools: string[]
  n: number
  /**
   * The group's worst pair as a CD-relative index — the ranking key, and the
   * only cross-cell comparable measure of how well the group matches.
   */
  weakestPairIndex: number
  /**
   * That same worst pair in nanometres, from the cell that produced it.
   *
   * NOT the max nm across cells, which is what this used to be: with cells at
   * different CDs the largest nm and the worst match are frequently different
   * pairs, and reporting one while ranking by the other puts a number on screen
   * that does not explain the ordering.
   */
  weakestPairSkew: number
  confidence: Confidence // weakest among contributing cells
  tier: Tier // 'predicted' if any contributing cell is predicted
}

const CONF_RANK: Record<Confidence, number> = { High: 3, Med: 2, Low: 1 }

// Weakest (lowest) confidence / predicted-dominant tier across cells.
function inheritConfidence(cells: GroupCell[]): { confidence: Confidence, tier: Tier } {
  let confidence: Confidence = 'High'
  let tier: Tier = 'direct'
  for (const c of cells) {
    if (CONF_RANK[c.confidence] < CONF_RANK[confidence]) confidence = c.confidence
    if (c.tier === 'predicted') tier = 'predicted'
  }
  return { confidence, tier }
}

export function groupFromCells(cells: GroupCell[], tolerance: ToleranceIndex): NbaGroup[] {
  if (cells.length === 0) return []
  const tools = cells[0]!.matrix.tools
  const n = tools.length

  // All cells must share the same tool list in the same order — the AND-fold
  // below aligns cells by positional index. Fail loud rather than silently
  // mis-grouping (matters when office swaps in real multi-source data).
  for (const cell of cells) {
    const t = cell.matrix.tools
    if (t.length !== n || t.some((name, i) => name !== tools[i])) {
      throw new Error('groupFromCells: every cell must share the same tool list/order as cells[0]')
    }
  }

  // Intersect adjacency: a pair is TTTM only if it passes in EVERY cell — but
  // "passes" is now that cell's OWN nm threshold, derived from its CD. A 68 nm
  // cell gets a wider allowance than a 32 nm one because its limit really is
  // wider, not because we relaxed the standard for it.
  const inter: boolean[][] = Array.from({ length: n }, () => Array<boolean>(n).fill(true))
  for (let i = 0; i < n; i++) inter[i]![i] = false
  for (const cell of cells) {
    const adj = buildAdjacency(cell.matrix, effectiveToleranceNm(tolerance, cell.cdNm))
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (!adj[i]![j]) inter[i]![j] = false
  }

  const { confidence, tier } = inheritConfidence(cells)

  // The worst cell for every pair, as a CD-relative index carrying the
  // nanometres it came from so the two always describe the same pair.
  //
  // Built once here rather than per pair inside the clique loop below: cliques
  // overlap, so a shared pair would be re-scanned across every clique that
  // contains it, and the number of maximal cliques grows as 3^(n/3). At today's
  // 5-tool fleets that is microseconds either way; the reason to pay it once is
  // that the cost stops being a function of the clique count.
  const worst: { index: number, nm: number }[][] = Array.from(
    { length: n },
    () => Array.from({ length: n }, () => ({ index: 0, nm: 0 }))
  )
  for (const cell of cells) {
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const v = cell.matrix.values[i]?.[j]
        if (!isMeasured(v)) continue
        const index = fractionOfLimit(v, cell.cdNm)
        if (index > worst[i]![j]!.index) worst[i]![j] = worst[j]![i] = { index, nm: v }
      }
    }
  }

  return maximalCliques(inter).map((clique): NbaGroup => {
    let weakest = { index: 0, nm: 0 }
    for (let a = 0; a < clique.length; a++) {
      for (let b = a + 1; b < clique.length; b++) {
        const pair = worst[clique[a]!]![clique[b]!]!
        if (pair.index > weakest.index) weakest = pair
      }
    }
    return {
      tools: clique.map(idx => tools[idx]!),
      n: clique.length,
      weakestPairIndex: Number(weakest.index.toFixed(6)),
      weakestPairSkew: Number(weakest.nm.toFixed(6)),
      confidence,
      tier
    }
  })
}

// max N → smaller weakest-pair INDEX → higher confidence.
//
// The tie-break is the index rather than the nanometres: two groups whose worst
// pairs sit in cells at different CDs are not ranked by nm at all, and ranking
// by nm would prefer whichever group happened to be measured on the finer
// pattern regardless of how well its tools actually match.
export function pickPrimary(groups: NbaGroup[]): NbaGroup | null {
  if (groups.length === 0) return null
  return [...groups].sort((a, b) => {
    if (b.n !== a.n) return b.n - a.n
    if (a.weakestPairIndex !== b.weakestPairIndex) return a.weakestPairIndex - b.weakestPairIndex
    return CONF_RANK[b.confidence] - CONF_RANK[a.confidence]
  })[0]!
}
