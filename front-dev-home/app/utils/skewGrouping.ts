// Pure, dependency-free skew-grouping engine. The server sends raw pairwise
// skew matrices; the client computes N배화 (= maximal cliques) at a tolerance.

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
        new Set([...X].filter(u => Nv.has(u))),
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
      const tttm = v !== null && v !== undefined && v <= tolerance
      adj[i]![j] = tttm
      adj[j]![i] = tttm
    }
  }
  return adj
}
