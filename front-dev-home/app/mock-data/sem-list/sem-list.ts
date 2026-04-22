import type { Fab } from '~/stores/navigation'

export interface SemListRow {
  fac_id: Exclude<Fab, 'all'>
  eqp_id: string
  eqp_model_cd: string
  eqp_grp_id: string
  vendor_nm: 'HITACHI' | 'AMAT'
  eqp_ip: string
  fab_name: string
  updt_dt: string
  available: 'On' | 'Off'
  version: number
}

export type SemListResponse = SemListRow[]
