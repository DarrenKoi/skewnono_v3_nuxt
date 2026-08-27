import { joinApiPath } from '~/utils/apiPath'
import type { WindowWeeks } from '~/utils/analysisWindow'
import type { BeamCondition, CellSkew, ScanAxis } from '~/utils/pmPlanning'

export interface GateBlock {
  cd_monitoring_value: number
  cd_spec_lower: number
  cd_spec_upper: number
  cd_in_spec: boolean
  bsm_in_spec: boolean
  bsm_sharpness_avg: number
  bsm_noise_avg: number
  post_pm_at: string | null
  prev_post_delta: number | null
  mdc_changed: boolean
  verdict: 'up' | 'hold'
}

export interface EpochPoint {
  epoch_start: string
  mdc: number
  bsm_sharpness_avg: number
}

export interface ToolBlock {
  eqp_id: string
  gate: GateBlock
  cells: CellSkew[]
  epoch_history: EpochPoint[]
}

export interface ConsensusCell {
  beam: BeamCondition
  axis: ScanAxis
  consensus: number
}

export interface FleetDefaults {
  focus_n: number
  advisory_threshold: Record<string, number>
}

export interface FleetResponse {
  tool_type: 'cd-sem'
  fab_name: string
  fetched_at: string
  anchor_date: string
  /** How far back runs, BSM readings and PM events were gathered — echoed. */
  window_weeks: number
  beam_conditions: BeamCondition[]
  axes: ScanAxis[]
  defaults: FleetDefaults
  consensus: ConsensusCell[]
  tools: ToolBlock[]
}

export const usePmPlanningApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  // The same `window_weeks` the tttm check is fetched under: pm-planning joins
  // the two payloads, and one label has to describe both.
  const fetchPmPlanningFleet = async (
    fabName: string,
    windowWeeks: WindowWeeks
  ): Promise<FleetResponse> => {
    return await $fetch<FleetResponse>(
      joinApiPath(base, '/cdsem/pm-planning/fleet'),
      { query: { fab_name: fabName, window_weeks: windowWeeks } }
    )
  }

  return {
    fetchPmPlanningFleet
  }
}
