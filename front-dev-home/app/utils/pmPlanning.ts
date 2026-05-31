// Pure client-side logic for the pm-planning dashboard. Kept dependency-free
// and framework-free so it runs under `node --test`.

export type BeamCondition = '500V' | '800V'
export type ScanAxis = 'X' | 'Y'

export interface CellSkew {
  beam: BeamCondition
  axis: ScanAxis
  skew: number
  current_value: number
  median: number
  gap: number
}

export interface ToolCells {
  eqp_id: string
  cells: CellSkew[]
}

export interface GateInputs {
  cd_in_spec: boolean
  bsm_in_spec: boolean
}

export interface RankedTool {
  eqp_id: string
  score: number
  axis: ScanAxis
  nominated: boolean
}

export const maxAxisSkew = (
  cells: CellSkew[],
  beam: BeamCondition
): { score: number, axis: ScanAxis } => {
  let best: { score: number, axis: ScanAxis } = { score: 0, axis: 'X' }

  for (const cell of cells) {
    if (cell.beam !== beam) continue
    const score = Math.abs(cell.skew)
    if (score >= best.score) best = { score, axis: cell.axis }
  }

  return best
}

export const rankFocusTargets = (
  tools: ToolCells[],
  beam: BeamCondition,
  threshold: number,
  n: number
): RankedTool[] => {
  const candidates = tools
    .map((tool) => {
      const { score, axis } = maxAxisSkew(tool.cells, beam)
      return { eqp_id: tool.eqp_id, score, axis, nominated: false }
    })
    .filter(candidate => candidate.score > threshold)
    .sort((left, right) => right.score - left.score)

  return candidates.slice(0, n).map(candidate => ({
    ...candidate,
    nominated: true
  }))
}

export const gateVerdict = (gate: GateInputs): 'up' | 'hold' =>
  gate.cd_in_spec && gate.bsm_in_spec ? 'up' : 'hold'
