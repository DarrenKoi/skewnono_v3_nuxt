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

const FAC_IDS: Exclude<Fab, 'all'>[] = ['M11', 'M12', 'M14', 'M15', 'M16', 'R3']
const FAB_SUFFIXES = ['A', 'B', 'C'] as const

const HITACHI_MODELS = ['CG6300', 'CG6320', 'CG6340', 'CG6360', 'CG6380', 'GT2000', 'GT2000S'] as const
const AMAT_MODELS = [
  'TP3000', 'TP3500', 'TP4000', 'TP4500',
  'PROVISION_10', 'PROVISION_20',
  'VERITYSEM_4', 'VERITYSEM_5'
] as const

const HITACHI_EQP_PREFIXES = ['ECXDX', 'ECDX', 'HCDX'] as const
const AMAT_EQP_PREFIXES = ['PCD', 'MCD', 'ACD', 'VCD'] as const

const EQP_GRP_PREFIXES = ['G-ECD-', 'G-MCD-', 'G-KCD-', 'G-MDS-', 'G-PCD-', 'G-ACD-'] as const

const mulberry32 = (seed: number) => {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6D2B79F5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const pick = <T>(rng: () => number, arr: readonly T[]): T => arr[Math.floor(rng() * arr.length)]!
const intBetween = (rng: () => number, min: number, max: number) =>
  Math.floor(rng() * (max - min + 1)) + min

const generateSemList = (nRows = 300, seed = 42, now = new Date('2026-04-19T00:00:00Z')): SemListRow[] => {
  const rng = mulberry32(seed)
  const rows: SemListRow[] = []

  for (let i = 0; i < nRows; i++) {
    const fac_id = pick(rng, FAC_IDS)

    const fab_name = fac_id === 'R3' && rng() < 0.3
      ? 'R4'
      : `${fac_id}${pick(rng, FAB_SUFFIXES)}`

    const vendor_nm: 'HITACHI' | 'AMAT' = rng() < 0.5 ? 'HITACHI' : 'AMAT'

    const model = vendor_nm === 'HITACHI' ? pick(rng, HITACHI_MODELS) : pick(rng, AMAT_MODELS)
    const eqp_prefix = vendor_nm === 'HITACHI'
      ? pick(rng, HITACHI_EQP_PREFIXES)
      : pick(rng, AMAT_EQP_PREFIXES)

    const eqp_id = `${eqp_prefix}${intBetween(rng, 100, 999)}`

    const grpPrefix = pick(rng, EQP_GRP_PREFIXES)
    const eqp_grp_id = `${grpPrefix}${String(intBetween(rng, 1, 3)).padStart(2, '0')}`

    const ipPrefix = rng() < 0.5 ? '177' : '197'
    const eqp_ip = `${ipPrefix}.${intBetween(rng, 1, 254)}.${intBetween(rng, 1, 254)}.${intBetween(rng, 1, 254)}`

    const daysAgo = intBetween(rng, 0, 90)
    const updt_dt = new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000).toISOString()

    const available: 'On' | 'Off' = rng() < 0.9 ? 'On' : 'Off'
    const version = intBetween(rng, 1, 3)

    rows.push({
      fac_id,
      eqp_id,
      eqp_model_cd: model,
      eqp_grp_id,
      vendor_nm,
      eqp_ip,
      fab_name,
      updt_dt,
      available,
      version
    })
  }

  return rows
}

export { generateSemList }

export const mockSemListResponse: SemListResponse = generateSemList()
