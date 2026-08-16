// Pure, dependency-free skew-grouping engine. The server sends raw pairwise
// skew matrices; the client computes N배화 (= maximal cliques) at a tolerance.

export type ToleranceNm = number

export interface SkewMatrix {
  tools: string[]
  // Symmetric, diagonal 0. null = the pair has no data (never TTTM).
  values: (number | null)[][]
}

// "This pair was actually measured." Declared beside the type that permits the
// hole, because more than one engine has to ask the question and they must not
// answer it differently — `buildAdjacency` below and `retainComplete` in
// fleetMap.ts previously spelled it two ways, which disagreed on NaN.
export const isMeasured = (v: number | null | undefined): v is number => Number.isFinite(v)

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
}

export interface NbaGroup {
  tools: string[]
  n: number
  weakestPairSkew: number // max pairwise skew inside the group, across all cells
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

export function groupFromCells(cells: GroupCell[], tolerance: ToleranceNm): NbaGroup[] {
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

  // Intersect adjacency: a pair is TTTM only if <= tolerance in EVERY cell.
  const inter: boolean[][] = Array.from({ length: n }, () => Array<boolean>(n).fill(true))
  for (let i = 0; i < n; i++) inter[i]![i] = false
  for (const cell of cells) {
    const adj = buildAdjacency(cell.matrix, tolerance)
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (!adj[i]![j]) inter[i]![j] = false
  }

  const { confidence, tier } = inheritConfidence(cells)

  // Worst (max) pairwise skew across all cells, for a given index pair.
  const worst = (i: number, j: number): number => {
    let w = 0
    for (const cell of cells) {
      const v = cell.matrix.values[i]?.[j]
      if (v !== null && v !== undefined) w = Math.max(w, v)
    }
    return w
  }

  return maximalCliques(inter).map((clique): NbaGroup => {
    let weakest = 0
    for (let a = 0; a < clique.length; a++)
      for (let b = a + 1; b < clique.length; b++)
        weakest = Math.max(weakest, worst(clique[a]!, clique[b]!))
    return {
      tools: clique.map(idx => tools[idx]!),
      n: clique.length,
      weakestPairSkew: Number(weakest.toFixed(6)),
      confidence,
      tier
    }
  })
}

// max N → smaller weakest-pair skew → higher confidence.
export function pickPrimary(groups: NbaGroup[]): NbaGroup | null {
  if (groups.length === 0) return null
  return [...groups].sort((a, b) => {
    if (b.n !== a.n) return b.n - a.n
    if (a.weakestPairSkew !== b.weakestPairSkew) return a.weakestPairSkew - b.weakestPairSkew
    return CONF_RANK[b.confidence] - CONF_RANK[a.confidence]
  })[0]!
}
