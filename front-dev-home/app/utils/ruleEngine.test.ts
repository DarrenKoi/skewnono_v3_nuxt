// Pure-logic tests for ruleEngine. Zero deps — run with Node's built-in runner:
//   node --test app/utils/ruleEngine.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  deriveType, deriveFamily, derivePhase, deriveMemoryClass,
  capFor, applyAnnotation, resolveRuleCell, evaluateRecipe, evaluateLot,
  classifyHealth, type RuleCell, type RecipeInput
} from './ruleEngine.ts'

// --- fixtures ---
const coreEarlyDram: RuleCell = {
  id: 'r3-core-tev-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [{ patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains', cap: 13 }]
}
const sampleDram: RuleCell = {
  id: 'r3-sample-dram',
  selector: { fac_id: 'R3', recipe_class: 'Sample', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 0 },
  // providers/rules.py `_SAMPLE_OVERRIDES` 를 그대로 옮긴 것입니다 — DUMMY 면제
  // 포함 (user-confirmed 2026-08-05).
  name_overrides: [
    { patterns: ['WAFER', 'WF'], match: 'affix', cap: null },
    { patterns: ['DUMMY'], match: 'affix', cap: null }
  ]
}
const wfOverride = { patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains' as const, cap: 13 }
// D8 — Core early NAND (EDGE 8), Core TV/PV (EDGE/EDGE_EX 16, no memory split)
const coreEarlyNand: RuleCell = {
  id: 'r3-core-tev-nand',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'NAND' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 8, EDGE_EX: 0, _other: 9 },
  name_overrides: [wfOverride]
}
const coreTvPv: RuleCell = {
  id: 'r3-core-tvpv',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['TV', 'PV'] },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 16, EDGE_EX: 16, _other: 9 },
  name_overrides: [wfOverride]
}
// D8 — Pool keys on yield_check (phase ignored); after-yield opens EDGE_EX
const poolBeforeDram: RuleCell = {
  id: 'r3-pool-before-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Pool', yield_check: 'before', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [wfOverride]
}
const poolAfterDram: RuleCell = {
  id: 'r3-pool-after-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Pool', yield_check: 'after', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 10, _other: 9 },
  name_overrides: [wfOverride]
}
const sampleNand: RuleCell = {
  id: 'r3-sample-nand',
  selector: { fac_id: 'R3', recipe_class: 'Sample', memory_class: 'NAND' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 8, EDGE_EX: 0, _other: 0 },
  // providers/rules.py `_SAMPLE_OVERRIDES` 를 그대로 옮긴 것입니다 — DUMMY 면제
  // 포함 (user-confirmed 2026-08-05).
  name_overrides: [
    { patterns: ['WAFER', 'WF'], match: 'affix', cap: null },
    { patterns: ['DUMMY'], match: 'affix', cap: null }
  ]
}
// D15 — same selector shape, different fab (M-fab recipe_class × memory_class)
const mfabMainDram: RuleCell = {
  id: 'm14-main-dram',
  selector: { fac_id: 'M14', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 99, EDGE_EX: 99, _other: 99 },
  name_overrides: []
}
const recipe = (over: Partial<RecipeInput>): RecipeInput => ({
  lot_cd: 'R3K-12', recipe_id: 'R', fac_id: 'R3', ctn_desc: 't-EV DRAM dev', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 't-EV', memory_class_auto: 'DRAM', parameters: [], ...over
})

// --- D10 deriveType: longest-prefix, suffix allowed, Class-independent ---
test('deriveType', () => {
  assert.equal(deriveType('WAFER'), 'WAFER')
  assert.equal(deriveType('WAFER_2'), 'WAFER') // suffix allowed
  assert.equal(deriveType('EDGE_EX'), 'EDGE_EX')
  assert.equal(deriveType('EDGE_EX_3'), 'EDGE_EX') // longest match beats EDGE
  assert.equal(deriveType('EDGE_WF_CD'), 'EDGE') // prefix EDGE, inner WF ignored
  assert.equal(deriveType('DSPT_CD'), 'OTHER')
  assert.equal(deriveType('X_WF'), 'OTHER')
})

// --- D3/D7 derivations ---
test('deriveFamily priority VG > Pool > Core', () => {
  assert.equal(deriveFamily('vertical gate pool lot'), 'VG_RTC_Cubic')
  assert.equal(deriveFamily('Pool제 dram'), 'Pool')
  assert.equal(deriveFamily('plain core lot'), 'Core')
})
test('derivePhase t-EV before EV, null fallback', () => {
  assert.equal(derivePhase('t-EV dram'), 't-EV')
  assert.equal(derivePhase('PV transfer'), 'PV')
  assert.equal(derivePhase('TV qual'), 'TV')
  assert.equal(derivePhase('EV early'), 'EV')
  assert.equal(derivePhase('no keyword'), null)
})
test('deriveType tolerates empty/malformed name', () => {
  assert.equal(deriveType(''), 'OTHER')
  assert.equal(deriveType(undefined as unknown as string), 'OTHER')
})
test('deriveMemoryClass DRAM/NAND/FLASH + unknown', () => {
  assert.equal(deriveMemoryClass('DRAM'), 'DRAM')
  assert.equal(deriveMemoryClass('NAND'), 'NAND')
  assert.equal(deriveMemoryClass('FLASH'), 'NAND')
  assert.equal(deriveMemoryClass('Tech'), 'unknown')
  assert.equal(deriveMemoryClass('Advanced'), 'unknown')
})

// --- D9 capFor: type wins over name-override ---
test('capFor: type cap beats name-override', () => {
  assert.equal(capFor({ name: 'EDGE_WF_CD', point_count: 12 }, coreEarlyDram), 10) // EDGE, NOT 13
  assert.equal(capFor({ name: 'EDGE_EX', point_count: 0 }, coreEarlyDram), 0)
})
test('capFor: OTHER param uses name-override then _other', () => {
  assert.equal(capFor({ name: 'DSPT_CD', point_count: 13 }, coreEarlyDram), 13) // override
  assert.equal(capFor({ name: 'RANDOM', point_count: 5 }, coreEarlyDram), 9) // _other
})
test('capFor: Sample affix exemption returns null (no limit)', () => {
  assert.equal(capFor({ name: 'X_WF', point_count: 99 }, sampleDram), null) // exempt
  assert.equal(capFor({ name: 'RANDOM', point_count: 1 }, sampleDram), 0) // _other 0
})

// Sample 셀의 _other 는 0 이라, 면제가 없으면 자리 표시용 DUMMY 가 point 1 만
// 있어도 항상 위반입니다 (user-confirmed 2026-08-05).
test('capFor: Sample DUMMY is exempt, not capped at 0', () => {
  assert.equal(capFor({ name: 'DUMMY', point_count: 1 }, sampleDram), null)
  assert.equal(capFor({ name: 'DUMMY_1', point_count: 9 }, sampleDram), null)
  assert.equal(capFor({ name: 'CD_DUMMY', point_count: 9 }, sampleDram), null)
})

test('evaluateRecipe: a Sample DUMMY no longer makes the recipe violate', () => {
  const merged = applyAnnotation(recipe({
    recipe_class: 'Sample',
    parameters: [{ name: 'WAFER_CD', point_count: 13 }, { name: 'DUMMY', point_count: 1 }]
  }))
  const evaluated = evaluateRecipe(merged, resolveRuleCell(merged, [sampleDram]))

  assert.equal(evaluated.pass, true)
  assert.deepEqual(evaluated.violation_params, [])
  // 목록에서 빼는 것이 아니라 판정에서만 빼므로 파라미터 수는 그대로입니다.
  assert.equal(evaluated.total_params, 2)
  assert.equal(evaluated.results.find(r => r.name === 'DUMMY')?.cap, null)
})

// --- D8/D14 cell resolution ---
test('resolveRuleCell: match / Gray-A / Gray-B', () => {
  const merged = applyAnnotation(recipe({}))
  assert.equal(resolveRuleCell(merged, [coreEarlyDram]).kind, 'cell')

  const vg = applyAnnotation(recipe({ family: 'VG_RTC_Cubic' }))
  const grayA = resolveRuleCell(vg, [coreEarlyDram])
  assert.equal(grayA.kind, 'gray')
  assert.equal(grayA.kind === 'gray' && grayA.gray, 'A') // no rule

  const tech = applyAnnotation(recipe({ memory_class_auto: 'unknown' }))
  const grayB = resolveRuleCell(tech, [coreEarlyDram])
  assert.equal(grayB.kind === 'gray' && grayB.gray, 'B') // memory_class 미설정
})
test('annotation overrides auto memory_class → resolves', () => {
  const tech = recipe({ memory_class_auto: 'unknown' })
  const merged = applyAnnotation(tech, { memory_class: 'DRAM' })
  assert.equal(resolveRuleCell(merged, [coreEarlyDram]).kind, 'cell')
})

// --- D5 evaluation: under-measuring is never a violation ---
test('evaluateRecipe: over=violation, under=OK', () => {
  const over = applyAnnotation(recipe({ parameters: [{ name: 'EDGE', point_count: 12 }] }))
  const rOver = evaluateRecipe(over, resolveRuleCell(over, [coreEarlyDram]))
  assert.equal(rOver.pass, false)
  assert.equal(rOver.violation_params.length, 1)

  const under = applyAnnotation(recipe({ parameters: [{ name: 'EDGE', point_count: 8 }] }))
  const rUnder = evaluateRecipe(under, resolveRuleCell(under, [coreEarlyDram]))
  assert.equal(rUnder.pass, true) // 8 ≤ 10
})
test('evaluateRecipe: gray recipe is pass (conservative)', () => {
  const vg = applyAnnotation(recipe({ family: 'VG_RTC_Cubic', parameters: [{ name: 'EDGE', point_count: 999 }] }))
  const r = evaluateRecipe(vg, resolveRuleCell(vg, [coreEarlyDram]))
  assert.equal(r.pass, true)
  assert.equal(r.gray, 'A')
})

// --- D14 lot roll-up: gray excluded from denominator ---
test('evaluateLot: ratio, health, gray excluded', () => {
  const recipes = [
    recipe({ recipe_id: 'r1', parameters: [{ name: 'EDGE', point_count: 12 }] }), // violation
    recipe({ recipe_id: 'r2', parameters: [{ name: 'EDGE', point_count: 8 }] }), // ok
    recipe({ recipe_id: 'r3', memory_class_auto: 'unknown', parameters: [{ name: 'EDGE', point_count: 12 }] }) // gray-B
  ]
  const h = evaluateLot('R3K-12', recipes, [coreEarlyDram])
  assert.equal(h.total_recipes, 3)
  assert.equal(h.violation_recipes, 1)
  assert.equal(h.violation_ratio, 0.5) // 1 / 2 evaluated (gray excluded)
  assert.equal(h.health, 'red')
})

test('classifyHealth thresholds', () => {
  assert.equal(classifyHealth(0.05), 'green')
  assert.equal(classifyHealth(0.15), 'yellow')
  assert.equal(classifyHealth(0.25), 'red')
})

// --- D15 fab is a real axis: a cell from another fab must never match ---
test('resolveRuleCell: cross-fab cell is ignored (D15)', () => {
  // R3 recipe, only an M14 cell present → no rule (Gray-A), not a silent match
  const r3 = applyAnnotation(recipe({}))
  assert.equal(resolveRuleCell(r3, [mfabMainDram]).kind, 'gray')
  // both fabs present → R3 recipe resolves to the R3 cell, not M14's cap=99
  const both = resolveRuleCell(r3, [mfabMainDram, coreEarlyDram])
  assert.equal(both.kind === 'cell' && both.cell.id, 'r3-core-tev-dram')
  // an M14 recipe resolves to the M14 cell
  const m14 = applyAnnotation(recipe({ fac_id: 'M14' }))
  const mres = resolveRuleCell(m14, [mfabMainDram, coreEarlyDram])
  assert.equal(mres.kind === 'cell' && mres.cell.id, 'm14-main-dram')
})

// --- D19 Sample Core TV/PV EDGE bumps to 16; specific cell must precede phase-blind ---
test('D19 Sample Core TV/PV EDGE 16 beats phase-blind Sample (order = precedence)', () => {
  const sampleCoreTvpv: RuleCell = {
    id: 'r3-sample-core-tvpv',
    selector: { fac_id: 'R3', recipe_class: 'Sample', family: 'Core', phase_in: ['TV', 'PV'] },
    caps: { WAFER: 13, LEVEL: 4, EDGE: 16, EDGE_EX: 0, _other: 0 },
    // providers/rules.py `_SAMPLE_OVERRIDES` 를 그대로 옮긴 것입니다 — DUMMY 면제
  // 포함 (user-confirmed 2026-08-05).
  name_overrides: [
    { patterns: ['WAFER', 'WF'], match: 'affix', cap: null },
    { patterns: ['DUMMY'], match: 'affix', cap: null }
  ]
  }
  const coreTvpvSample = applyAnnotation(
    recipe({ recipe_class: 'Sample', family: 'Core', phase: 'PV', parameters: [{ name: 'EDGE', point_count: 14 }] })
  )
  // specific cell first → first-match picks it; EDGE 14 ≤ 16 passes
  const res = resolveRuleCell(coreTvpvSample, [sampleCoreTvpv, sampleDram])
  assert.equal(res.kind === 'cell' && res.cell.id, 'r3-sample-core-tvpv')
  assert.equal(evaluateRecipe(coreTvpvSample, res).pass, true)
  // without the specific cell, the phase-blind cap 10 would (wrongly) flag it — documents the gap D19 closes
  const fallback = resolveRuleCell(coreTvpvSample, [sampleDram])
  assert.equal(evaluateRecipe(coreTvpvSample, fallback).pass, false)
})

// --- D7 VG·RTC·Cubic reduces to DRAM-side when class is otherwise unset ---
test('applyAnnotation: VG/RTC/Cubic falls back to DRAM (D7)', () => {
  const vg = applyAnnotation(recipe({ family: 'VG_RTC_Cubic', memory_class_auto: 'unknown' }))
  assert.equal(vg.memory_class, 'DRAM')
  // manual annotation still wins over the fallback
  const forced = applyAnnotation(recipe({ family: 'VG_RTC_Cubic', memory_class_auto: 'unknown' }), { memory_class: 'NAND' })
  assert.equal(forced.memory_class, 'NAND')
})

// --- D8 Main matrix: NAND EDGE 8, Core TV/PV EDGE 16, Pool yield_check keying ---
test('D8 Core early NAND: EDGE cap 8', () => {
  const r = applyAnnotation(recipe({ memory_class_auto: 'NAND', parameters: [{ name: 'EDGE', point_count: 10 }] }))
  const res = evaluateRecipe(r, resolveRuleCell(r, [coreEarlyNand]))
  assert.equal(res.pass, false) // 10 > 8
})
test('D8 Core TV/PV: EDGE/EDGE_EX cap 16, no memory split', () => {
  const r = applyAnnotation(recipe({ phase: 'PV', parameters: [{ name: 'EDGE', point_count: 16 }, { name: 'EDGE_EX', point_count: 16 }] }))
  const res = evaluateRecipe(r, resolveRuleCell(r, [coreTvPv]))
  assert.equal(res.pass, true) // 16 ≤ 16 boundary
})
test('D8 Pool keys on yield_check, ignores phase', () => {
  // before-yield: EDGE_EX must be 0
  const before = applyAnnotation(
    recipe({ family: 'Pool', ctn_desc: 'PV Pool제 dram', phase: 'PV', parameters: [{ name: 'EDGE_EX', point_count: 5 }] }),
    { yield_check: 'before' }
  )
  assert.equal(evaluateRecipe(before, resolveRuleCell(before, [poolBeforeDram, poolAfterDram])).pass, false)
  // after-yield: EDGE_EX up to 10 allowed
  const after = applyAnnotation(
    recipe({ family: 'Pool', phase: 'PV', parameters: [{ name: 'EDGE_EX', point_count: 5 }] }),
    { yield_check: 'after' }
  )
  assert.equal(evaluateRecipe(after, resolveRuleCell(after, [poolBeforeDram, poolAfterDram])).pass, true)
})
test('D14 Pool missing yield_check → Gray-B', () => {
  const r = applyAnnotation(recipe({ family: 'Pool', parameters: [{ name: 'EDGE_EX', point_count: 5 }] }))
  const res = resolveRuleCell(r, [poolBeforeDram, poolAfterDram])
  assert.equal(res.kind === 'gray' && res.gray, 'B')
  assert.equal(res.kind === 'gray' && res.reason, 'yield_check 미설정')
})

// --- D5 boundaries: equality passes, cap 0 means any measurement violates ---
test('D5 boundary: point_count === cap passes', () => {
  const r = applyAnnotation(recipe({ parameters: [{ name: 'EDGE', point_count: 10 }] }))
  assert.equal(evaluateRecipe(r, resolveRuleCell(r, [coreEarlyDram])).pass, true) // 10 ≤ 10
})
test('D5 cap 0: EDGE_EX 0 passes, 1 violates', () => {
  const ok = applyAnnotation(recipe({ parameters: [{ name: 'EDGE_EX', point_count: 0 }] }))
  assert.equal(evaluateRecipe(ok, resolveRuleCell(ok, [coreEarlyDram])).pass, true)
  const bad = applyAnnotation(recipe({ parameters: [{ name: 'EDGE_EX', point_count: 1 }] }))
  assert.equal(evaluateRecipe(bad, resolveRuleCell(bad, [coreEarlyDram])).pass, false)
})

// --- D6 Sample matrix: per-type caps + NAND EDGE 8 ---
test('D6 Sample DRAM caps per type', () => {
  assert.equal(capFor({ name: 'WAFER', point_count: 13 }, sampleDram), 13)
  assert.equal(capFor({ name: 'LEVEL', point_count: 4 }, sampleDram), 4)
  assert.equal(capFor({ name: 'EDGE', point_count: 10 }, sampleDram), 10)
  assert.equal(capFor({ name: 'EDGE_EX', point_count: 0 }, sampleDram), 0)
})
test('D6 Sample NAND: EDGE cap 8', () => {
  assert.equal(capFor({ name: 'EDGE', point_count: 8 }, sampleNand), 8)
})

// --- D16/D17/D18 thresholds are injected, not hardcoded ---
test('D16 classifyHealth honors injected thresholds', () => {
  const t = { yellow_at: 0.3, red_at: 0.6 }
  assert.equal(classifyHealth(0.25, t), 'green') // would be red under seed 0.1/0.2
  assert.equal(classifyHealth(0.45, t), 'yellow')
  assert.equal(classifyHealth(0.7, t), 'red')
})
test('D17 evaluateLot threads thresholds through to health', () => {
  const recipes = [
    recipe({ recipe_id: 'r1', parameters: [{ name: 'EDGE', point_count: 12 }] }), // violation
    recipe({ recipe_id: 'r2', parameters: [{ name: 'EDGE', point_count: 8 }] }) // ok
  ]
  // ratio 0.5 → red under seed, but green under a permissive saved threshold
  assert.equal(evaluateLot('R3K-12', recipes, [coreEarlyDram]).health, 'red')
  assert.equal(evaluateLot('R3K-12', recipes, [coreEarlyDram], undefined, { yellow_at: 0.6, red_at: 0.8 }).health, 'green')
})
