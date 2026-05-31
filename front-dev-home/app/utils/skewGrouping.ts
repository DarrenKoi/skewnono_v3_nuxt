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
