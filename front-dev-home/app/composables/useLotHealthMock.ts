import type { SummaryRow } from '~/composables/useRecipeStatisticsApi'
import { classifyHealth, type HealthLevel } from '~/components/cdsem/comparison/healthTokens'

export type DevStage = 'EV' | 'TV' | 'PV' | 'Pool' | '?'

export interface RuleCaps {
  para_16_max: number
  para_13_max: number
  para_9_max: number
  para_5_max: number
}

export interface HealthAugmentedRow extends SummaryRow {
  dev_stage: DevStage
  stage_inferred: boolean         // true when ctn_desc had no stage keyword
  caps: RuleCaps
  violations: number              // number of cap-categories exceeded
  cap_total: number               // sum of caps (used as denominator hint)
  para_total: number              // para_16+13+9+5
  violation_ratio: number         // violations / 4  (fraction of cap-categories breached)
  health: HealthLevel
  // Per-cell over indicator (how far past cap, in cap-relative units 0..2+).
  // Drives the cell stripe / chip intensity in the stacked bar.
  cap_breach: {
    para_16: number
    para_13: number
    para_9: number
    para_5: number
  }
}

const STAGE_PATTERNS: Array<{ stage: DevStage, regex: RegExp }> = [
  { stage: 'PV',   regex: /\bPV\b|\bP\.?V\b|\bpv\b/ },
  { stage: 'EV',   regex: /\bEV\b|\bE\.?V\b|\bev\b/ },
  { stage: 'TV',   regex: /\bTV\b|\bT\.?V\b|\btv\b/ },
  { stage: 'Pool', regex: /\bPool\b|\bpool\b|\bPOOL\b/ }
]

// CAPS_BY_STAGE — provisional rule snapshot (mirrors the seed in
// back_dev_home/ebeam/cdsem/device_statistics/rules.py). Later this composable
// is swapped for a real fetch against /admin/measurement-rules.
const CAPS_BY_STAGE: Record<DevStage, RuleCaps> = {
  EV:   { para_16_max: 14, para_13_max: 22, para_9_max: 30, para_5_max: 40 },  // strictest (earliest stage)
  TV:   { para_16_max: 18, para_13_max: 28, para_9_max: 38, para_5_max: 52 },
  PV:   { para_16_max: 24, para_13_max: 36, para_9_max: 48, para_5_max: 64 },
  Pool: { para_16_max: 30, para_13_max: 44, para_9_max: 58, para_5_max: 78 },  // most permissive
  '?':  { para_16_max: 14, para_13_max: 22, para_9_max: 30, para_5_max: 40 }   // unknown → strictest fallback (CONTEXT.md)
}

// M-fab caps — single rule per bucket, no stage axis. Tuned mid-strict.
const CAPS_MFAB: RuleCaps = { para_16_max: 16, para_13_max: 26, para_9_max: 36, para_5_max: 48 }

// only_sample bucket — universal cap, same across fab/stage.
const CAPS_SAMPLE: RuleCaps = { para_16_max: 4, para_13_max: 6, para_9_max: 9, para_5_max: 14 }

export const extractStage = (ctnDesc: string | undefined): DevStage => {
  if (!ctnDesc) return '?'
  for (const { stage, regex } of STAGE_PATTERNS) {
    if (regex.test(ctnDesc)) return stage
  }
  return '?'
}

export const getCaps = (
  facId: string,
  stage: DevStage,
  bucketKey: string
): RuleCaps => {
  if (bucketKey === 'only_sample_summary') return CAPS_SAMPLE
  if (facId === 'R3') return CAPS_BY_STAGE[stage]
  return CAPS_MFAB
}

export const augmentSummaryRow = (
  row: SummaryRow,
  bucketKey: string
): HealthAugmentedRow => {
  const stage = extractStage(row.ctn_desc)
  const stageInferred = stage === '?'
  const caps = getCaps(row.fac_id, stage, bucketKey)

  const breach = {
    para_16: Math.max(0, (row.para_16 - caps.para_16_max) / Math.max(1, caps.para_16_max)),
    para_13: Math.max(0, (row.para_13 - caps.para_13_max) / Math.max(1, caps.para_13_max)),
    para_9:  Math.max(0, (row.para_9  - caps.para_9_max)  / Math.max(1, caps.para_9_max)),
    para_5:  Math.max(0, (row.para_5  - caps.para_5_max)  / Math.max(1, caps.para_5_max))
  }

  const violations
    = (breach.para_16 > 0 ? 1 : 0)
    + (breach.para_13 > 0 ? 1 : 0)
    + (breach.para_9  > 0 ? 1 : 0)
    + (breach.para_5  > 0 ? 1 : 0)

  const violation_ratio = violations / 4

  return {
    ...row,
    dev_stage: stage,
    stage_inferred: stageInferred,
    caps,
    violations,
    cap_total: caps.para_16_max + caps.para_13_max + caps.para_9_max + caps.para_5_max,
    para_total: row.para_16 + row.para_13 + row.para_9 + row.para_5,
    violation_ratio,
    health: classifyHealth(violation_ratio),
    cap_breach: breach
  }
}

export const useLotHealthMock = () => {
  return {
    augmentSummaryRow,
    extractStage,
    getCaps
  }
}
